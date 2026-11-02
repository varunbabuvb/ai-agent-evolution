"""Cleaning + exact/near-duplicate removal.
Run from repo root:  PYTHONPATH=src python -m ainevo.preprocessing.clean_dedup [--inp ..] [--out ..] [--report ..]
The data cutoff is read from configs/split.yaml (cutoff_month); falls back to 2026-09-30.
Documents are never silently rewritten beyond cleaning; two advisory flags are added to metadata
(low_signal_release, llm_terms_found) so later steps can filter without losing the original document.
Documents already given to annotators (data/annotations/pool_v0.json) are never dropped as short or duplicate."""
import argparse, calendar, collections, hashlib, json, re
from datetime import date, datetime
from pathlib import Path
import yaml
from datasketch import MinHash, MinHashLSH
from ainevo.preprocessing.build_corpus import protected_ids

START = date(2017, 1, 1)
MIN_CHARS = 100
JACCARD = 0.85

# Each pattern removes only the sentence/line fragment it matches - never the rest of the document
# (the old `.*` patterns ran to the end of the text because whitespace had already been collapsed).
BOILERPLATE = [
    r"subscribe to (?:our )?newsletter[^.!?\n]*[.!?]?",
    r"all rights reserved[^.!?\n]*[.!?]?",
    r"read more\s*(?:»|>)?",
    r"share (?:this )?(?:post|article)[^.!?\n]*[.!?]?",
    r"click here to [^.!?\n]*[.!?]?",
    r"sign up for [^.!?\n]*[.!?]?",
    r"cookies? (?:policy|settings)[^.!?\n]*[.!?]?",
]
BP = re.compile("|".join(BOILERPLATE), re.I)
BUMP = re.compile(r"\b(bump|dependabot|update dependenc\w*|deps?:|chore|ci:|typo|lockfile|pre-commit|release-please)\b", re.I)
LLM = re.compile(r"\bLLMs?\b|language model|GPT|agentic|foundation model|tool[- ]use|function call|Claude|Gemini|\bMCP\b|copilot|chatbot|transformer", re.I)


def load_cutoff(path="configs/split.yaml") -> date:
    try:
        m = str(yaml.safe_load(open(path, encoding="utf-8"))["cutoff_month"])
        y, mo = map(int, m.split("-"))
        return date(y, mo, calendar.monthrange(y, mo)[1])
    except Exception:
        return date(2026, 9, 30)


def clean_text(t: str) -> str:
    t = re.sub(r"<[^>]+>", " ", t)          # leftover HTML tags
    t = re.sub(r"https?://\S+", " ", t)     # raw URLs
    t = BP.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def parse_date(s):
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def minhash(text, n=5):
    words = text.lower().split()
    m = MinHash(num_perm=128)
    for i in range(max(1, len(words) - n + 1)):
        m.update(" ".join(words[i:i + n]).encode("utf-8"))
    return m


def low_signal_release(d) -> bool:
    return d["source_type"] == "release_notes" and (len(d["text"]) < 150 or (bool(BUMP.search(d["text"])) and len(d["text"]) < 400))


def process(rows, cutoff: date, protected=frozenset()):
    stats, docs = collections.Counter(), []
    for d in rows:
        stats["input"] += 1
        dt = parse_date(d.get("publication_date", ""))
        if dt is None:
            stats["dropped_bad_date"] += 1; continue
        if dt < START or dt > cutoff:
            stats["dropped_out_of_range"] += 1; continue
        d["publication_date"] = dt.isoformat()
        d["text"] = clean_text(d["text"])
        d["title"] = re.sub(r"\s+", " ", d["title"]).strip()
        if len(d["text"]) < MIN_CHARS and d.get("doc_id") not in protected:
            stats["dropped_too_short"] += 1; continue
        docs.append(d)
    seen, unique = set(), []
    for d in docs:
        h = hashlib.md5(d["text"].lower().encode("utf-8")).hexdigest()
        if h in seen and d.get("doc_id") not in protected:
            stats["dropped_exact_dup"] += 1; continue
        seen.add(h); unique.append(d)
    lsh, final = MinHashLSH(threshold=JACCARD, num_perm=128), []
    for i, d in enumerate(sorted(unique, key=lambda x: x["publication_date"])):   # earliest copy is kept
        m = minhash(d["text"])
        if lsh.query(m) and d.get("doc_id") not in protected:
            stats["dropped_near_dup"] += 1; continue
        lsh.insert(str(i), m)
        d.setdefault("metadata", {})
        d["metadata"]["low_signal_release"] = low_signal_release(d)
        d["metadata"]["llm_terms_found"] = bool(LLM.search(d["title"] + " " + d["text"]))
        stats["flag_low_signal_release"] += d["metadata"]["low_signal_release"]
        stats["flag_no_llm_terms"] += not d["metadata"]["llm_terms_found"]
        final.append(d)
    stats["output"] = len(final)
    return final, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", default="data/interim/corpus_v1.jsonl")
    ap.add_argument("--out", default="data/interim/corpus_v1_clean.jsonl")
    ap.add_argument("--report", default="data/interim/cleaning_report.json")
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.inp, encoding="utf-8")]
    final, stats = process(rows, load_cutoff(), protected_ids())
    with open(a.out, "w", encoding="utf-8") as f:
        for d in final:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    report = {"cutoff": load_cutoff().isoformat(), "stats": dict(stats),
              "by_year": dict(sorted(collections.Counter(d["publication_date"][:4] for d in final).items())),
              "by_source_type": dict(collections.Counter(d["source_type"] for d in final))}
    Path(a.report).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()