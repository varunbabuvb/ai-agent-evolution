"""Small, polite web helpers shared by collectors: robots.txt check, main-text and date extraction."""
from __future__ import annotations
import json, re, urllib.robotparser
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (academic NLP project)"
_ROBOTS: dict[str, urllib.robotparser.RobotFileParser] = {}


def _load_robots(host: str) -> urllib.robotparser.RobotFileParser:
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = requests.get(f"https://{host}/robots.txt", headers={"User-Agent": UA}, timeout=15)
        if r.status_code == 200:
            rp.parse(r.text.splitlines())
        elif r.status_code in (404, 410):
            rp.allow_all = True
        else:
            rp.disallow_all = True     # cannot read the rules -> stay on the safe side
    except requests.RequestException:
        rp.disallow_all = True
    return rp


def allowed(url: str) -> bool:
    host = urlparse(url).netloc
    if host not in _ROBOTS:
        _ROBOTS[host] = _load_robots(host)
    return _ROBOTS[host].can_fetch(UA, url)


def fetch(url: str, timeout: int = 30) -> str | None:
    """Return page HTML, or None if robots.txt forbids it or the request fails."""
    if not allowed(url):
        return None
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        return r.text if r.status_code == 200 else None
    except requests.RequestException:
        return None


def extract_main_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
        tag.decompose()
    node = soup.find("article") or soup.find("main") or soup.body or soup
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def extract_meta(html: str) -> dict:
    """title + ISO publication date (YYYY-MM-DD) from meta tags, JSON-LD or <time>. Missing -> None (never guessed)."""
    soup = BeautifulSoup(html, "html.parser")
    title = None
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()
    raw = None
    m = soup.find("meta", property="article:published_time")
    if m and m.get("content"):
        raw = m["content"]
    if not raw:
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(s.string or "")
            except json.JSONDecodeError:
                continue
            for item in (data if isinstance(data, list) else [data]):
                if isinstance(item, dict) and item.get("datePublished"):
                    raw = item["datePublished"]; break
            if raw:
                break
    if not raw:
        t = soup.find("time", attrs={"datetime": True})
        raw = t["datetime"] if t else None
    mt = re.match(r"\d{4}-\d{2}-\d{2}", raw or "")
    return {"title": title, "date": mt.group(0) if mt else None}


def parse_sitemap(xml_text: str) -> list[str]:
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml_text)
