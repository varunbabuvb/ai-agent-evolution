import arxiv, json, yaml, time
from datetime import date

cfg = yaml.safe_load(open("configs/sources.yaml", encoding="utf-8"))["arxiv"]
cats = " OR ".join(f"cat:{c}" for c in cfg["categories"])
kws = " OR ".join(f'all:"{k}"' for k in cfg["keywords"])

# per-year targets: 80 for 2017-2021, 120 for 2022-2026 (about 1,000 total)
targets = {y: 80 for y in range(2017, 2022)}
targets.update({y: 120 for y in range(2022, 2027)})

client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=5)
seen = set()

with open("data/raw/arxiv/arxiv_raw.jsonl", "w", encoding="utf-8") as f:
    for year, n in targets.items():
        query = f"({cats}) AND ({kws}) AND submittedDate:[{year}01010000 TO {year}12312359]"
        search = arxiv.Search(query=query, max_results=n,
                              sort_by=arxiv.SortCriterion.Relevance)
        count = 0
        for r in client.results(search):
            if r.entry_id in seen:
                continue
            seen.add(r.entry_id)
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
            count += 1
        print(year, count)
