from pathlib import Path

import pandas as pd

from ainevo.collection.seed_timelines import _impact, build_seed, epoch_events
from ainevo.schema import load_taxonomy

TAX = load_taxonomy(Path(__file__).resolve().parents[1] / "configs" / "taxonomy.yaml")


def epoch(rows):
    base = dict(Model="", Organization="Org A,Org B", Domain="Language", Link="http://x",
                Parameters=None, **{"Publication date": "2024-01-01", "Training compute (FLOP)": None,
                                    "Model accessibility": "API access", "Notability criteria": "Highly cited"})
    return pd.DataFrame([{**base, **r} for r in rows])


def test_released_vs_unreleased_category():
    df = epoch([dict(Model="A"), dict(Model="B", **{"Model accessibility": "Unreleased"})])
    ev, _, _ = epoch_events(df, models=["A", "B"])
    assert [e.category for e in ev] == ["capability_breakthrough", "research_milestone"]
    assert ev[0].organization == "Org A" and ev[0].origin == "seed"


def test_missing_names_and_cutoff_are_reported_or_dropped():
    df = epoch([dict(Model="A"), dict(Model="Late", **{"Publication date": "2026-10-05"})])
    ev, extras, missing = epoch_events(df, models=["A", "Late", "Nope"])
    assert [e.model_agent for e in ev] == ["A"] and len(extras) == 1
    assert missing == ["Nope"]


def test_agentic_override_and_review_flag():
    df = epoch([dict(Model="Computer-Using Agent (CUA)", **{"Publication date": "2025-01-23"}),
                dict(Model="CogAgent", **{"Publication date": "2023-12-14"})])
    ev, extras, _ = epoch_events(df, models=["Computer-Using Agent (CUA)", "CogAgent"])
    assert (ev[0].category, ev[0].autonomy_level, ev[0].phase_hint) == ("autonomous_action", 3, 4)
    assert [x["needs_review"] for x in extras] == ["", "Y"]


def test_ai_index_merge_replaces_date_and_impact():
    df = epoch([dict(Model="GPT-5.1", **{"Publication date": "2025-11-13"})])
    ev, extras, _ = epoch_events(df, models=["GPT-5.1"])
    assert ev[0].date == "2025-11-12" and "SWE-bench" in ev[0].impact
    assert extras[0]["seed_source"] == "epoch+ai_index" and len(ev[0].source_doc_ids) == 2


def test_impact_formatting():
    r = pd.Series({"Parameters": 3e12, "Training compute (FLOP)": 5e26})
    assert _impact(r) == "3T parameters; 5.0e26 FLOP training compute"
    assert _impact(pd.Series({"Parameters": 213e6, "Training compute (FLOP)": None})) == "213M parameters"


def test_build_seed_is_valid_and_sorted():
    out, missing, problems = build_seed(epoch([dict(Model="GPT-4o", **{"Publication date": "2024-05-13"})]), TAX)
    assert problems == [] and out["date"].is_monotonic_increasing
    assert out["event_id"].is_unique and {"seed_source", "needs_review"} <= set(out.columns)
