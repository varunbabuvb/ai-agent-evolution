"""Day 17: phase start months and a comparison with the detected change points (owner: TS).

A reference table has one row per phase: phase, start_month (YYYY-MM).  Until the team agrees a manual list, a DRAFT is
derived from the gold phase_hint labels: the start of phase p is the month of its k-th earliest event (k=3 by default, so
one early outlier does not set the start).  phase_hint says which phase an event's content looks like, not when the
period was, so the draft shows when each kind of content first appears; it is not an authoritative phase calendar.
"""
from __future__ import annotations

import pandas as pd


def month_index(m: str) -> int:
    y, mo = str(m)[:7].split("-")
    return int(y) * 12 + int(mo) - 1


def month_diff(a: str, b: str) -> int:
    """a - b in months."""
    return month_index(a) - month_index(b)


def draft_phase_starts(gold: pd.DataFrame, k: int = 3) -> pd.DataFrame:
    """Draft start month per phase 1-7 from gold phase_hint; start = month of the k-th earliest event."""
    g = gold.copy()
    g["m"] = g["date"].astype(str).str[:7]
    g["phase"] = pd.to_numeric(g["phase_hint"], errors="coerce")
    g = g[g["phase"].between(1, 7) & g["m"].str.match(r"^\d{4}-\d{2}$")]
    rows = []
    for p in range(1, 8):
        ms = sorted(g.loc[g["phase"] == p, "m"])
        rows.append({
            "phase": p, "n_events": len(ms),
            "first_month": ms[0] if ms else "",
            "start_month": ms[min(k, len(ms)) - 1] if ms else "",
            "median_month": ms[len(ms) // 2] if ms else "",
            "status": "draft from gold phase_hint (pending approval)",
        })
    return pd.DataFrame(rows)


def load_reference(path) -> pd.DataFrame:
    ref = pd.read_csv(path, dtype=str)
    missing = {"phase", "start_month"} - set(ref.columns)
    if missing:
        raise ValueError(f"reference table needs columns phase, start_month; missing {sorted(missing)}")
    ref["phase"] = ref["phase"].astype(int)
    ref["start_month"] = ref["start_month"].fillna("").astype(str).str[:7]
    return ref


def compare(breaks: list[str], ref: pd.DataFrame, series_start: str, tol: int = 3) -> pd.DataFrame:
    """One row per phase: its start, the nearest detected break, the offset in months (break - phase start), and a verdict.

    Phases starting before the first month of the series cannot be matched by any break (no data before it), so they are
    reported as 'before series'.
    """
    rows = []
    for _, r in ref.sort_values("phase").iterrows():
        s = r["start_month"]
        if not s:
            rows.append({"phase": r["phase"], "start_month": "", "nearest_break": "", "offset_months": None, "verdict": "no start"})
            continue
        if month_diff(s, series_start) < 0:
            rows.append({"phase": r["phase"], "start_month": s, "nearest_break": "", "offset_months": None, "verdict": "before series"})
            continue
        if not breaks:
            rows.append({"phase": r["phase"], "start_month": s, "nearest_break": "", "offset_months": None, "verdict": "no break"})
            continue
        b = min(breaks, key=lambda x: abs(month_diff(x, s)))
        off = month_diff(b, s)
        rows.append({"phase": r["phase"], "start_month": s, "nearest_break": b, "offset_months": off,
                     "verdict": f"within +/-{tol}" if abs(off) <= tol else "no match"})
    return pd.DataFrame(rows)


# ---- manual list with windows (phase_transitions_manual.csv, written by HA) ----
def _quarter_start(q: str) -> str:
    """'2023-Q3' -> '2023-07'; anything else (for example 'none (...)') -> ''."""
    import re
    m = re.match(r"^(\d{4})-Q([1-4])$", str(q).strip())
    return f"{m.group(1)}-{(int(m.group(2)) - 1) * 3 + 1:02d}" if m else ""


def load_manual(path) -> pd.DataFrame:
    """Read the manual transitions: one row per phase with a landmark window and the quarter it is sustained from."""
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    need = {"phase", "landmark_window_start", "landmark_window_end", "sustained_from_quarter"}
    if need - set(d.columns):
        raise ValueError(f"manual table is missing columns {sorted(need - set(d.columns))}")
    out = pd.DataFrame({
        "phase": d["phase"].astype(int),
        "window_start": d["landmark_window_start"].str[:7],
        "window_end": d["landmark_window_end"].str[:7],
        "sustained_from": d["sustained_from_quarter"].map(_quarter_start),
        "confidence": d.get("confidence", ""),
    })
    return out


def compare_windows(breaks: list[str], man: pd.DataFrame, series_start: str, tol: int = 3) -> pd.DataFrame:
    """Per phase: distance from the nearest break to the landmark window (0 = inside it) and to the sustained-from month.

    A break matches the landmark when it lies within tol months of the window.
    """
    rows = []
    for _, r in man.sort_values("phase").iterrows():
        base = {"phase": r["phase"], "window": f"{r['window_start']}..{r['window_end']}",
                "sustained_from": r["sustained_from"], "confidence": r["confidence"]}
        if not breaks:
            rows.append({**base, "nearest_break": "", "gap_to_window": None, "gap_to_sustained": None, "verdict": "no break"})
            continue

        def gap(b):
            lo, hi = month_diff(b, r["window_start"]), month_diff(b, r["window_end"])
            return 0 if lo >= 0 and hi <= 0 else (lo if lo < 0 else hi)   # <0: break before window, >0: after

        b = min(breaks, key=lambda x: abs(gap(x)))
        g = gap(b)
        gs = month_diff(b, r["sustained_from"]) if r["sustained_from"] else None
        rows.append({**base, "nearest_break": b, "gap_to_window": g, "gap_to_sustained": gs,
                     "verdict": f"within +/-{tol}" if abs(g) <= tol else "no match"})
    return pd.DataFrame(rows)
