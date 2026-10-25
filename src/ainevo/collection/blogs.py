import json, time, requests, feedparser
from datetime import date, datetime
from bs4 import BeautifulSoup

FEEDS = {
    "OpenAI": "https://openai.com/news/rss.xml",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "Google Research": "https://research.google/blog/rss/",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (academic NLP project)"}
OUT = "data/raw/lab_blogs/blogs_raw.jsonl"


def clean_html(s):
    return BeautifulSoup(s or "", "html.parser").get_text(" ", strip=True)


def entry_date(e):
    t = e.get("published_parsed") or e.get("updated_parsed")
    return datetime(*t[:6]).date().isoformat() if t else None


total = 0
with open(OUT, "w", encoding="utf-8") as f:
    for name, url in FEEDS.items():
        resp = requests.get(url, headers=HEADERS, timeout=30)
        feed = feedparser.parse(resp.content)
        count = 0
        for e in feed.entries:
            d = entry_date(e)
            text = clean_html(e.get("content", [{}])[0].get("value")
                              or e.get("summary", ""))
            if not d or len(text) < 50:
                continue
            doc = {
                "doc_id": f"blog_{name.replace(' ', '_')}_{abs(hash(e.link)) % 10**10}",
                "title": e.get("title", "").strip(),
                "publication_date": d,
                "source": name,
                "source_type": "lab_blog",
                "url": e.link,
                "text": text,
                "retrieval_date": str(date.today()),
                "query_used": url,
                "metadata": {"tags": [t.term for t in e.get("tags", [])]},
            }
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
            count += 1
        print(name, count)
        total += count
        time.sleep(2)
print("total", total)