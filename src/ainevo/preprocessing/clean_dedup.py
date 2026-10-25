import json, re, hashlib, collections
from datetime import date, datetime
from datasketch import MinHash, MinHashLSH

IN = "data/interim/corpus_v1.jsonl"
OUT = "data/interim/corpus_v1_clean.jsonl"
REPORT = "data/interim/cleaning_report.json"

START = date(2017, 1, 1)
CUTOFF = date(2026, 9, 30)      # last complete month; final value goes in configs/split.yaml on Day 11
MIN_CHARS = 100
JACCARD = 0.85                  # near-duplicate threshold

BOILERPLATE = [
    r"subscribe to (our )?newsletter.*",
    r"all rights reserved.*",
    r"read more\s*(»|>)?",
    r"share (this )?(post|article).*",
    r"click here to .*",
    r"sign up for .*",
    r"cookie(s)? (policy|settings).*",
]
BP = re.compile("|".join(BOILERPLATE), re.I)


def clean_text(t):
    t = re.sub(r"<[^>]+>", " ", t)            # leftover HTML tags
    t = re.sub(r"https?://\S+", " ", t)       # raw URLs
    t = BP.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_date(s):
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def minhash(text, n=5):
    words = text.lower().split()
    m = MinHash(num_perm=128)
    for i in range(max(1, len(words) - n + 1)):
        m.update(" ".join(words[i:i + n]).encode("utf-8"))
    return m


stats = collections.Counter()
docs = []
for line in open(IN, encoding="utf-8"):
    d = json.loads(line)
    stats["input"] += 1
    dt = parse_date(d.get("publication_date", ""))
    if dt is None:
        stats["dropped_bad_date"] += 1
        continue
    if dt < START or dt > CUTOFF:
        stats["dropped_out_of_range"] += 1
        continue
    d["publication_date"] = dt.isoformat()
    d["text"] = clean_text(d["text"])
    d["title"] = re.sub(r"\s+", " ", d["title"]).strip()
    if len(d["text"]) < MIN_CHARS:
        stats["dropped_too_short"] += 1
        continue
    docs.append(d)

# 1. exact duplicates (same normalized text)
seen, unique = set(), []
for d in docs:
    h = hashlib.md5(d["text"].lower().encode("utf-8")).hexdigest()
    if h in seen:
        stats["dropped_exact_dup"] += 1
        continue
    seen.add(h)
    unique.append(d)

# 2. near duplicates (MinHash + LSH)
lsh = MinHashLSH(threshold=JACCARD, num_perm=128)
final = []
for i, d in enumerate(unique):
    m = minhash(d["text"])
    if lsh.query(m):
        stats["dropped_near_dup"] += 1
        continue
    lsh.insert(str(i), m)
    final.append(d)

with open(OUT, "w", encoding="utf-8") as f:
    for d in final:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")

by_year = collections.Counter(d["publication_date"][:4] for d in final)
by_source = collections.Counter(d["source_type"] for d in final)
stats["output"] = len(final)
report = {"stats": dict(stats), "by_year": dict(sorted(by_year.items())),
          "by_source_type": dict(by_source)}
json.dump(report, open(REPORT, "w"), indent=2)
print(json.dumps(report, indent=2))