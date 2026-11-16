import numpy as np
import pandas as pd

from ainevo.analysis.changepoints import default_penalty, exact_partition, pelt, prepare, segments, stability


def step_series(n1=20, n2=20, jump=4.0, seed=0, noise=0.5):
    rng = np.random.default_rng(seed)
    return np.concatenate([rng.normal(0, noise, n1), rng.normal(jump, noise, n2)])[:, None]


def test_finds_a_clear_step_and_nothing_in_flat_noise():
    X = step_series()
    assert pelt(X, default_penalty(len(X), 1), 3) == [20]
    flat = np.random.default_rng(1).normal(0, 1, (40, 1))
    assert pelt(flat, default_penalty(40, 1), 3) == []


def test_pelt_equals_exact_dynamic_programme():
    rng = np.random.default_rng(3)
    for k in range(6):
        X = np.concatenate([rng.normal(0, 1, (12, 2)), rng.normal(3, 1, (9, 2)), rng.normal(-2, 1, (11, 2))])
        pen = default_penalty(len(X), 2, 0.5 + k / 4)
        assert pelt(X, pen, 3) == exact_partition(X, pen, 3)


def test_min_size_and_penalty_behave():
    X = step_series(15, 15, 3.0, noise=1.0)
    for m in (3, 5, 8):
        cps = pelt(X, 1.0, m)
        edges = [0] + cps + [len(X)]
        assert all(b - a >= m for a, b in zip(edges[:-1], edges[1:]))
    assert len(pelt(X, 0.5, 3)) >= len(pelt(X, 5000.0, 3)) == 0


def test_prepare_fills_nan_and_segments_table():
    mf = pd.DataFrame({"n_events": [1, 2, 3, 4], "entropy": [0.0] * 4, "mean_autonomy": [np.nan, 2.0, np.nan, 4.0]})
    X = prepare(mf, ["n_events", "entropy", "mean_autonomy"])
    assert X.shape == (4, 3) and not np.isnan(X).any() and np.allclose(X[:, 1], 0)
    seg = segments(["a", "b", "c", "d", "e"], [2])
    assert seg.start.tolist() == ["a", "c"] and seg.end.tolist() == ["b", "e"] and seg.months.tolist() == [2, 3]


def test_stability_marks_the_true_break_in_every_run():
    X = step_series()
    months = [f"m{i}" for i in range(len(X))]
    st = stability(X, months)
    top = st.iloc[0]
    assert top["month"] == "m20" and top["share_of_runs"] == 1.0


def test_prepare_shares_ignores_volume_and_thin_months():
    from ainevo.analysis.changepoints import prepare_shares
    mf = pd.DataFrame({"n_events": [0, 1, 5, 9, 4], "multi_agent_share": [0.0, 0.0, 0.2, 0.4, 0.4], "incident_share": [0.0] * 5,
                       "mean_autonomy": [np.nan, 0.0, 2.0, 2.0, 2.0], "high_autonomy_share": [0.0, 0.0, 0.5, 0.5, 0.5]})
    X = prepare_shares(mf)
    assert X.shape == (5, 4) and not np.isnan(X).any()
    assert np.allclose(X[0], X[2])        # months with <3 events are back-filled from the first usable month
    assert np.allclose(X[:, 2], 0)        # a constant column carries no information