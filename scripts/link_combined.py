"""Link gold + provisional extracted events and build features (owner: TS, Day 10 follow-up).
Input : gold_events_v1.csv, extracted_events_provisional.csv (Harsha, threshold 0.8, gold docs excluded), the corpus (for titles)
Run   : python scripts/link_combined.py [--gold data/annotations/gold_events_v1.csv] [--extracted data/processed/extracted_events_provisional.csv]
        [--labelled results/tables/_review_labelled.csv]   (pairs Harshita already labelled are marked, so she reviews only new ones)
Output: results/tables/combined_link_groups.csv, combined_link_review.csv, data/processed/events_combined_linked.csv,
        results/tables/features_monthly_combined.csv, counts_quarterly_combined.csv
"""
import argparse
import itertools
import json
import random
from pathlib import Path

import pandas as pd

from ainevo.analysis.timeline import apply_merges, build_timeline, from_gold
from ainevo.features.monthly import monthly_features, quarterly_counts
from ainevo.normalization.link_events import link, merge_groups
from ainevo.schema import load_taxonomy

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=str(ROOT / "data" / "annotations" / "gold_events_v1.csv"))
    ap.add_argument("--extracted", default=str(ROOT / "data" / "processed" / "extracted_events_provisional.csv"))
    ap.add_argument("--corpus", default=str(ROOT / "data" / "interim" / "corpus_v1_clean.jsonl"))
    ap.add_argument("--labelled", default=str(ROOT / "results" / "tables" / "_review_labelled.csv"))
    a = ap.parse_args()
    titles = {}
    for line in open(a.corpus, encoding="utf-8"):
        d = json.loads(line)
        titles[d["doc_id"]] = d.get("title", "")
    gold = from_gold(pd.read_csv(a.gold, keep_default_na=False))
    mp = ROOT / "data" / "reference" / "gold_merges.csv"
    if mp.exists():
        gold = apply_merges(gold, pd.read_csv(mp, keep_default_na=False))
    gold["origin"] = "gold"
    ex = pd.read_csv(a.extracted, keep_default_na=False)
    ex["title"] = ex["doc_id"].map(titles).fillna("")
    ex["source_doc_ids"] = ex["doc_id"]
    ex["origin"] = "extracted"
    ex["confidence"] = 2
    for c in ("capability", "action", "interaction"):
        if c not in ex:
            ex[c] = ""
    cols = ["event_id", "doc_id", "date", "category", "organization", "model_agent", "capability", "action",
            "autonomy_level", "interaction", "source", "source_type", "title", "confidence", "source_doc_ids", "origin"]
    both = pd.concat([gold.reindex(columns=cols), ex.reindex(columns=cols)], ignore_index=True)
    both = build_timeline(both).reset_index(drop=True)
    print(f"gold {int((both.origin == 'gold').sum())} + extracted {int((both.origin == 'extracted').sum())} = {len(both)} events on the timeline")
    g = link(both)
    sizes = g.groupby("event_group").size()
    multi = sizes[sizes > 1]
    print(f"{g.event_group.nunique()} groups; {len(multi)} groups with 2+ documents ({int(multi.sum())} docs); largest {int(sizes.max())}")
    tab = ROOT / "results" / "tables"
    gcols = ["event_group", "doc_id", "origin", "date", "source", "organization", "model_agent", "category", "title"]
    g[g.event_group.isin(multi.index)].sort_values(["event_group", "date"])[gcols].to_csv(tab / "combined_link_groups.csv", index=False, encoding="utf-8")
    seen = {}
    lp = Path(a.labelled)
    if lp.exists():
        for r in pd.read_csv(lp, keep_default_na=False).itertuples():
            seen[tuple(sorted((r.doc_a, r.doc_b)))] = r.label
    pairs = []
    for gid in multi.index:
        rows = g[g.event_group == gid].to_dict("records")
        pairs += [(gid, x, y) for x, y in itertools.combinations(rows, 2)]
    random.Random(42).shuffle(pairs)
    out = [{"event_group": gid, "doc_a": x["doc_id"], "title_a": x["title"], "date_a": x["date"], "doc_b": y["doc_id"],
            "title_b": y["title"], "date_b": y["date"], "organization": x["organization"], "model_agent_a": x["model_agent"],
            "model_agent_b": y["model_agent"], "already_labelled": seen.get(tuple(sorted((x["doc_id"], y["doc_id"]))), ""),
            "same_event? (Y/N)": ""} for gid, x, y in pairs]
    pd.DataFrame(out).sort_values("already_labelled").to_csv(tab / "combined_link_review.csv", index=False, encoding="utf-8")
    new = sum(1 for o in out if not o["already_labelled"])
    print(f"review file: {len(out)} pairs, {new} not labelled before -> results/tables/combined_link_review.csv")
    m = merge_groups(g, load_taxonomy()["category_precedence"])
    m.to_csv(ROOT / "data" / "processed" / "events_combined_linked.csv", index=False, encoding="utf-8")
    mt = build_timeline(m)
    mf = monthly_features(mt, "2022-01", "2026-09")
    mf.to_csv(tab / "features_monthly_combined.csv", index=False, encoding="utf-8")
    quarterly_counts(mt).to_csv(tab / "counts_quarterly_combined.csv", index=False, encoding="utf-8")
    print(f"merged events {len(mt)}; labelled months (>=3 events): {(mf.dominant_category != '').sum()} of {len(mf)}")
    print(mf[["month", "n_events", "n_categories", "entropy", "multi_agent_share", "mean_autonomy", "novelty"]].tail(6).to_string(index=False))


if __name__ == "__main__":
    main()