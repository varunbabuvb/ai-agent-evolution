"""Inter-annotator agreement for the pilot.

Usage (from repo root, with src on PYTHONPATH):
    python -m ainevo.evaluation.agreement data/annotations/pilot_VV.csv data/annotations/pilot_SH.csv ...
Each CSV needs columns: doc_id, has_event, category, autonomy_level (one row per pilot document).
Export the 'Pilot' sheet of each member's workbook to CSV first.
"""
from __future__ import annotations
import itertools, sys
from collections import Counter
import pandas as pd


def cohen_kappa(a, b) -> float:
    a, b = list(a), list(b)
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("need two equal-length, non-empty label lists")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def fleiss_kappa(ratings: list[list]) -> float:
    """ratings[i] = labels given to item i by all raters (same number of raters per item)."""
    n_items, n_raters = len(ratings), len(ratings[0])
    cats = sorted({x for row in ratings for x in row}, key=str)
    counts = [[row.count(c) for c in cats] for row in ratings]
    p_i = [(sum(c * c for c in row) - n_raters) / (n_raters * (n_raters - 1)) for row in counts]
    p_j = [sum(row[j] for row in counts) / (n_items * n_raters) for j in range(len(cats))]
    p_bar, pe = sum(p_i) / n_items, sum(p * p for p in p_j)
    return 1.0 if pe == 1 else (p_bar - pe) / (1 - pe)


def band(k: float) -> str:
    return "good" if k >= 0.70 else "acceptable" if k >= 0.60 else "REWRITE RULE"


def compare(frames: dict[str, pd.DataFrame], fields=("has_event", "category", "autonomy_level")) -> pd.DataFrame:
    names = list(frames)
    docs = sorted(set.intersection(*(set(f["doc_id"]) for f in frames.values())))
    rows = []
    for fld in fields:
        wide = pd.DataFrame({n: frames[n].set_index("doc_id").loc[docs, fld].fillna("(blank)").astype(str) for n in names})
        rows.append({"field": fld, "pair": "ALL (Fleiss)", "kappa": fleiss_kappa(wide.values.tolist()), "n": len(docs)})
        for x, y in itertools.combinations(names, 2):
            rows.append({"field": fld, "pair": f"{x}-{y}", "kappa": cohen_kappa(wide[x], wide[y]), "n": len(docs)})
    out = pd.DataFrame(rows)
    out["verdict"] = out["kappa"].map(band)
    return out


def disagreements(frames: dict[str, pd.DataFrame], field: str = "category") -> pd.DataFrame:
    wide = pd.DataFrame({n: f.set_index("doc_id")[field].fillna("(blank)").astype(str) for n, f in frames.items()})
    return wide[wide.nunique(axis=1) > 1]


if __name__ == "__main__":
    paths = sys.argv[1:]
    frames = {p.split("pilot_")[-1].replace(".csv", ""): pd.read_csv(p) for p in paths}
    print(compare(frames).round(3).to_string(index=False))
    print("\nDisagreements on category:\n", disagreements(frames).to_string())
