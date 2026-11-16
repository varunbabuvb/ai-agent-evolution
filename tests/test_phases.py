import pandas as pd
import pytest

from ainevo.analysis.phases import compare, draft_phase_starts, load_reference, month_diff


def test_month_diff():
    assert month_diff("2023-03", "2022-12") == 3
    assert month_diff("2022-12", "2023-03") == -3
    assert month_diff("2023-05", "2023-05") == 0


def _gold():
    rows = [("2019-01-05", 1), ("2019-02-01", 1), ("2019-03-01", 1), ("2020-01-01", 1),
            ("2023-06-01", 3), ("2023-07-01", 3), ("2023-09-01", 3), ("2024-01-01", 3)]
    return pd.DataFrame({"date": [r[0] for r in rows], "phase_hint": [r[1] for r in rows]})


def test_draft_uses_kth_earliest_event():
    d = draft_phase_starts(_gold(), k=3).set_index("phase")
    assert d.loc[1, "first_month"] == "2019-01" and d.loc[1, "start_month"] == "2019-03"
    assert d.loc[3, "start_month"] == "2023-09"
    assert d.loc[2, "n_events"] == 0 and d.loc[2, "start_month"] == ""


def test_draft_k_larger_than_count_uses_last():
    g = pd.DataFrame({"date": ["2023-01-01", "2023-02-01"], "phase_hint": [4, 4]})
    assert draft_phase_starts(g, k=5).set_index("phase").loc[4, "start_month"] == "2023-02"


def test_draft_ignores_bad_rows():
    g = pd.DataFrame({"date": ["2023-01-01", "bad", "2023-03-01"], "phase_hint": [4, 4, 9]})
    d = draft_phase_starts(g).set_index("phase")
    assert d.loc[4, "n_events"] == 1


def test_compare_verdicts():
    ref = pd.DataFrame({"phase": [1, 2, 3, 4], "start_month": ["2019-03", "2023-05", "2024-06", ""]})
    c = compare(["2023-04", "2023-11"], ref, "2022-01", tol=3).set_index("phase")
    assert c.loc[1, "verdict"] == "before series"
    assert c.loc[2, "nearest_break"] == "2023-04" and c.loc[2, "offset_months"] == -1 and c.loc[2, "verdict"] == "within +/-3"
    assert c.loc[3, "verdict"] == "no match" and c.loc[3, "nearest_break"] == "2023-11"
    assert c.loc[4, "verdict"] == "no start"


def test_compare_no_breaks():
    ref = pd.DataFrame({"phase": [2], "start_month": ["2023-05"]})
    assert compare([], ref, "2022-01").iloc[0]["verdict"] == "no break"


def test_load_reference_needs_columns(tmp_path):
    p = tmp_path / "r.csv"
    pd.DataFrame({"phase": [1]}).to_csv(p, index=False)
    with pytest.raises(ValueError):
        load_reference(p)
    pd.DataFrame({"phase": [1, 2], "start_month": ["2019-03-15", "2023-05"]}).to_csv(p, index=False)
    assert load_reference(p)["start_month"].tolist() == ["2019-03", "2023-05"]


def test_quarter_start_and_load_manual(tmp_path):
    from ainevo.analysis.phases import _quarter_start, load_manual
    assert _quarter_start("2023-Q3") == "2023-07" and _quarter_start("2026-Q1") == "2026-01"
    assert _quarter_start("none (max 2 gold events per quarter)") == ""
    p = tmp_path / "m.csv"
    pd.DataFrame({"phase": ["2", "3"], "landmark_window_start": ["2023-03", "2023-03"], "landmark_window_end": ["2023-03", "2023-04"],
                  "sustained_from_quarter": ["none (x)", "2023-Q3"], "confidence": ["low", "medium"]}).to_csv(p, index=False)
    m = load_manual(p)
    assert m["sustained_from"].tolist() == ["", "2023-07"] and m["phase"].tolist() == [2, 3]


def test_compare_windows_inside_before_after():
    from ainevo.analysis.phases import compare_windows
    man = pd.DataFrame({"phase": [3, 4, 7], "window_start": ["2023-03", "2024-10", "2025-07"], "window_end": ["2023-04", "2024-11", "2026-03"],
                        "sustained_from": ["2023-07", "2024-10", "2026-01"], "confidence": ["m", "l", "l"]})
    c = compare_windows(["2023-04", "2023-11"], man, "2022-01", tol=3).set_index("phase")
    assert c.loc[3, "gap_to_window"] == 0 and c.loc[3, "verdict"] == "within +/-3"
    assert c.loc[4, "nearest_break"] == "2023-11" and c.loc[4, "gap_to_window"] == -11 and c.loc[4, "verdict"] == "no match"
    assert c.loc[7, "gap_to_window"] == -20
    assert compare_windows([], man, "2022-01").iloc[0]["verdict"] == "no break"
