"""Change-point detection on the monthly series (owner: TS, plan T8 / Day 16).

PELT (Killick et al. 2012) with a least-squares cost: a segment is scored by the sum of squared deviations of its
values from the segment mean, so a change point is a shift in the MEAN of the (standardised) series. Written in numpy
(no extra dependency). Several series are combined by standardising each column and adding their costs.

Change-point detection here is DESCRIPTIVE: it looks at the whole series, so it must not be used to make features
for forecasting (that would leak the future). Use it for phase boundaries and charts only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_COLS = ["n_events", "entropy", "multi_agent_share", "incident_share", "mean_autonomy", "high_autonomy_share"]


def prepare(mf: pd.DataFrame, cols=DEFAULT_COLS) -> np.ndarray:
    """Columns -> standardised matrix (n_months x d). Missing months (no autonomy value) are carried forward, then
    filled with the column mean. Constant columns become 0."""
    X = mf[cols].apply(pd.to_numeric, errors="coerce").astype(float)
    X = X.ffill().fillna(X.mean()).fillna(0.0)
    sd = X.std(ddof=0).replace(0, 1.0)
    return ((X - X.mean()) / sd).to_numpy()


SHARE_COLS = ["multi_agent_share", "incident_share", "mean_autonomy", "high_autonomy_share"]


def prepare_shares(mf: pd.DataFrame, cols=SHARE_COLS, min_events: int = 3) -> np.ndarray:
    """Volume-free version of `prepare`: only share / average columns (no counts, no entropy), and months with fewer
    than `min_events` events are treated as missing (a share of 0.0 from 0 or 1 events says nothing), then carried
    forward. This asks "did the MIX of events change?" and is not driven by how many documents the corpus has."""
    d = mf.copy()
    thin = pd.to_numeric(d["n_events"], errors="coerce") < min_events
    for c in cols:
        d[c] = pd.to_numeric(d[c], errors="coerce").where(~thin)
    X = d[cols].astype(float).ffill().bfill()
    sd = X.std(ddof=0).replace(0, 1.0)
    return ((X - X.mean()) / sd).fillna(0.0).to_numpy()


class _Cost:
    """O(1) segment cost from cumulative sums: cost(a, b) for rows a..b-1."""

    def __init__(self, X: np.ndarray):
        self.c1 = np.vstack([np.zeros(X.shape[1]), np.cumsum(X, axis=0)])
        self.c2 = np.concatenate([[0.0], np.cumsum((X ** 2).sum(axis=1))])

    def __call__(self, a: int, b: int) -> float:
        s = self.c1[b] - self.c1[a]
        return float(self.c2[b] - self.c2[a] - (s ** 2).sum() / (b - a))


def pelt(X: np.ndarray, penalty: float, min_size: int = 3) -> list[int]:
    """Indices t where a new segment starts (0 < t < n), minimising total cost + penalty * (#segments - 1).
    Every segment has at least `min_size` points."""
    n = len(X)
    cost = _Cost(X)
    F = np.full(n + 1, np.inf)
    F[0] = -penalty
    last = [0] * (n + 1)
    cand = [0]
    for t in range(min_size, n + 1):
        best, arg = np.inf, 0
        vals = {}
        for s in cand:
            if t - s < min_size:
                continue
            v = F[s] + cost(s, t) + penalty
            vals[s] = v
            if v < best:
                best, arg = v, s
        if not vals:
            continue
        F[t], last[t] = best, arg
        # prune: s can never be optimal again if F[s] + cost(s, t) > F[t]
        cand = [s for s in cand if s not in vals or F[s] + cost(s, t) <= F[t]] + [t - min_size + 1]
        cand = sorted(set(cand))
    cps, t = [], n
    while t > 0:
        s = last[t]
        if s > 0:
            cps.append(s)
        t = s
    return sorted(cps)


def exact_partition(X: np.ndarray, penalty: float, min_size: int = 3) -> list[int]:
    """Reference O(n^2) dynamic programme with no pruning; used to test `pelt`."""
    n = len(X)
    cost = _Cost(X)
    F = np.full(n + 1, np.inf)
    F[0] = -penalty
    last = [0] * (n + 1)
    for t in range(min_size, n + 1):
        for s in range(0, t - min_size + 1):
            if np.isfinite(F[s]):
                v = F[s] + cost(s, t) + penalty
                if v < F[t]:
                    F[t], last[t] = v, s
    cps, t = [], n
    while t > 0:
        s = last[t]
        if s > 0:
            cps.append(s)
        t = s
    return sorted(cps)


def default_penalty(n: int, d: int, beta: float = 1.0) -> float:
    """BIC-style penalty for standardised data: beta * d * ln(n) * 2 (each extra segment adds one mean per dimension)."""
    return beta * 2.0 * d * float(np.log(n))


def segments(months: list[str], cps: list[int]) -> pd.DataFrame:
    """Break points -> segment table (start month, end month, length)."""
    edges = [0] + list(cps) + [len(months)]
    return pd.DataFrame([{"segment": i + 1, "start": months[a], "end": months[b - 1], "months": b - a}
                         for i, (a, b) in enumerate(zip(edges[:-1], edges[1:]))])


def stability(X: np.ndarray, months: list[str], betas=(0.25, 0.5, 1.0, 2.0), sizes=(3, 4, 6), tol: int = 1) -> pd.DataFrame:
    """Run PELT over a grid of penalty scales and minimum segment sizes. For each month that is a break point in at
    least one run, report the share of runs that place a break within +/- `tol` months of it."""
    runs = [pelt(X, default_penalty(len(X), X.shape[1], b), m) for b in betas for m in sizes]
    cands = sorted({c for r in runs for c in r})
    rows = []
    for c in cands:
        hit = sum(any(abs(c - x) <= tol for x in r) for r in runs)
        rows.append({"month": months[c], "index": c, "share_of_runs": round(hit / len(runs), 3)})
    return pd.DataFrame(rows).sort_values("share_of_runs", ascending=False).reset_index(drop=True)