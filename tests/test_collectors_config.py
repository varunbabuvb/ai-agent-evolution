import yaml
from ainevo.collection.arxiv_collector import year_query
from ainevo.preprocessing.build_corpus import cap_openai_per_month

CFG = yaml.safe_load(open("configs/sources.yaml"))["arxiv"]


def test_modern_query_requires_llm_and_agent_terms():
    q = year_query(CFG, 2024)
    assert '"large language model"' in q and '"multi-agent"' in q and "AND" in q and "20240101" in q


def test_early_query_has_no_agent_only_terms():
    q = year_query(CFG, 2019)
    assert '"language model"' in q and 'all:"agent"' not in q


def test_openai_cap_is_per_month_and_keeps_year_end():
    docs = [{"source": "OpenAI", "publication_date": f"2025-{m:02d}-{d:02d}"} for m in (1, 12) for d in range(1, 21)]
    out = cap_openai_per_month(docs, cap=5)
    assert sum(x["publication_date"].startswith("2025-12") for x in out) == 5 and len(out) == 10
