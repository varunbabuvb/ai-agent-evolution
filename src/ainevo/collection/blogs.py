"""Lab-blog collector: RSS feeds + sitemap sources from configs/sources.yaml.
Run from the repo root:  PYTHONPATH=src python -m ainevo.collection.blogs
RSS summaries are often 1-2 sentences, so short entries are upgraded to the full page text (robots.txt respected)."""
import json, os, time, hashlib
from datetime import date, datetime
import feedparser, requests, yaml
from bs4 import BeautifulSoup
from ainevo.collection import web_utils as W

CFG = yaml.safe_load(open("configs/sources.yaml", encoding="utf-8"))["lab_blogs"]
OUT = "data/raw/lab_blogs/blogs_raw.jsonl"
MIN_FULL = CFG.get("full_text_min_chars", 400)


def clean_html(s):
    return BeautifulSoup(s or "", "html.parser").get_text(" ", strip=True)


def entry_date(e):
    t = e.get("published_parsed") or e.get("updated_parsed")
    return datetime(*t[:6]).date().isoformat() if t else None


def make_doc(name, title, d, url, text, query, meta):
    return {"doc_id": f"blog_{name.replace(' ', '_')}_{hashlib.md5(url.encode()).hexdigest()[:10]}",  # stable across runs
            "title": title, "publication_date": d, "source": name, "source_type": "lab_blog", "url": url,
            "text": text, "retrieval_date": str(date.today()), "query_used": query, "metadata": meta}


def collect_rss(name, url, out):
    resp = requests.get(url, headers={"User-Agent": W.UA}, timeout=30)
    feed = feedparser.parse(resp.content)
    n = 0
    for e in feed.entries:
        d = entry_date(e)
        text = clean_html(e.get("content", [{}])[0].get("value") or e.get("summary", ""))
        src = "rss_summary"
        if len(text) < MIN_FULL:
            html = W.fetch(e.link)
            if html:
                full = W.extract_main_text(html)
                if len(full) > len(text):
                    text, src = full, "full_page"
            time.sleep(2)
        if not d or len(text) < 50:
            continue
        out.write(json.dumps(make_doc(name, e.get("title", "").strip(), d, e.link, text, url,
                                      {"tags": [t.term for t in e.get("tags", [])], "text_source": src}),
                             ensure_ascii=False) + "\n")
        n += 1
    return n


def collect_sitemap(spec, out):
    xml = W.fetch(spec["sitemap"])
    if not xml:
        print(spec["name"], "sitemap not reachable or not allowed by robots.txt"); return 0
    n = 0
    for url in W.parse_sitemap(xml):
        if spec["url_contains"] not in url:
            continue
        html = W.fetch(url); time.sleep(2)
        if not html:
            continue
        meta, text = W.extract_meta(html), W.extract_main_text(html)
        if not meta["date"] or len(text) < 200:       # no date -> skip, never guess
            continue
        out.write(json.dumps(make_doc(spec["name"], meta["title"] or url, meta["date"], url, text, spec["sitemap"],
                                      {"text_source": "full_page"}), ensure_ascii=False) + "\n")
        n += 1
    return n


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    total = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for name, url in CFG["rss"].items():
            c = collect_rss(name, url, f); print(name, c); total += c; time.sleep(2)
        for spec in CFG.get("sitemaps", []):
            c = collect_sitemap(spec, f); print(spec["name"], c); total += c
    print("total", total)
