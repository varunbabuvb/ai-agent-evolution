"""Run the linking rules on the gold events (owner: TS, Day 10).
Input : gold_events_v1.csv (path argument). Output: results/tables/gold_link_groups.csv + printed summary.
Run   : $env:PYTHONPATH="src"; python scripts/link_gold.py path/to/gold_events_v1.csv
Gold has one event per document, so any group of 2+ is a candidate duplicate to REVIEW, not a known error.
"""
import sys
from pathlib import Path

import pandas as pd

from ainevo.analysis.timeline import from_gold
from ainevo.normalization.link_events import link, norm_model

ROOT = Path(__file__).resolve().parents[1]


def main():
    df = from_gold(pd.read_csv(sys.argv[1], keep_default_na=False))
    g = link(df)
    sizes = g.groupby("event_group").size()
    multi = sizes[sizes > 1].index
    print(f"{len(df)} events -> {g.event_group.nunique()} groups; groups with 2+ mentions: {len(multi)}")
    named = int((df.model_agent.map(lambda x: len(norm_model(x))) > 0).sum())
    print(f"events with a usable model name: {named}/{len(df)}; with an organisation: {(df.organization != '').sum()}/{len(df)}")
    cols = ["event_group", "event_id", "doc_id", "annotator", "date", "organization", "model_agent", "category", "title"]
    out = g[g.event_group.isin(multi)].sort_values(["event_group", "date"])[cols]
    path = ROOT / "results" / "tables" / "gold_link_groups.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, encoding="utf-8")
    print(out.to_string(index=False) if len(out) else "no candidate duplicates")
    print("saved", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
