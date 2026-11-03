"""Merge raw collections into data/interim/corpus_v1.jsonl.  PYTHONPATH=src python -m ainevo.preprocessing.build_corpus"""
import collections, glob, hashlib, json, os, re

KEYWORDS = re.compile(
    r"agent|tool use|function call|autonom|multi-agent|computer use|"
    r"assistant|chatgpt|gpt|operator|codex|reasoning|browse|"
    r"plugin|mcp|workflow|copilot|robot|safety|incident|model", re.I)
EVENT_HINT = re.compile(
    r"agent|tool use|function call|autonom|reasoning|introducing|announc|launch|releas|"
    r"partnership|integration|leaderboard|benchmark|welcome|collaborat|open-source|available", re.I)

OPENAI_CAP_PER_MONTH = 15       # was 120 per YEAR, which kept the earliest posts and dropped the end of each year
HF_CAP_PER_MONTH = 8            # Hugging Face blog mixes news with community tutorials
RELEASE_CAP_PER_REPO_MONTH = 8  # keeps one busy repo (langchain) from dominating the corpus
POOL = "data/annotations/pool_v0.json"   # documents already given to annotators are never dropped
OUT = "data/interim/corpus_v1.jsonl"


def merge_raw(paths):
    docs, seen = [], set()
    for path in paths:
        for line in open(path, encoding="utf-8"):
            d = json.loads(line)
            if d["url"] in seen:
                continue
            seen.add(d["url"])
            d["doc_id"] = d["source_type"][:2] + "_" + hashlib.md5(d["url"].encode()).hexdigest()[:10]
            d["text"] = re.sub(r"\s+", " ", d["text"]).strip()
            docs.append(d)
    return docs


def keep_agent_related(docs):
    return [d for d in docs if d["source_type"] != "lab_blog" or KEYWORDS.search(d["title"] + " " + d["text"][:500])]


def cap_openai_per_month(docs, cap=OPENAI_CAP_PER_MONTH):
    count, final = collections.Counter(), []
    for d in sorted(docs, key=lambda x: x["publication_date"]):
        if d["source"] == "OpenAI":
            key = d["publication_date"][:7]
            if count[key] >= cap:
                continue
            count[key] += 1
        final.append(d)
    return final


def cap_hugging_face(docs, cap=HF_CAP_PER_MONTH):
    """Per month keep the `cap` Hugging Face posts with the most launch/agent words (ties: longer text)."""
    groups, rest = collections.defaultdict(list), []
    for d in docs:
        if d["source"] == "Hugging Face":
            groups[d["publication_date"][:7]].append(d)
        else:
            rest.append(d)
    score = lambda x: (-len(EVENT_HINT.findall(x["title"] + " " + x["text"][:500])), -len(x["text"]))
    kept = [d for g in groups.values() for d in sorted(g, key=score)[:cap]]
    return sorted(rest + kept, key=lambda x: x["publication_date"])


def cap_release_notes(docs, cap=RELEASE_CAP_PER_REPO_MONTH):
    """Keep the `cap` longest release notes per repo per month."""
    groups, rest = collections.defaultdict(list), []
    for d in docs:
        if d["source_type"] == "release_notes":
            groups[(d["source"], d["publication_date"][:7])].append(d)
        else:
            rest.append(d)
    kept = [d for g in groups.values() for d in sorted(g, key=lambda x: -len(x["text"]))[:cap]]
    return sorted(rest + kept, key=lambda x: x["publication_date"])


def protected_ids(path=POOL):
    if not os.path.exists(path):
        return set()
    pool = json.load(open(path, encoding="utf-8"))
    return {d["doc_id"] for docs in pool.values() for d in docs}


def build(docs, protected=frozenset()):
    """Apply filters and caps; documents in `protected` bypass them (months may exceed a cap by a few)."""
    keep = [d for d in docs if d["doc_id"] in protected]
    rest = [d for d in docs if d["doc_id"] not in protected]
    out = cap_release_notes(cap_hugging_face(cap_openai_per_month(keep_agent_related(rest)))) + keep
    return sorted(out, key=lambda x: x["publication_date"])


if __name__ == "__main__":
    paths = sorted(glob.glob("data/raw/**/*.jsonl", recursive=True))
    final = build(merge_raw(paths), protected_ids())
    with open(OUT, "w", encoding="utf-8") as f:
        for d in final:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    by = collections.Counter(d["publication_date"][:4] for d in final)
    print("total", len(final))
    for y in sorted(by):
        print(y, by[y])