import numpy as np
import pandas as pd

from ainevo.analysis.timeline import build_timeline
from ainevo.features.monthly import monthly_features, quarterly_counts


def ev(date, cat, org="OpenAI", aut=0, i=[0]):
    i[0] += 1
    return {"event_id": f"e{i[0]}", "date": date, "category": cat, "organization": org, "autonomy_level": aut}


DF = pd.DataFrame([
    ev("2022-01-05", "capability_breakthrough", "OpenAI", 0),
    ev("2022-01", "multi_agent_coordination", "Google", 4),
    ev("2022-01-20", "multi_agent_coordination", "OpenAI", "NA"),
    ev("2022-03-02", "adoption_scale", "Meta", 3),
    ev("2019-05-01", "research_milestone", "Google", 0),
    ev("2019-06-01", "research_milestone", "Google", 0),
    ev("2020-02-01", "capability_breakthrough", "OpenAI", 0),
    ev("2026-10-03", "autonomous_action", "xAI", 2),        # after cutoff
    ev("2023-02-30", "autonomous_action", "xAI", 2),        # bad date
    ev("2023-02-01", "not_a_category", "xAI", 2),           # bad category
])


def test_timeline_cleans_and_cuts():
    tl = build_timeline(DF, "2026-09")
    assert len(tl) == 7 and tl.month.max() == "2022-03"
    assert list(tl.date_start) == sorted(tl.date_start)
    assert tl.loc[tl.date == "2020-02-01", "quarter"].iloc[0] == "2020Q1"
    assert np.isnan(tl.loc[tl.date == "2022-01-20", "autonomy"].iloc[0])


def test_monthly_features_values():
    tl = build_timeline(DF)
    mf = monthly_features(tl, "2022-01", "2022-03").set_index("month")
    assert list(mf.index) == ["2022-01", "2022-02", "2022-03"]
    jan, feb = mf.loc["2022-01"], mf.loc["2022-02"]
    assert jan.n_events == 3 and jan.n_categories == 2
    assert jan.multi_agent_share == round(2 / 3, 4)
    assert jan.dominant_category == "multi_agent_coordination"
    assert jan.mean_autonomy == 2.0 and jan.high_autonomy_share == 0.5   # 0 and 4 -> only 4 is >=3
    assert feb.n_events == 0 and feb.dominant_category == "" and feb.entropy == 0.0
    assert mf.loc["2022-03"].dominant_category == ""                     # 1 event < min_events


def test_novelty_uses_only_the_past():
    tl = build_timeline(DF)
    mf = monthly_features(tl, "2022-01", "2022-03", min_events=1).set_index("month")
    # OpenAI and Google were seen before 2022 (2019/2020 rows); Meta is new in March
    assert mf.loc["2022-01"].novelty == 0.0
    assert mf.loc["2022-03"].novelty == 1.0
    # shifting a FUTURE event must not change an earlier month
    more = pd.concat([DF, pd.DataFrame([ev("2022-02-10", "adoption_scale", "Meta")])])
    mf2 = monthly_features(build_timeline(more), "2022-01", "2022-03", min_events=1).set_index("month")
    assert mf2.loc["2022-01"].equals(mf.loc["2022-01"])
    assert mf2.loc["2022-03"].novelty == 0.0       # Meta no longer new in March


def test_dominant_tie_goes_to_taxonomy_precedence():
    d = pd.DataFrame([ev("2023-05-01", "capability_breakthrough"), ev("2023-05-02", "adoption_scale"),
                      ev("2023-05-03", "capability_breakthrough"), ev("2023-05-04", "adoption_scale")])
    mf = monthly_features(build_timeline(d), "2023-05", "2023-05")
    assert mf.dominant_category.iloc[0] == "adoption_scale"


def test_quarterly_counts_zero_filled():
    q = quarterly_counts(build_timeline(DF))
    assert len(q) == 20 and q.n_events.sum() == 3
    assert q.set_index("quarter").loc["2019Q2", "research_milestone"] == 2


def test_from_gold_blanks_placeholders_and_maps_columns():
    from ainevo.analysis.timeline import from_gold
    g = pd.DataFrame([{"event_id": "GE-1", "doc_id": "d1", "date": "2024-01-01", "category": "adoption_scale",
                       "organization": "arXiv", "model_agent": "Model/Agent", "annotator_confidence": 2},
                      {"event_id": "GE-2", "doc_id": "d2", "date": "2024-01-02", "category": "adoption_scale",
                       "organization": "OpenAI", "model_agent": "GPT-4", "annotator_confidence": 3}])
    o = from_gold(g)
    assert list(o.organization) == ["", "OpenAI"] and list(o.model_agent) == ["", "GPT-4"]
    assert list(o.source_doc_ids) == ["d1", "d2"] and list(o.confidence) == [2, 3]

def test_from_extractions_filters_and_maps():
    from ainevo.analysis.timeline import from_extractions
    x = pd.DataFrame([{"doc_id": "d1", "event_date": "2024-05-13", "p_event": "0.9", "category_pred": "adoption_scale",
                       "organizations": "OpenAI; Microsoft", "systems": "GPT-4o; ChatGPT", "capability_pred": "multimodal",
                       "autonomy_pred": "", "interaction_pred": "human_model"},
                      {"doc_id": "d2", "event_date": "2024-05-14", "p_event": "0.2", "category_pred": "", "organizations": "",
                       "systems": "", "capability_pred": "", "autonomy_pred": "", "interaction_pred": ""}])
    o = from_extractions(x)
    assert len(o) == 1 and o.organization[0] == "OpenAI" and o.model_agent[0] == "GPT-4o"
    assert o.autonomy_level[0] == "NA" and o.source_doc_ids[0] == "d1"


def test_apply_merges_drops_one_and_keeps_both_docs():
    import pandas as pd
    import pytest
    from ainevo.analysis.timeline import apply_merges
    df = pd.DataFrame({"annotation_id": ["A-1", "A-2", "A-3"], "source_doc_ids": ["d1", "d2", "d3"]})
    m = pd.DataFrame({"keep_annotation_id": ["A-1"], "drop_annotation_id": ["A-2"]})
    out = apply_merges(df, m)
    assert out["annotation_id"].tolist() == ["A-1", "A-3"]
    assert out.loc[0, "source_doc_ids"] == "d1;d2"
    with pytest.raises(ValueError):
        apply_merges(df, pd.DataFrame({"keep_annotation_id": ["A-1"], "drop_annotation_id": ["ZZ"]}))