from ainevo.collection import web_utils as W

HTML = """<html><head><title>T</title><meta property="og:title" content="Intro Agent">
<meta property="article:published_time" content="2025-03-04T10:00:00Z"></head>
<body><nav>menu</nav><article><p>Agents can plan.</p><p>They use tools.</p></article><footer>foot</footer></body></html>"""


def test_extract():
    assert W.extract_main_text(HTML) == "Agents can plan. They use tools."
    assert W.extract_meta(HTML) == {"title": "Intro Agent", "date": "2025-03-04"}


def test_missing_date_is_none():
    assert W.extract_meta("<html><body><p>x</p></body></html>")["date"] is None


def test_json_ld_date():
    h = '<script type="application/ld+json">{"datePublished":"2024-01-09T00:00:00Z"}</script>'
    assert W.extract_meta(h)["date"] == "2024-01-09"


def test_robots(monkeypatch):
    class R:
        def __init__(s, c, t): s.status_code, s.text = c, t
    W._ROBOTS.clear()
    monkeypatch.setattr(W.requests, "get", lambda *a, **k: R(200, "User-agent: *\nDisallow: /private"))
    assert W.allowed("https://a.com/news/x") and not W.allowed("https://a.com/private/x")
    W._ROBOTS.clear(); monkeypatch.setattr(W.requests, "get", lambda *a, **k: R(404, ""))
    assert W.allowed("https://b.com/x")
    W._ROBOTS.clear(); monkeypatch.setattr(W.requests, "get", lambda *a, **k: R(500, ""))
    assert not W.allowed("https://c.com/x")


def test_sitemap():
    assert W.parse_sitemap("<urlset><url><loc> https://a.com/news/1 </loc></url><url><loc>https://a.com/x</loc></url></urlset>") == ["https://a.com/news/1", "https://a.com/x"]
