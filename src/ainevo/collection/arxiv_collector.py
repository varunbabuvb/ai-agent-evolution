"""arXiv collector. Run from the repo root:  PYTHONPATH=src python -m ainevo.collection.arxiv_collector
2023+ queries require a language-model term AND an agent term, so classical multi-agent RL / robotics papers are not collected."""
import json, os
from datetime import date
import arxiv, yaml


def _or(terms, field="all"):
    return " OR ".join(f'{field}:"{t}"' for t in terms)


def year_query(cfg, year):
    cats = " OR ".join(f"cat:{c}" for c in cfg["categories"])
    dates = f"submittedDate:[{year}01010000 TO {year}12312359]"
    if year >= 2023:
        topic = f"({_or(cfg['llm_terms'])}) AND ({_or(cfg['agent_terms'])})"
    else:
        topic = f"({_or(cfg['early_terms'])})"
    return f"({cats}) AND ({topic}) AND {dates}"


if __name__ == "__main__":
    cfg = yaml.safe_load(open("configs/sources.yaml", encoding="utf-8"))["arxiv"]
    os.makedirs("data/raw/arxiv", exist_ok=True)
    client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=5)
    seen = set()
    with open("data/raw/arxiv/arxiv_raw.jsonl", "w", encoding="utf-8") as f:
        for year, n in cfg["per_year_target"].items():
            query = year_query(cfg, year)
            count = 0
            for r in client.results(arxiv.Search(query=query, max_results=n, sort_by=arxiv.SortCriterion.Relevance)):
                if r.entry_id in seen:
                    continue
                seen.add(r.entry_id)
                f.write(json.dumps({
                    "doc_id": "arxiv_" + r.get_short_id(), "title": r.title, "publication_date": str(r.published.date()),
                    "source": "arXiv", "source_type": "paper", "url": r.entry_id, "text": r.summary.replace("\n", " "),
                    "retrieval_date": str(date.today()), "query_used": query,
                    "metadata": {"authors": [a.name for a in r.authors], "categories": r.categories}},
                    ensure_ascii=False) + "\n")
                count += 1
            print(year, count)
