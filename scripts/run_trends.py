"""Day 15: rolling statistics on the monthly features + clustering of event embeddings (owner: TS).
Run: python scripts/run_trends.py [--features results/tables/features_monthly_gold.csv]
                                  [--events data/annotations/gold_events_v1.csv] [--threshold 0.8]
Output: results/tables/features_rolling_gold.csv, event_clusters_gold.csv, event_cluster_summary_gold.csv
"""
import argparse
from pathlib import Path

import pandas as pd

from ainevo.analysis.timeline import apply_merges, build_timeline, from_gold
from ainevo.analysis.trends import cluster_events, cluster_summary, rolling_features

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=str(ROOT / "results" / "tables" / "features_monthly_gold.csv"))
    ap.add_argument("--events", default=str(ROOT / "data" / "annotations" / "gold_events_v1.csv"))
    ap.add_argument("--threshold", type=float, default=0.8)
    a = ap.parse_args()
    tab = ROOT / "results" / "tables"
    mf = pd.read_csv(a.features, keep_default_na=False, na_values=[""])
    mf["dominant_category"] = mf["dominant_category"].fillna("")
    rf = rolling_features(mf)
    rf.to_csv(tab / "features_rolling_gold.csv", index=False, encoding="utf-8")
    print(f"rolling features: {rf.shape[0]} months x {rf.shape[1]} columns -> results/tables/features_rolling_gold.csv")
    print(rf[["month", "n_events", "n_events_ma3", "n_events_ma6", "entropy_ma3", "multi_agent_share_ma3",
              "mean_autonomy_ma3"]].tail(6).to_string(index=False))
    _g = from_gold(pd.read_csv(a.events, keep_default_na=False))
    _m = Path(a.events).resolve().parents[2] / "data" / "reference" / "gold_merges.csv"
    if _m.exists():
        _g = apply_merges(_g, pd.read_csv(_m, keep_default_na=False))
    ev = build_timeline(_g).reset_index(drop=True)    
    labels, X, emb = cluster_events(ev, a.threshold)
    ev["cluster"] = labels
    ev[["cluster", "event_id", "doc_id", "date", "organization", "model_agent", "category", "title"]].sort_values(
        ["cluster", "date"]).to_csv(tab / "event_clusters_gold.csv", index=False, encoding="utf-8")
    cs = cluster_summary(ev, labels, X, emb)
    cs.to_csv(tab / "event_cluster_summary_gold.csv", index=False, encoding="utf-8")
    sizes = cs["size"]
    print(f"\n{len(ev)} events -> {len(cs)} clusters at distance {a.threshold} (singletons {(sizes == 1).sum()}, largest {sizes.max()})")
    print(cs.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
