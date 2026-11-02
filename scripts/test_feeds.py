import requests

feeds = {
    "OpenAI": "https://openai.com/news/rss.xml",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "Google Research": "https://research.google/blog/rss/",
    "Microsoft Research": "https://www.microsoft.com/en-us/research/feed/",
    "Meta AI": "https://ai.meta.com/blog/rss/",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
    "Anthropic": "https://www.anthropic.com/news",
}

for name, url in feeds.items():
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        print(name, r.status_code, len(r.text))
    except Exception as e:
        print(name, "FAILED", e)