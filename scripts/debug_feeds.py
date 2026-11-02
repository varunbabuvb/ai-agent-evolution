import requests, feedparser

for name, url in {
    "Google Research": "https://research.google/blog/rss/",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
}.items():
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    feed = feedparser.parse(r.content)
    print(name, "entries:", len(feed.entries))
    if feed.entries:
        e = feed.entries[0]
        print("  keys:", list(e.keys()))
        print("  published_parsed:", e.get("published_parsed"))
        print("  updated_parsed:", e.get("updated_parsed"))
        print("  summary length:", len(e.get("summary", "")))