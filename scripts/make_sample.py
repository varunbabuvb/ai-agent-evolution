import arxiv, json
from datetime import date

query = "cat:cs.AI AND all:agent"
search = arxiv.Search(query=query, max_results=20,
                      sort_by=arxiv.SortCriterion.SubmittedDate)

with open("data/interim/sample_20.jsonl", "w", encoding="utf-8") as f:
    for r in arxiv.Client().results(search):
        doc = {
            "doc_id": "arxiv_" + r.get_short_id(),
            "title": r.title,
            "publication_date": str(r.published.date()),
            "source": "arXiv",
            "source_type": "paper",
            "url": r.entry_id,
            "text": r.summary.replace("\n", " "),
            "retrieval_date": str(date.today()),
            "query_used": query,
            "metadata": {"authors": [a.name for a in r.authors],
                         "categories": r.categories},
        }
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
print("done")
