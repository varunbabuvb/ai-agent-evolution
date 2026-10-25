import json, glob, hashlib, re, collections

KEYWORDS = re.compile(
    r"agent|tool use|function call|autonom|multi-agent|computer use|"
    r"assistant|chatgpt|gpt|operator|codex|reasoning|browse|"
    r"plugin|mcp|workflow|copilot|robot|safety|incident|model", re.I)

OPENAI_CAP_PER_YEAR = 120
OUT = "data/interim/corpus_v1.jsonl"

docs, seen_urls = [], set()
for path in glob.glob("data/raw/**/*.jsonl", recursive=True):
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        url = d["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        d["doc_id"] = d["source_type"][:2] + "_" + hashlib.md5(url.encode()).hexdigest()[:10]
        d["text"] = re.sub(r"\s+", " ", d["text"]).strip()
        docs.append(d)

# keep agent-related lab blog posts only
docs = [d for d in docs
        if d["source_type"] != "lab_blog"
        or KEYWORDS.search(d["title"] + " " + d["text"][:500])]

# cap OpenAI posts per year
count, final = collections.Counter(), []
for d in sorted(docs, key=lambda x: x["publication_date"]):
    if d["source"] == "OpenAI":
        key = d["publication_date"][:4]
        if count[key] >= OPENAI_CAP_PER_YEAR:
            continue
        count[key] += 1
    final.append(d)

with open(OUT, "w", encoding="utf-8") as f:
    for d in final:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")

by = collections.Counter(d["publication_date"][:4] for d in final)
print("total", len(final))
for y in sorted(by):
    print(y, by[y])