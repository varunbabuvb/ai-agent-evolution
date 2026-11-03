import json, random, collections as c
rows = [json.loads(l) for l in open("data/interim/corpus_v1_clean.jsonl", encoding="utf-8")]
print("total", len(rows))
by = c.Counter((r["publication_date"][:4], r["source_type"]) for r in rows)
for y in range(2017, 2027):
    print(y, {s: by[(str(y), s)] for s in ("paper", "lab_blog", "release_notes")})
print("dup ids", len(rows) - len({r["doc_id"] for r in rows}), "| dup urls", len(rows) - len({r["url"] for r in rows}))
print("date range", min(r["publication_date"] for r in rows), max(r["publication_date"] for r in rows))
print("texts under 100 chars", sum(len(r["text"]) < 100 for r in rows))
p = [r for r in rows if r["source_type"] == "paper" and r["publication_date"] >= "2023"]
print("papers 2023+:", len(p), "| with LLM terms:", sum(bool(r["metadata"].get("llm_terms_found")) for r in p))
print("sources", c.Counter(r["source"] for r in rows).most_common())
random.seed(1)
print("\nrandom 2023+ paper titles:")
for r in random.sample(p, min(8, len(p))):
    print(" -", r["publication_date"], r["title"][:90])
