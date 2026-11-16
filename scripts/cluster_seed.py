"""Cluster the seed timeline events (owner: TS, Day 8 prototype).

Input : data/seed/seed_timeline.csv
Output: results/tables/seed_clusters_<embedder>.csv  (one row per event with its cluster id)
        and a printed threshold sweep + most similar pairs.
Run   : PYTHONPATH=src python scripts/cluster_seed.py [--embedder tfidf|sbert] [--threshold 0.7]
"""
import argparse
from pathlib import Path

import pandas as pd

from ainevo.normalization.embed import cluster, event_text, get_embedder, nearest_pairs, sweep

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embedder", default="tfidf", choices=["tfidf", "sbert"])
    ap.add_argument("--threshold", type=float, default=0.7, help="cosine-distance cut for the saved clusters")
    a = ap.parse_args()

    df = pd.read_csv(ROOT / "data" / "seed" / "seed_timeline.csv", keep_default_na=False)
    texts = [event_text(r) for r in df.to_dict("records")]
    X = get_embedder(a.embedder).fit_transform(texts)
    print(f"{len(df)} events embedded with {a.embedder}: matrix {X.shape}\n")

    truths = {"category": df["category"].tolist(), "organization": df["organization"].tolist()}
    print("threshold sweep (distance cut; purity = how well clusters match the column):")
    print(sweep(X, truths).to_string(index=False), "\n")

    print("most similar pairs:")
    for i, j, s in nearest_pairs(X, 12):
        print(f"  {s:.2f}  {df.model_agent[i]} ({df.date[i]})  <->  {df.model_agent[j]} ({df.date[j]})")

    df["cluster"] = cluster(X, a.threshold)
    out = ROOT / "results" / "tables" / f"seed_clusters_{a.embedder}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df[["cluster", "event_id", "date", "organization", "model_agent", "category"]].sort_values(
        ["cluster", "date"]).to_csv(out, index=False, encoding="utf-8")
    print(f"\nsaved {df.cluster.nunique()} clusters at threshold {a.threshold} -> {out}")


if __name__ == "__main__":
    main()
