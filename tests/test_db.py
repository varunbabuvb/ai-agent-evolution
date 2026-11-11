import csv
import json

from ainevo.storage import db

TAX = db.load_taxonomy("configs/taxonomy.yaml")

DOCS = [
    {"doc_id": "pa_1", "title": "An LLM Compiler for Parallel Function Calling", "publication_date": "2023-12-07",
     "source": "arXiv", "source_type": "paper", "url": "http://arxiv.org/abs/1", "retrieval_date": "2026-11-01",
     "text": "We present a compiler that plans and runs tool calls in parallel for large language model agents.",
     "query_used": "q", "metadata": {"llm_terms_found": True}},
    {"doc_id": "la_2", "title": "Introducing Operator", "publication_date": "2025-01-23", "source": "OpenAI",
     "source_type": "lab_blog", "url": "https://openai.com/operator", "retrieval_date": "2026-11-01",
     "text": "Operator is an agent that can use its own browser to perform tasks for you.",
     "query_used": "q", "metadata": {"text_source": "full_page", "llm_terms_found": True}},
    {"doc_id": "re_3", "title": "langchain 0.1.0", "publication_date": "2024-01-05", "source": "langchain-ai/langchain",
     "source_type": "release_notes", "url": "https://github.com/langchain-ai/langchain/releases/1",
     "retrieval_date": "2026-11-01", "text": "Adds a new agent executor with streaming support for tools.",
     "query_used": "q", "metadata": {"low_signal_release": False}},
]


def _corpus(tmp_path):
    p = tmp_path / "corpus.jsonl"
    p.write_text("\n".join(json.dumps(d) for d in DOCS), encoding="utf-8")
    return p


def _event(i="E1", **kw):
    e = {"event_id": i, "date": "2025-01-23", "category": "agentic_development", "trigger": "Introducing",
         "organization": "OpenAI", "model_agent": "Operator", "capability": "tool_use", "action": "browses the web",
         "autonomy_level": "3", "interaction": "human_agent", "impact": "", "phase_hint": "3",
         "annotator_confidence": "2", "doc_id": "la_2", "source_url": "https://openai.com/operator"}
    e.update(kw)
    return e


def _built(tmp_path, events=None):
    conn = db.connect(tmp_path / "t.db")
    db.create_schema(conn)
    db.load_documents(conn, _corpus(tmp_path))
    if events:
        db.insert_events(conn, events, TAX)
    return conn


def test_build_and_counts(tmp_path):
    conn = _built(tmp_path)
    c = db.corpus_counts(conn)
    assert c["total"] == 3
    assert {(r["year"], r["source_type"]): r["n"] for r in c["by_year_and_type"]}[(2025, "lab_blog")] == 1
    assert db.get_document(conn, "pa_1")["year"] == 2023
    assert db.get_document(conn, "nope") is None
    assert db.get_document(conn, "la_2")["text_source"] == "full_page"


def test_search_and_filters(tmp_path):
    conn = _built(tmp_path)
    hits = db.search_documents(conn, "browser")
    assert [h["doc_id"] for h in hits] == ["la_2"]
    assert {h["doc_id"] for h in db.search_documents(conn, "agent")} == {"pa_1", "la_2", "re_3"}
    assert [h["doc_id"] for h in db.search_documents(conn, "agent", source_types=["paper"])] == ["pa_1"]
    assert [h["doc_id"] for h in db.search_documents(conn, "", year_from=2025)] == ["la_2"]
    assert len(db.search_documents(conn, "", sources=["OpenAI", "arXiv"])) == 2
    assert len(db.search_documents(conn, "agent", limit=1)) == 1


def test_search_survives_special_characters(tmp_path):
    conn = _built(tmp_path)
    for q in ['agent "tool" OR (', "multi-agent*", "NEAR(a b)", "'; DROP TABLE documents; --", "   "]:
        db.search_documents(conn, q)
    assert db.corpus_counts(conn)["total"] == 3


def test_fallback_search_without_fts(tmp_path):
    conn = _built(tmp_path)
    conn.execute("DROP TABLE documents_fts")
    assert [h["doc_id"] for h in db.search_documents(conn, "browser")] == ["la_2"]


def test_valid_event_loads_with_source(tmp_path):
    conn = _built(tmp_path, [_event()])
    ev = db.query_events(conn)
    assert len(ev) == 1 and ev[0]["trigger"] == "Introducing" and ev[0]["month"] == "2025-01"
    assert ev[0]["phase_hint"] == 3 and ev[0]["annotator_confidence"] == 2 and ev[0]["origin"] == "gold"
    assert ev[0]["sources"] == [{"doc_id": "la_2", "url": "https://openai.com/operator", "title": "Introducing Operator"}]


def test_bad_events_are_rejected_not_loaded(tmp_path):
    conn = _built(tmp_path)
    good = _event("G1")
    bad = [_event("B1", category="made_up"), _event("B2", date="Jan 2025"), _event("B3", autonomy_level="7"),
           _event("B4", capability="telepathy"), _event("B5", phase_hint="9"), _event("", date="2025-01"),
           _event("B7", annotator_confidence="5")]
    n, rejected = db.insert_events(conn, [good] + bad, TAX)
    assert n == 1 and len(rejected) == 7
    assert [e["event_id"] for e in db.query_events(conn)] == ["G1"]


def test_event_filters_and_monthly_view(tmp_path):
    ev = [_event("E1"), _event("E2", date="2025-01", category="capability_breakthrough", autonomy_level="NA"),
          _event("E3", date="2024-06-10", organization="Anthropic", doc_id="pa_1", source_url="")]
    conn = _built(tmp_path, ev)
    assert [e["event_id"] for e in db.query_events(conn, categories=["agentic_development"])] == ["E3", "E1"]
    assert [e["event_id"] for e in db.query_events(conn, organizations=["Anthropic"])] == ["E3"]
    assert [e["event_id"] for e in db.query_events(conn, autonomy_levels=["NA"])] == ["E2"]
    assert [e["event_id"] for e in db.query_events(conn, month_from="2025-01")] == ["E2", "E1"]
    assert len(db.query_events(conn, limit=1)) == 1
    m = {(r["month"], r["category"]): r["n_events"] for r in conn.execute("SELECT * FROM events_monthly")}
    assert m[("2025-01", "agentic_development")] == 1 and m[("2025-01", "capability_breakthrough")] == 1


def test_reloading_an_event_replaces_it_and_its_sources(tmp_path):
    conn = _built(tmp_path, [_event("E1")])
    db.insert_events(conn, [_event("E1", category="adoption_scale",
                                   sources=[{"doc_id": "pa_1", "url": "u1"}, {"doc_id": "re_3", "url": "u2"}])], TAX)
    ev = db.query_events(conn)
    assert len(ev) == 1 and ev[0]["category"] == "adoption_scale"
    assert sorted(s["doc_id"] for s in ev[0]["sources"]) == ["pa_1", "re_3"]


def test_load_events_csv_like_gold_file(tmp_path):
    p = tmp_path / "gold.csv"
    rows = [_event("GE-0001"), _event("GE-0002", category="bogus")]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    conn = _built(tmp_path)
    n, rejected = db.load_events_file(conn, p, TAX, "gold")
    assert n == 1 and rejected[0][0] == "GE-0002"


def test_build_database_is_repeatable(tmp_path):
    p = tmp_path / "gold.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(_event()))
        w.writeheader()
        w.writerow(_event())
    out = [db.build_database(tmp_path / "x.db", _corpus(tmp_path), p) for _ in range(2)]
    assert out[0]["documents"] == out[1]["documents"] == 3 and out[1]["events"] == 1
