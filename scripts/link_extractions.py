"""Day 10: link cross-article events on the extracted events and build the features (owner: TS).
Input : data/processed/extractions_final.csv (Harsha's final run).  Run: python scripts/link_extractions.py [csv] [--threshold 0.5]
Output: results/tables/extracted_link_groups.csv      every group with 2+ documents
        results/tables/extracted_link_review100.csv   100 random linked PAIRS for Harshita's review
        data/processed/events_linked.csv              one row per linked event
        results/tables/features_monthly_extracted.csv / counts_quarterly_extracted.csv
"""
import argparse
import itertools
import random
import time
from pathlib import Path

import pandas as pd

from ainevo.analysis.timeline import build_timeline, from_extractions
from ainevo.features.monthly import monthly_features, quarterly_counts
from ainevo.normalization.link_events import link, merge_groups
from ainevo.schema import load_taxonomy

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default=str(ROOT / "data" / "processed" / "extractions_final.csv"))
    ap.add_argument("--threshold", type=float, default=0.5)
    a = ap.parse_args()
    ex = pd.read_csv(a.csv, keep_default_na=False)
    ev = build_timeline(from_extractions(ex, a.threshold))
    print(f"{len(ex)} documents -> {len(ev)} predicted events (p_event >= {a.threshold}, up to 2026-09)")
    t0 = time.time()
    g = link(ev)
    sizes = g.groupby("event_group").size()
    multi = sizes[sizes > 1]
    print(f"linking took {time.time() - t0:.0f}s: {g.event_group.nunique()} groups; {len(multi)} groups with 2+ docs "
          f"({int(multi.sum())} docs); largest group {int(sizes.max())}")
    tab = ROOT / "results" / "tables"
    tab.mkdir(parents=True, exist_ok=True)
    cols = ["event_group", "doc_id", "date", "source", "organization", "model_agent", "category", "title"]
    g[g.event_group.isin(multi.index)].sort_values(["event_group", "date"])[cols].to_csv(
        tab / "extracted_link_groups.csv", index=False, encoding="utf-8")
    rng = random.Random(42)
    pairs = []
    for gid in multi.index:
        rows = g[g.event_group == gid].to_dict("records")
        pairs += [(gid, x, y) for x, y in itertools.combinations(rows, 2)]
    pairs = rng.sample(pairs, min(100, len(pairs)))
    pd.DataFrame([{"event_group": gid, "doc_a": x["doc_id"], "title_a": x["title"], "date_a": x["date"],
                   "doc_b": y["doc_id"], "title_b": y["title"], "date_b": y["date"], "organization": x["organization"],
                   "model_agent_a": x["model_agent"], "model_agent_b": y["model_agent"], "same_event? (Y/N)": ""}
                  for gid, x, y in pairs]).to_csv(tab / "extracted_link_review100.csv", index=False, encoding="utf-8")
    tax = load_taxonomy()
    m = merge_groups(g, tax["category_precedence"])
    m.to_csv(ROOT / "data" / "processed" / "events_linked.csv", index=False, encoding="utf-8")
    m = build_timeline(m.assign(date=m["date"]))
    mf = monthly_features(m, "2022-01", "2026-09")
    mf.to_csv(tab / "features_monthly_extracted.csv", index=False, encoding="utf-8")
    quarterly_counts(m).to_csv(tab / "counts_quarterly_extracted.csv", index=False, encoding="utf-8")
    print(f"merged events: {len(m)}; labelled months (>=3 events): {(mf.dominant_category != '').sum()} of {len(mf)}")
    print(f"review sample: {len(pairs)} pairs -> results/tables/extracted_link_review100.csv")


if __name__ == "__main__":
    main()
