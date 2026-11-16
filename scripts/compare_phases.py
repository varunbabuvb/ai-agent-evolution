"""Day 17: compare detected change points with a phase-start reference table (owner: TS).
Run: python scripts/compare_phases.py [--reference data/reference/phase_starts.csv] [--tol 3] [--k 3]
Without --reference a DRAFT is built from gold phase_hint and saved to data/reference/phase_starts_draft.csv.
Output: results/tables/phase_comparison.csv
"""
import argparse
from pathlib import Path

import pandas as pd

from ainevo.analysis.phases import compare, compare_windows, draft_phase_starts, load_manual, load_reference

ROOT = Path(__file__).resolve().parents[1]
TAGS = ["gold", "gold_shares", "combined", "combined_shares"]


def breaks_for(tab: Path, tag: str) -> list[str]:
    p = tab / f"changepoints_{tag}.csv"
    if not p.exists():
        print(f"WARNING: {p.name} not found; run scripts/run_changepoints.py for tag '{tag}' first")
        return []
    seg = pd.read_csv(p)
    return seg["start"].iloc[1:].astype(str).tolist()  # each segment after the first starts at a break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", default=None)
    ap.add_argument("--manual", default=str(ROOT / "data" / "reference" / "phase_transitions_manual.csv"),
                    help="manual transitions with landmark windows (HA); used when the file exists")
    ap.add_argument("--gold", default=str(ROOT / "data" / "annotations" / "gold_events_v1.csv"))
    ap.add_argument("--tol", type=int, default=3)
    ap.add_argument("--k", type=int, default=3)
    a = ap.parse_args()
    tab = ROOT / "results" / "tables"
    if Path(a.manual).exists() and not a.reference:
        man = load_manual(a.manual)
        series_start = str(pd.read_csv(tab / "features_monthly_gold.csv")["month"].iloc[0])
        frames = []
        print(f"phase transitions: manual list {Path(a.manual).name}; match = break within +/-{a.tol} months of the landmark window")
        for tag in TAGS:
            br = breaks_for(tab, tag)
            c = compare_windows(br, man, series_start, a.tol)
            c.insert(0, "variant", tag)
            frames.append(c)
            print(f"\nbreaks [{tag}]: {br or 'none'}")
            print(c[["phase", "window", "sustained_from", "confidence", "nearest_break", "gap_to_window", "gap_to_sustained", "verdict"]].to_string(index=False))
        pd.concat(frames).to_csv(tab / "phase_comparison_manual.csv", index=False, encoding="utf-8")
        print("\nsaved results/tables/phase_comparison_manual.csv (gap < 0: break before the window; > 0: after)")
        return
    if a.reference:
        ref = load_reference(a.reference)
        label = "reference"
    else:
        ref = draft_phase_starts(pd.read_csv(a.gold, keep_default_na=False), a.k)
        out = ROOT / "data" / "reference"
        out.mkdir(parents=True, exist_ok=True)
        ref.to_csv(out / "phase_starts_draft.csv", index=False, encoding="utf-8")
        label = "DRAFT from gold phase_hint (pending approval)"
    print(f"phase starts: {label}")
    print(ref.to_string(index=False))

    series_start = str(pd.read_csv(tab / "features_monthly_gold.csv")["month"].iloc[0])
    frames = []
    for tag in TAGS:
        br = breaks_for(tab, tag)
        c = compare(br, ref, series_start, a.tol)
        c.insert(0, "variant", tag)
        frames.append(c)
        print(f"\nbreaks [{tag}]: {br or 'none'}")
        print(c[["phase", "start_month", "nearest_break", "offset_months", "verdict"]].to_string(index=False))
    pd.concat(frames).to_csv(tab / "phase_comparison.csv", index=False, encoding="utf-8")
    print(f"\nseries starts {series_start}; tolerance +/-{a.tol} months; saved results/tables/phase_comparison.csv")


if __name__ == "__main__":
    main()
