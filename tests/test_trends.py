import numpy as np
import pandas as pd

from ainevo.analysis.trends import cluster_events, cluster_summary, rolling_features


def mf(vals, aut=None):
    n = len(vals)
    return pd.DataFrame({"month": [f"2023-{i + 1:02d}" for i in range(n)], "n_events": vals, "entropy": 0.0,
                         "multi_agent_share": 0.0, "incident_share": 0.0, "high_autonomy_share": 0.0, "novelty": 0.0,
                         "mean_autonomy": aut if aut is not None else [1.0] * n, "dominant_category": ""})


def test_trailing_moving_average_worked_example():
    r = rolling_features(mf([2, 4, 6, 8]), windows=(3,))
    assert list(r.n_events_ma3) == [2.0, 3.0, 4.0, 6.0]       # (2) (2+4)/2 (2+4+6)/3 (4+6+8)/3
    assert list(r.n_events_d1[1:]) == [2.0, 2.0, 2.0] and np.isnan(r.n_events_d1[0])
    assert list(r.n_obs_w3) == [1, 2, 3, 3]


def test_rolling_never_uses_the_future():
    base = mf([1, 2, 3, 4, 5, 6])
    changed = mf([1, 2, 3, 4, 5, 600])
    a, b = rolling_features(base), rolling_features(changed)
    cols = [c for c in a.columns if c.startswith("n_events_")]
    assert a.loc[:4, cols].equals(b.loc[:4, cols])            # months 1-5 unaffected by a change in month 6


def test_nan_months_are_skipped_not_zero():
    r = rolling_features(mf([1, 1, 1], aut=[2.0, np.nan, 4.0]), cols=["mean_autonomy"], windows=(3,))
    assert r.mean_autonomy_ma3[2] == 3.0                       # mean of 2 and 4, the NaN month is ignored


def test_cluster_summary_groups_and_describes():
    ev = pd.DataFrame({"model_agent": ["GPT-4", "GPT-4", "Claude 3", "Claude 3"], "organization": ["OpenAI", "OpenAI", "Anthropic", "Anthropic"],
                       "action": ["releases GPT-4", "launches GPT-4", "releases Claude 3", "launches Claude 3"],
                       "capability": ["x"] * 4, "date": ["2023-03", "2023-03-15", "2024-03", "2024-03-05"],
                       "category": ["capability_breakthrough"] * 4})
    labels, X, emb = cluster_events(ev, 0.8)
    cs = cluster_summary(ev, labels, X, emb)
    assert len(cs) == 2 and cs["size"].tolist() == [2, 2]
    assert any("gpt" in t for t in cs.top_terms) and any("claude" in t for t in cs.top_terms)


def test_category_counts_and_year_mix():
    from ainevo.analysis.trends import category_counts_by_month, category_mix_by_year
    tl = pd.DataFrame({"month": ["2023-01", "2023-01", "2023-03", "2024-01"], "year": [2023, 2023, 2023, 2024],
                       "category": ["a", "b", "a", "b"]})
    c = category_counts_by_month(tl, ["2023-01", "2023-02", "2023-03"], ["a", "b"])
    assert c.loc["2023-02"].sum() == 0 and c.loc["2023-01", "a"] == 1 and c.loc["2023-03", "a"] == 1
    y = category_mix_by_year(tl, ["a", "b"])
    assert y.loc[2023, "a"] == round(2 / 3, 10) or abs(y.loc[2023, "a"] - 2 / 3) < 1e-9
    assert y.loc[2023, "n"] == 3 and y.loc[2024, "b"] == 1.0
