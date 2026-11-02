import pandas as pd
from ainevo.evaluation.agreement import cohen_kappa, fleiss_kappa, compare, disagreements


def test_cohen_known_value():
    assert abs(cohen_kappa([1, 1, 0, 0], [1, 0, 0, 0]) - 0.5) < 1e-9


def test_cohen_perfect_and_chance():
    assert cohen_kappa(list("abab"), list("abab")) == 1.0
    assert abs(cohen_kappa(list("aabb"), list("abab"))) < 1e-9


def test_fleiss_perfect_and_known():
    assert fleiss_kappa([["a", "a", "a"], ["b", "b", "b"]]) == 1.0
    # classic textbook-style case: complete disagreement pattern gives negative kappa
    assert fleiss_kappa([["a", "b"], ["a", "b"]]) < 0


def test_compare_and_disagreements():
    base = pd.DataFrame({"doc_id": ["d1", "d2", "d3", "d4"], "has_event": ["yes", "yes", "no_off_topic", "yes"],
                         "category": ["x", "y", "", "x"], "autonomy_level": ["1", "2", "", "1"]})
    other = base.copy(); other.loc[1, "category"] = "z"
    res = compare({"A": base, "B": other})
    assert set(res["field"]) == {"has_event", "category", "autonomy_level"}
    assert list(disagreements({"A": base, "B": other}).index) == ["d2"]
