"""Build timeline + monthly/quarterly features (owner: TS, Days 11-13).
Input : an events CSV (default data/seed/seed_timeline.csv; later the merged real events)
Output: data/processed/timeline.csv, results/tables/features_monthly.csv, results/tables/counts_quarterly.csv
Run   : PYTHONPATH=src python scripts/build_features.py [events.csv] [--cutoff 2026-09] [--gold --tag gold]
"""
import argparse
from pathlib import Path

import pandas as pd

from ainevo.analysis.timeline import apply_merges, build_timeline, from_gold
from ainevo.features.monthly import monthly_features, quarterly_counts

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("events", nargs="?", default=str(ROOT / "data" / "seed" / "seed_timeline.csv"))
    ap.add_argument("--cutoff", default="2026-09")
    ap.add_argument("--gold", action="store_true", help="input is gold_events_v1.csv (blank placeholder organisations)")
    ap.add_argument("--merges", default=str(ROOT / "data" / "reference" / "gold_merges.csv"),
                    help="gold events to merge (keep_annotation_id, drop_annotation_id); used with --gold when the file exists")
    ap.add_argument("--tag", default="", help="suffix for output names, e.g. gold -> features_monthly_gold.csv")
    a = ap.parse_args()
    df = pd.read_csv(a.events, keep_default_na=False)
    if a.gold:
        df = from_gold(df)
        if Path(a.merges).exists():
            m = pd.read_csv(a.merges, keep_default_na=False)
            n0 = len(df)
            df = apply_merges(df, m)
            print(f"merged {n0 - len(df)} gold event(s) using {Path(a.merges).name}")
    t = f"_{a.tag}" if a.tag else ""
    tl = build_timeline(df, a.cutoff)
    print(f"{len(df)} rows in, {len(tl)} on the timeline (cutoff {a.cutoff})")
    mf = monthly_features(tl, "2022-01", a.cutoff)
    qc = quarterly_counts(tl)
    for path, t in [(ROOT / "data" / "processed" / f"timeline{t}.csv", tl),
                    (ROOT / "results" / "tables" / f"features_monthly{t}.csv", mf),
                    (ROOT / "results" / "tables" / f"counts_quarterly{t}.csv", qc)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        t.to_csv(path, index=False, encoding="utf-8")
        print("saved", path.relative_to(ROOT))
    print(f"\nmonths: {len(mf)}, with >=3 events (labelled): {(mf.dominant_category != '').sum()}")
    print(qc.to_string(index=False))
    print("\nlast 6 months:\n", mf.tail(6).to_string(index=False))


if __name__ == "__main__":
    main()