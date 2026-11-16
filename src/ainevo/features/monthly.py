"""Monthly and quarterly features from the timeline (owner: TS, plan T7 / Days 12-13).

Monthly (2022-01 .. cutoff), one row per month INCLUDING months with no events (zeros):
  n_events, n_categories, entropy (Shannon over categories, normalised to 0..1), multi_agent_share,
  incident_share, mean_autonomy (NaN if none), high_autonomy_share (autonomy >= 3), n_orgs,
  novelty (share of the month's events whose organisation was never seen in an EARLIER month),
  dominant_category (most events; ties -> taxonomy precedence; '' if fewer than `min_events`).
Causality: every value for month t uses only events dated in month t, except `novelty`, which also uses
months < t. No value ever looks forward, so the table can be used for rolling-origin forecasting.
Quarterly (2017Q1 .. 2021Q4): category counts per quarter for the long, description-only view.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ainevo.normalization.link_events import norm_org
from ainevo.schema import load_taxonomy

MULTI_AGENT = "multi_agent_coordination"
INCIDENT = "unexpected_behavior_incident"


def _entropy(counts: list[int], k: int) -> float:
    tot = sum(counts)
    if tot == 0 or k < 2:
        return 0.0
    p = np.array([c for c in counts if c > 0], dtype=float) / tot
    return float(max(0.0, -(p * np.log(p)).sum() / np.log(k)))


def month_range(start: str, end: str) -> list[str]:
    return [p.strftime("%Y-%m") for p in pd.period_range(start, end, freq="M")]


def monthly_features(tl: pd.DataFrame, start: str = "2022-01", end: str = "2026-09",
                     min_events: int = 3, tax: dict | None = None) -> pd.DataFrame:
    tax = tax or load_taxonomy()
    order = {c: i for i, c in enumerate(tax["category_precedence"])}
    k = len(tax["categories"])
    seen_orgs: set[str] = set()
    # orgs seen before `start` still count as "already seen"
    for _, r in tl[tl["month"] < start].iterrows():
        seen_orgs |= set(norm_org(r.get("organization")))
    rows = []
    for m in month_range(start, end):
        g = tl[tl["month"] == m]
        n = len(g)
        counts = g["category"].value_counts()
        orgs = [norm_org(o) for o in g["organization"]] if n else []
        new = sum(1 for o in orgs if o and not (o & seen_orgs))
        with_org = sum(1 for o in orgs if o)
        for o in orgs:
            seen_orgs |= set(o)
        aut = g["autonomy"].dropna()
        top = ""
        if n >= min_events:
            top = sorted(counts.index, key=lambda c: (-counts[c], order.get(c, 99)))[0]
        rows.append({
            "month": m, "n_events": n, "n_categories": int(len(counts)),
            "entropy": round(_entropy(list(counts.values), k), 4),
            "multi_agent_share": round(counts.get(MULTI_AGENT, 0) / n, 4) if n else 0.0,
            "incident_share": round(counts.get(INCIDENT, 0) / n, 4) if n else 0.0,
            "mean_autonomy": round(float(aut.mean()), 3) if len(aut) else np.nan,
            "high_autonomy_share": round(float((aut >= 3).sum() / len(aut)), 4) if len(aut) else 0.0,
            "n_orgs": len({x for o in orgs for x in o}),
            "novelty": round(new / with_org, 4) if with_org else 0.0,
            "dominant_category": top,
        })
    return pd.DataFrame(rows)


def quarterly_counts(tl: pd.DataFrame, start: str = "2017-01", end: str = "2021-12",
                     tax: dict | None = None) -> pd.DataFrame:
    """Events per quarter and category for the 2017-2021 view (zero-filled)."""
    tax = tax or load_taxonomy()
    cats = [c["id"] for c in tax["categories"]]
    qs = [str(p) for p in pd.period_range(start, end, freq="Q")]
    sub = tl[(tl["month"] >= start) & (tl["month"] <= end)]
    tab = pd.crosstab(sub["quarter"], sub["category"]).reindex(index=qs, columns=cats, fill_value=0)
    tab.insert(0, "n_events", tab.sum(axis=1))
    tab.index.name = "quarter"
    return tab.reset_index()
