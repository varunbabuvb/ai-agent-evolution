"""Link event mentions that report the same real event (owner: TS, plan T7 / Day 9).

A 'mention' is one extracted/annotated event from one document (an `ainevo.schema.Event`-shaped row). Several
articles about the same release give several mentions; this module groups them and merges each group into one event.

Two mentions are linked only if ALL of these hold (precision first: a wrong merge hides a real event):
  1. DATE   : their dates are within `window_days` (month-only dates are treated as the whole month).
     CASE STUDY: neither title looks like a customer story / use-case post (see `CASE_STUDY`).
  TITLE  : when both mentions have the same model name, both titles must contain it (`names_model`).
  2. ORG    : if both name an organisation, the normalised organisations overlap.
  3. MODEL  : if both name a model/agent, the normalised names are IDENTICAL token by token. Versions are
              part of the name, so 'GPT-5' and 'GPT-5.5' never match even though their text is 99% similar
              (seed-timeline finding, Day 8). If a model name is missing on either side, the org must match
              and the text similarity must reach `sim_missing`.
  4. TEXT   : cosine similarity of the event texts >= `sim_min`.
Groups are built with union-find; a merge is refused if the group would span more than `max_span_days`
(stops long chains A~B~C~D from swallowing separate events).
"""
from __future__ import annotations

import calendar
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from ainevo.normalization.embed import TfidfEmbedder, event_text, similarity_matrix
from ainevo.schema import make_event_id

# Small alias table; full entity normalisation is a later step. Keys are lower-case, punctuation-free.
ORG_ALIASES = {
    "google research": "google", "google brain": "google", "google deepmind": "google", "deepmind": "google",
    "google": "google", "facebook ai": "meta", "facebook": "meta", "meta ai": "meta", "meta": "meta",
    "microsoft research": "microsoft", "microsoft": "microsoft", "openai": "openai",
    "anthropic": "anthropic", "xai": "xai", "alibaba": "alibaba", "alibaba cloud": "alibaba", "qwen": "alibaba",
    "zai zhipu ai": "zhipu", "zhipu ai": "zhipu", "zai": "zhipu", "deepseek": "deepseek",
    "moonshot": "moonshot", "moonshot ai": "moonshot", "mistral ai": "mistral", "mistral": "mistral",
    "nvidia": "nvidia", "amazon": "amazon", "aws": "amazon", "stack overflow": "stackoverflow",
}


# Product/family names that do not identify ONE release. Extractors and annotators often put these in model_agent
# ('ChatGPT' on every OpenAI post); two documents sharing them say nothing about being the same event, so they count
# as "no model name" and the stricter text rule applies.
GENERIC_MODELS = {("chatgpt",), ("gpt",), ("openai", "models"), ("openai", "api"), ("gpt", "models"), ("gpt", "model"),
                  ("model", "agent"), ("claude",), ("gemini",), ("codex",), ("ai",), ("llm",), ("llms",), ("api",),
                  ("models",), ("agents",), ("agent",), ("model",)}


# Customer stories and use-case posts ("Playco cut manual fixes ... with GPT-6 Astra", "Coding with OpenAI o1",
# "Minnesota's translation office uses ChatGPT") share the model name and day with the launch post but are not the
# launch. Harshita's review of 81 linked pairs found these were most of the false merges, so a document whose title
# looks like one is never linked to another document.
CASE_STUDY = re.compile(r"\b(?:with|using|powered by|uses|use|built on)\s+(?:openai\s+)?(?:gpt|chatgpt|claude|gemini|codex|o\d)\b", re.I)


def is_case_study(title) -> bool:
    return bool(title) and bool(CASE_STUDY.search(str(title)))


def _title_tokens(title) -> set[str]:
    return set(re.findall(r"[a-z]+|\d+(?:\.\d+)*", str(title).lower()))


def names_model(title, model: tuple[str, ...]) -> bool:
    """True if the title contains every token of the model name ('GPT-5.1' -> gpt, 5.1). Titles may be missing
    (seed or gold rows), in which case there is nothing to check and the answer is True."""
    if not title or not model:
        return True
    return set(model) <= _title_tokens(title)


@dataclass(frozen=True)
class LinkConfig:
    window_days: int = 1          # max gap between two mentions of one event (all 25 true pairs in the review were <= 1 day)
    sim_min: float = 0.2          # text similarity floor when both model names match
    sim_missing: float = 0.5      # text similarity needed when a model name is missing
    max_span_days: int = 14       # widest date span allowed inside one group


# ----------------------------------------------------------------------------- normalisation helpers
def norm_org(org) -> frozenset[str]:
    """Organisation string -> set of canonical names ('Google,Stanford' -> {'google','stanford'})."""
    if org is None or str(org).strip() in ("", "nan"):
        return frozenset()
    out = set()
    for part in re.split(r"[;,&]| and ", str(org)):
        key = re.sub(r"[^a-z0-9 ]", "", part.lower()).strip()
        if key:
            out.add(ORG_ALIASES.get(key, key))
    return frozenset(out)


def norm_model(name, org=None) -> tuple[str, ...]:
    """Model name -> tuple of tokens, version numbers kept whole: 'GPT-5.5' -> ('gpt','5.5').
    Parenthesised qualifiers like '(Mar 2025)' are dropped; the date window separates those versions.
    If the name starts with the mention's own organisation ('OpenAI GPT-4o'), that prefix is removed."""
    if name is None or str(name).strip() in ("", "nan"):
        return ()
    s = re.sub(r"\(.*?\)", " ", str(name).lower())
    toks = re.findall(r"[a-z]+|\d+(?:\.\d+)*", s)
    if org is not None and str(org).strip() not in ("", "nan"):
        org_toks = set(re.findall(r"[a-z]+", str(org).lower()))
        while toks and toks[0] in org_toks:
            toks = toks[1:]
    return () if tuple(toks) in GENERIC_MODELS else tuple(toks)


def date_range(d: str) -> tuple[date, date]:
    """'2024-05-13' -> (that day, that day); '2024-05' -> (May 1, May 31)."""
    d = str(d).strip()
    if len(d) == 7:
        y, m = int(d[:4]), int(d[5:7])
        return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    return date(y, m, dd), date(y, m, dd)


def date_gap(a: str, b: str) -> int:
    """Smallest number of days between two (possibly month-only) dates; 0 if they overlap."""
    (a0, a1), (b0, b1) = date_range(a), date_range(b)
    if a1 < b0:
        return (b0 - a1).days
    if b1 < a0:
        return (a0 - b1).days
    return 0


# ----------------------------------------------------------------------------- pair rule
def link_reason(a: dict, b: dict, sim: float, cfg: LinkConfig = LinkConfig()) -> str:
    """Return 'link' if the two mentions should be linked, otherwise the first rule that failed."""
    if date_gap(a["date"], b["date"]) > cfg.window_days:
        return "date"
    if is_case_study(a.get("title")) or is_case_study(b.get("title")):
        return "case_study"
    oa, ob = norm_org(a.get("organization")), norm_org(b.get("organization"))
    if oa and ob and not (oa & ob):
        return "org"
    ma = norm_model(a.get("model_agent"), a.get("organization"))
    mb = norm_model(b.get("model_agent"), b.get("organization"))
    if ma and mb:
        if ma != mb:
            return "model"
        # a post about a model's release names the model in its title; same-day posts that do not (customer
        # stories, safety research, other products) are different events
        if not (names_model(a.get("title"), ma) and names_model(b.get("title"), mb)):
            return "title"
        return "link" if sim >= cfg.sim_min else "text"
    if not (oa and ob):
        return "org_missing"
    return "link" if sim >= cfg.sim_missing else "text"


# ----------------------------------------------------------------------------- grouping
def link(df: pd.DataFrame, cfg: LinkConfig = LinkConfig()) -> pd.DataFrame:
    """Add an `event_group` column (int). Mentions in one group describe the same event."""
    recs = df.to_dict("records")
    n = len(recs)
    if n == 0:
        return df.assign(event_group=pd.Series(dtype=int))
    X = TfidfEmbedder().fit_transform([event_text(r) for r in recs])
    S = similarity_matrix(X)
    cand = []
    for i in range(n):
        for j in range(i + 1, n):
            if link_reason(recs[i], recs[j], float(S[i, j]), cfg) == "link":
                cand.append((float(S[i, j]) - 0.01 * date_gap(recs[i]["date"], recs[j]["date"]), i, j))
    parent = list(range(n))
    members = {i: [i] for i in range(n)}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for _, i, j in sorted(cand, reverse=True):          # strongest links first
        ri, rj = find(i), find(j)
        if ri == rj:
            continue
        merged = members[ri] + members[rj]
        starts = [date_range(recs[k]["date"])[0] for k in merged]
        # month-only dates are wide by nature; judge the span on their first day
        span = (max(starts) - min(starts)).days
        if span > cfg.max_span_days:
            continue
        parent[rj] = ri
        members[ri] = merged
        del members[rj]
    roots = {r: g for g, r in enumerate(sorted({find(i) for i in range(n)}))}
    return df.assign(event_group=[roots[find(i)] for i in range(n)])


# ----------------------------------------------------------------------------- merging a group
_FIELDS = ["trigger", "organization", "model_agent", "capability", "action", "interaction", "impact", "source"]


def merge_groups(df: pd.DataFrame, category_order: list[str] | None = None) -> pd.DataFrame:
    """One row per event_group. Rules: earliest day-precise date; majority category (ties go to the category
    listed first in `category_order`, i.e. taxonomy precedence); text fields from the most confident mention;
    autonomy = median; confidence = lowest of the group if the mentions disagree on category, else highest;
    source_doc_ids = union."""
    order = {c: i for i, c in enumerate(category_order or [])}
    rows = []
    for g, grp in df.groupby("event_group", sort=True):
        grp = grp.assign(_conf=pd.to_numeric(grp["confidence"], errors="coerce").fillna(2))
        grp = grp.sort_values("_conf", ascending=False)
        cats = Counter(grp["category"])
        top = max(cats.values())
        category = sorted([c for c, v in cats.items() if v == top], key=lambda c: order.get(c, 99))[0]
        precise = [d for d in grp["date"] if len(str(d)) == 10]
        date_ = min(precise) if precise else min(grp["date"])
        row = {"event_group": g, "date": date_, "category": category, "n_mentions": len(grp)}
        for f in _FIELDS:
            vals = [str(v) for v in grp[f] if str(v).strip() not in ("", "nan", "None")] if f in grp else []
            row[f] = (max(vals, key=len) if f == "impact" else vals[0]) if vals else ""
        aut = pd.to_numeric(grp["autonomy_level"], errors="coerce").dropna()
        row["autonomy_level"] = "NA" if aut.empty else int(round(float(aut.median())))
        ids = []
        for v in grp["source_doc_ids"]:
            ids += [i for i in (v if isinstance(v, list) else str(v).split(";")) if i]
        row["source_doc_ids"] = ";".join(sorted(set(ids)))
        row["event_id"] = make_event_id(*sorted(set(ids))) if ids else f"ev_group_{g}"
        row["confidence"] = int(grp["_conf"].min() if len(cats) > 1 else grp["_conf"].max())
        row["category_disagreement"] = "Y" if len(cats) > 1 else ""
        rows.append(row)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- evaluation
def pairwise_prf(pred_groups, gold_groups) -> dict:
    """Precision/recall/F1 over mention pairs: a pair is positive if both mentions share a group."""
    p, g = np.asarray(pred_groups), np.asarray(gold_groups)
    iu = np.triu_indices(len(p), k=1)
    pp, gg = (p[:, None] == p[None, :])[iu], (g[:, None] == g[None, :])[iu]
    tp, fp, fn = int((pp & gg).sum()), int((pp & ~gg).sum()), int((~pp & gg).sum())
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3), "tp": tp, "fp": fp, "fn": fn}