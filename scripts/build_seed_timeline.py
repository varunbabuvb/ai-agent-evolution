"""Build data/seed/seed_timeline.csv from Epoch AI + AI Index 2026 (owner: TS).

Input : data/raw/seed/notable_ai_models.csv   (download from https://epoch.ai/data/notable-ai-models; git-ignored)
Output: data/seed/seed_timeline.csv
Run   : PYTHONPATH=src python scripts/build_seed_timeline.py [path/to/notable_ai_models.csv]
"""
import sys
from pathlib import Path

import pandas as pd

from ainevo.collection.seed_timelines import build_seed
from ainevo.schema import load_taxonomy

ROOT = Path(__file__).resolve().parents[1]


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "raw" / "seed" / "notable_ai_models.csv"
    if not src.exists():
        raise SystemExit(f"Epoch file not found: {src}\nDownload notable_ai_models.csv from "
                         "https://epoch.ai/data/notable-ai-models and put it there (or pass the path).")
    df = pd.read_csv(src)
    tax = load_taxonomy(ROOT / "configs" / "taxonomy.yaml")
    out, missing, problems = build_seed(df, tax)
    dest = ROOT / "data" / "seed" / "seed_timeline.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(dest, index=False, encoding="utf-8")
    print(f"wrote {len(out)} events -> {dest}")
    print("per year:", out["date"].str[:4].value_counts().sort_index().to_dict())
    print("per category:", out["category"].value_counts().to_dict())
    print("needs review:", int((out["needs_review"] == "Y").sum()))
    if missing:
        print("NOT FOUND in Epoch file (rename or drop in SEED_MODELS):", missing)
    if problems:
        print("validation notes:\n  " + "\n  ".join(problems))


if __name__ == "__main__":
    main()
