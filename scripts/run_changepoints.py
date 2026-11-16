"""Day 16: change-point detection (PELT) on the monthly features + quarterly view 2017-2021 (owner: TS).
Run: python scripts/run_changepoints.py [--features results/tables/features_monthly_gold.csv] [--tag gold] [--beta 1.0] [--min-size 4]
Output: results/tables/changepoints_<tag>.csv (segments), changepoint_stability_<tag>.csv, quarterly_view_<tag>.csv
"""
import argparse
from pathlib import Path

import pandas as pd

from ainevo.analysis.changepoints import DEFAULT_COLS, SHARE_COLS, default_penalty, pelt, prepare, prepare_shares, segments, stability

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=str(ROOT / "results" / "tables" / "features_monthly_gold.csv"))
    ap.add_argument("--tag", default="gold")
    ap.add_argument("--beta", type=float, default=1.0)
    ap.add_argument("--min-size", type=int, default=4)
    ap.add_argument("--shares-only", action="store_true",
                    help="volume-free: use only shares/averages, months with <3 events are treated as missing")
    a = ap.parse_args()
    tab = ROOT / "results" / "tables"
    mf = pd.read_csv(a.features, keep_default_na=False, na_values=[""])
    months = mf["month"].tolist()
    X = prepare_shares(mf) if a.shares_only else prepare(mf, DEFAULT_COLS)
    if a.shares_only:
        a.tag += "_shares"
    pen = default_penalty(len(X), X.shape[1], a.beta)
    cps = pelt(X, pen, a.min_size)
    seg = segments(months, cps)
    # describe each segment with the raw means
    raw = mf[DEFAULT_COLS].apply(pd.to_numeric, errors="coerce")
    for c in ["n_events", "entropy", "multi_agent_share", "incident_share", "mean_autonomy"]:
        seg[f"mean_{c}" if c != "mean_autonomy" else "mean_autonomy"] = [
            round(raw[c].iloc[months.index(s):months.index(e) + 1].mean(), 3) for s, e in zip(seg.start, seg.end)]
    seg.to_csv(tab / f"changepoints_{a.tag}.csv", index=False, encoding="utf-8")
    print(f"series: {len(X)} months, {X.shape[1]} variables; penalty {pen:.2f} (beta {a.beta}), min segment {a.min_size} months")
    print(f"{len(cps)} change points -> {len(seg)} segments")
    print(seg.to_string(index=False))
    st = stability(X, months)
    st.to_csv(tab / f"changepoint_stability_{a.tag}.csv", index=False, encoding="utf-8")
    print("\nstability (share of 12 runs - 4 penalties x 3 minimum sizes - with a break within +/-1 month):")
    print(st.head(10).to_string(index=False))

    # quarterly view 2017-2021: seed timeline (Epoch / AI Index) next to the gold events
    q = pd.read_csv(tab / f"counts_quarterly_{a.tag.replace('_shares', '')}.csv")[["quarter", "n_events"]].rename(columns={"n_events": "gold_events"})
    seed_path = ROOT / "results" / "tables" / "counts_quarterly.csv"
    if seed_path.exists():
        s = pd.read_csv(seed_path)[["quarter", "n_events"]].rename(columns={"n_events": "seed_events"})
        q = q.merge(s, on="quarter", how="outer").fillna(0)
        q["year"] = q["quarter"].str[:4]
        q.to_csv(tab / f"quarterly_view_{a.tag.replace('_shares', '')}.csv", index=False, encoding="utf-8")
        print("\nquarterly view 2017-2021 (events per year):")
        print(q.groupby("year")[["seed_events", "gold_events"]].sum().astype(int).to_string())


if __name__ == "__main__":
    main()