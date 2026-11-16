"""Rolling statistics and event-cluster summaries (owner: TS, plan T8 / Day 15).

Rolling features are TRAILING windows: the value for month t uses months <= t only, so the table can be
used for rolling-origin forecasting without leaking the future. Windows are trimmed at the start of the series
(min_periods), so early values rest on fewer months: they are noisy, and `n_obs` says how many months were used.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ainevo.normalization.embed import TfidfEmbedder, cluster, event_text

ROLL_COLS = ["n_events", "entropy", "multi_agent_share", "incident_share", "mean_autonomy", "high_autonomy_share", "novelty"]


def rolling_features(mf: pd.DataFrame, cols=ROLL_COLS, windows=(3, 6)) -> pd.DataFrame:
    """Add, for every column and window w: trailing mean `<col>_ma<w>`, trailing std `<col>_sd<w>`;
    for every column: change vs the previous month `<col>_d1` and an EWMA `<col>_ewm`.
    Trailing only. NaN months (no autonomy value) are skipped by the mean, not treated as 0."""
    out = mf.copy().sort_values("month").reset_index(drop=True)
    new = {}
    for c in cols:
        s = pd.to_numeric(out[c], errors="coerce")
        for w in windows:
            new[f"{c}_ma{w}"] = s.rolling(w, min_periods=1).mean().round(4)
            new[f"{c}_sd{w}"] = s.rolling(w, min_periods=2).std().round(4)
        new[f"{c}_d1"] = s.diff().round(4)
        new[f"{c}_ewm"] = s.ewm(alpha=0.5, adjust=False, ignore_na=True).mean().round(4)
    new["n_obs_w3"] = pd.Series(np.minimum(np.arange(1, len(out) + 1), 3))
    new["n_obs_w6"] = pd.Series(np.minimum(np.arange(1, len(out) + 1), 6))
    return pd.concat([out, pd.DataFrame(new)], axis=1)


def cluster_events(df: pd.DataFrame, threshold: float = 0.8):
    """TF-IDF + average-linkage clustering of event texts (model, organisation, action, capability, title).
    Returns (labels, X, embedder). Fitted on the given rows only."""
    texts = [event_text(r) for r in df.to_dict("records")]
    emb = TfidfEmbedder()
    X = emb.fit_transform(texts)
    return cluster(X, threshold), X, emb


def cluster_summary(df: pd.DataFrame, labels, X, emb, top_terms: int = 6) -> pd.DataFrame:
    """One row per cluster: size, years spanned, dominant category and its share, top TF-IDF terms."""
    inv = {i: t for t, i in emb.vocab_.items()}
    d = df.assign(_c=labels)
    rows = []
    for c, g in d.groupby("_c"):
        idx = g.index.to_numpy()
        centre = X[idx].mean(axis=0)
        terms = [inv[j] for j in np.argsort(-centre)[:top_terms] if centre[j] > 0]
        cats = g["category"].value_counts()
        years = pd.to_datetime(g["date"].astype(str).str[:7], errors="coerce").dt.year
        rows.append({"cluster": int(c), "size": len(g), "first_year": int(years.min()), "last_year": int(years.max()),
                     "top_category": cats.index[0], "top_category_share": round(cats.iloc[0] / len(g), 3),
                     "top_terms": " ".join(terms)})
    return pd.DataFrame(rows).sort_values("size", ascending=False).reset_index(drop=True)


def category_counts_by_month(tl: pd.DataFrame, months: list[str], categories: list[str]) -> pd.DataFrame:
    """Events per month and category (rows = months in `months`, zero-filled, columns = `categories` in that order)."""
    t = pd.crosstab(tl["month"], tl["category"]).reindex(index=months, columns=categories, fill_value=0)
    t.index.name = "month"
    return t


def category_mix_by_year(tl: pd.DataFrame, categories: list[str]) -> pd.DataFrame:
    """Share of each category per year (rows sum to 1) plus `n` = events that year."""
    t = pd.crosstab(tl["year"], tl["category"]).reindex(columns=categories, fill_value=0)
    n = t.sum(axis=1)
    out = t.div(n.replace(0, np.nan), axis=0).fillna(0.0)
    out["n"] = n
    return out
