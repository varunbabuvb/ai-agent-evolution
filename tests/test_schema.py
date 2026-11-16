import pytest
from pathlib import Path

from ainevo.schema import EVENT_COLUMNS, Event, load_taxonomy, make_event_id

TAX = load_taxonomy(Path(__file__).resolve().parents[1] / "configs" / "taxonomy.yaml")


def good(**kw):
    base = dict(event_id="ev_1", date="2024-05-10", category="agentic_development", capability="tool_use",
                interaction="agent_tool", autonomy_level=2, confidence=2, phase_hint=3)
    base.update(kw)
    return Event(**base)


def test_valid_event_has_no_problems():
    assert good().validate(TAX) == []


def test_bad_values_are_reported():
    ev = good(date="May 2024", category="nope", capability="x", interaction="y",
              autonomy_level=7, confidence=5, phase_hint=8)
    msgs = " | ".join(ev.validate(TAX))
    for word in ("date", "category", "capability", "interaction", "autonomy_level", "confidence", "phase_hint"):
        assert word in msgs


def test_rule_warnings():
    assert any("autonomy 3-4" in m for m in good(category="autonomous_action", autonomy_level=1, phase_hint=4).validate(TAX))
    assert any("agent_agent" in m for m in good(category="multi_agent_coordination", phase_hint=5).validate(TAX))


def test_month_and_date_start():
    assert good(date="2024-05").month == "2024-05"
    assert good(date="2024-05").date_start == "2024-05-01"
    assert good(date="2024-05-10").date_start == "2024-05-10"
    assert good(date="2023-12-31").year == 2023


def test_event_id_is_stable_and_order_free():
    assert make_event_id("a", "b") == make_event_id("b", "a")
    assert make_event_id("a") != make_event_id("b")


def test_roundtrip_and_na_autonomy():
    ev = good(autonomy_level=None, source_doc_ids=["d1", "d2"])
    d = ev.to_dict()
    assert d["autonomy_level"] == "NA" and d["source_doc_ids"] == "d1;d2"
    assert Event.from_dict(d) == ev
    assert set(d) == set(EVENT_COLUMNS)


def test_from_gold_row():
    row = {"doc_id": "d9", "event_date": "", "publication_date": "2025-02-06", "category": "research_milestone",
           "trigger": "We introduce X", "capability": "evaluation_benchmark", "autonomy_level": "NA",
           "interaction": "agent_environment", "phase_hint": "3.0", "confidence": "2", "url": "http://u"}
    ev = Event.from_gold_row(row)
    assert ev.date == "2025-02-06"          # falls back to publication_date
    assert ev.autonomy_level is None and ev.phase_hint == 3
    assert ev.source_doc_ids == ["d9"] and ev.source == "http://u"
    assert ev.validate(TAX) == []


def test_from_gold_row_merged_gold_column_names():
    """gold_events_v1.csv uses date / source_url / annotator_confidence, not event_date / url / confidence."""
    row = {"doc_id": "d9", "date": "2025-01-30", "publication_date": "2025-02-06", "category": "research_milestone",
           "trigger": "We introduce X", "capability": "evaluation_benchmark", "autonomy_level": "NA",
           "interaction": "agent_environment", "phase_hint": "3", "annotator_confidence": "3", "source_url": "http://u2"}
    ev = Event.from_gold_row(row)
    assert ev.date == "2025-01-30"           # the event date, not the publication date
    assert ev.confidence == 3 and ev.source == "http://u2"
    assert ev.validate(TAX) == []


def test_from_gold_row_on_the_real_gold_file():
    import pandas as pd
    p = Path(__file__).resolve().parents[1] / "data" / "annotations" / "gold_events_v1.csv"
    if not p.exists():
        pytest.skip("gold file not present")
    g = pd.read_csv(p, keep_default_na=False)
    evs = [Event.from_gold_row(r) for r in g.to_dict("records")]
    assert len(evs) == len(g)
    assert any(e.confidence == 3 for e in evs) and all(e.source for e in evs)
    assert sum(e.date != str(r["publication_date"])[:10] for e, r in zip(evs, g.to_dict("records"))) > 0