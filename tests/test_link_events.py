import pandas as pd

from ainevo.normalization.link_events import (LinkConfig, date_gap, link, link_reason, merge_groups, norm_model,
                                              norm_org, pairwise_prf)

COLS = ["event_id", "date", "category", "trigger", "organization", "model_agent", "capability", "action",
        "autonomy_level", "interaction", "impact", "source", "confidence", "source_doc_ids"]


def m(date, model, org="OpenAI", action="releases it", cat="capability_breakthrough", conf=2, doc="d", **kw):
    row = dict(event_id=doc, date=date, category=cat, trigger="", organization=org, model_agent=model, capability="",
               action=action, autonomy_level="NA", interaction="", impact="", source="", confidence=conf,
               source_doc_ids=doc)
    row.update(kw)
    return row


def frame(*rows):
    return pd.DataFrame(rows, columns=COLS)


def test_normalisers():
    assert norm_model("GPT-5.5") == ("gpt", "5.5") != norm_model("GPT-5")
    assert norm_model("Claude 3.5 Sonnet (October 2024)") == norm_model("claude 3.5 sonnet")
    assert norm_model("OpenAI GPT-4o", "OpenAI") == norm_model("gpt 4o")
    assert norm_org("Google DeepMind") == norm_org("Google Research") == frozenset({"google"})
    assert norm_org("Google,Stanford University") == frozenset({"google", "stanford university"})
    assert norm_org("") == frozenset()


def test_date_gap_with_month_only_dates():
    assert date_gap("2024-05-10", "2024-05-13") == 3
    assert date_gap("2024-05", "2024-05-20") == 0
    assert date_gap("2024-05-31", "2024-06-02") == 2


def test_each_rule_can_reject():
    a = m("2025-08-07", "GPT-5")
    sim = 0.9
    cfg = LinkConfig(window_days=7)      # the rules are tested on a week window; the default is 1 day
    assert link_reason(a, m("2025-08-09", "gpt 5"), sim, cfg) == "link"
    assert link_reason(a, m("2025-08-09", "GPT-5.5"), sim, cfg) == "model"      # versions never merge
    assert link_reason(a, m("2025-08-20", "GPT-5"), sim, cfg) == "date"
    assert link_reason(a, m("2025-08-08", "GPT-5", org="Anthropic"), sim, cfg) == "org"
    assert link_reason(a, m("2025-08-08", "GPT-5"), 0.05, cfg) == "text"
    assert link_reason(a, m("2025-08-08", ""), 0.4, cfg) == "text"                # missing model needs more similarity
    assert link_reason(a, m("2025-08-08", "", org=""), 0.9, cfg) == "org_missing"


def test_link_groups_duplicates_and_keeps_versions_apart():
    df = frame(m("2025-08-07", "GPT-5", doc="a"), m("2025-08-08", "gpt 5", doc="b", action="announced GPT-5"),
               m("2025-08-09", "GPT-5.5", doc="c"), m("2026-04-23", "GPT-5.5", doc="d"))
    g = link(df)["event_group"].tolist()
    assert g[0] == g[1] and len({g[0], g[2], g[3]}) == 3


def test_span_guard_stops_chains():
    df = frame(*[m(f"2025-03-{d:02d}", "Model X", doc=f"d{d}") for d in (1, 7, 13, 19)])
    g = link(df, LinkConfig(window_days=7, max_span_days=14))["event_group"].tolist()
    assert len(set(g)) >= 2 and max(pd.Series(g).value_counts()) <= 3


def test_merge_groups_rules():
    df = frame(m("2025-05", "X", doc="a", conf=1, impact="short"),
               m("2025-05-22", "X", doc="b", conf=3, impact="a much longer impact statement", cat="agentic_development"),
               m("2025-05-23", "X", doc="c", conf=2, cat="agentic_development"))
    df["event_group"] = 0
    out = merge_groups(df, ["autonomous_action", "agentic_development", "capability_breakthrough"])
    r = out.iloc[0]
    assert r.date == "2025-05-22" and r.category == "agentic_development" and r.n_mentions == 3
    assert r.impact == "a much longer impact statement" and r.source_doc_ids == "a;b;c"
    assert r.category_disagreement == "Y" and r.confidence == 1
    tie = frame(m("2025-05-22", "X", doc="a", cat="capability_breakthrough"),
                m("2025-05-22", "X", doc="b", cat="agentic_development"))
    tie["event_group"] = 0
    assert merge_groups(tie, ["autonomous_action", "agentic_development", "capability_breakthrough"]).category[0] == "agentic_development"


def test_pairwise_prf():
    s = pairwise_prf([0, 0, 1, 1], [0, 0, 0, 1])
    assert (s["tp"], s["fp"], s["fn"]) == (1, 1, 2)
    assert pairwise_prf([0, 1], [0, 1])["f1"] == 1.0


def test_generic_model_names_do_not_identify_a_release():
    assert norm_model("ChatGPT", "OpenAI") == () and norm_model("OpenAI models", "OpenAI") == ()
    assert norm_model("GPT-5.1", "OpenAI") == ("gpt", "5.1")
    a = {"date": "2025-10-01", "organization": "OpenAI", "model_agent": "ChatGPT", "title": "Operation Alpha: influence"}
    b = {"date": "2025-10-01", "organization": "OpenAI", "model_agent": "ChatGPT", "title": "Romance scam: task workflows"}
    assert link_reason(a, b, 0.2) == "text"      # same org + generic model + different story: not linked


def test_case_study_titles_are_never_linked():
    from ainevo.normalization.link_events import is_case_study
    assert is_case_study("Playco cut manual fixes 50% prototyping games with GPT-6 Astra")
    assert is_case_study("Coding with OpenAI o1") and is_case_study("Introducing Verdi, an AI dev platform powered by GPT-4o")
    assert not is_case_study("Introducing GPT-5") and not is_case_study("GPT-5 System Card") and not is_case_study("Hello GPT-4o")
    launch = {"date": "2025-08-07", "organization": "OpenAI", "model_agent": "GPT-5", "title": "Introducing GPT-5"}
    story = {"date": "2025-08-07", "organization": "OpenAI", "model_agent": "GPT-5", "title": "Legora reviewed 41 documents with GPT-5"}
    card = {"date": "2025-08-07", "organization": "OpenAI", "model_agent": "GPT-5", "title": "GPT-5 System Card"}
    assert link_reason(launch, story, 0.9) == "case_study"
    assert link_reason(launch, card, 0.9) == "link"


def test_window_is_one_day_by_default():
    a = {"date": "2024-09-26", "organization": "OpenAI", "model_agent": "GPT-4o", "title": "X"}
    b = {"date": "2024-10-01", "organization": "OpenAI", "model_agent": "GPT-4o", "title": "Y"}
    assert link_reason(a, b, 0.9) == "date"


def test_titles_must_name_the_model():
    from ainevo.normalization.link_events import names_model
    assert names_model("Introducing GPT-5.1 for developers", ("gpt", "5.1")) and names_model("Hello GPT‑4o", ("gpt", "4", "o"))
    assert not names_model("Powering virtual education for the classroom", ("gpt", "4")) and names_model("", ("gpt", "4"))
    a = {"date": "2023-03-14", "organization": "OpenAI", "model_agent": "GPT-4", "title": "GPT-4"}
    b = {"date": "2023-03-14", "organization": "OpenAI", "model_agent": "GPT-4", "title": "Filling crucial language learning gaps"}
    assert link_reason(a, b, 0.9) == "title"