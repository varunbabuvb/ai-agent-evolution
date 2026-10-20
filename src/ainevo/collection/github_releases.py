import json, time, yaml, os, requests
from datetime import date

cfg = yaml.safe_load(open("configs/sources.yaml", encoding="utf-8"))
repos = cfg["github_releases"]

headers = {"Accept": "application/vnd.github+json"}
token = os.getenv("GITHUB_TOKEN")
if token:
    headers["Authorization"] = f"Bearer {token}"

MAX_PER_REPO = 150
out = "data/raw/lab_blogs/github_releases_raw.jsonl"
total = 0

with open(out, "w", encoding="utf-8") as f:
    for repo in repos:
        url = f"https://api.github.com/repos/{repo}/releases"
        count, page = 0, 1
        while count < MAX_PER_REPO:
            resp = requests.get(url, headers=headers,
                                params={"per_page": 100, "page": page}, timeout=30)
            if resp.status_code != 200:
                print(repo, "error", resp.status_code, resp.text[:200])
                break
            releases = resp.json()
            if not releases:
                break
            for r in releases:
                if r.get("draft") or not r.get("published_at"):
                    continue
                body = (r.get("body") or "").strip()
                if len(body) < 50:
                    continue
                doc = {
                    "doc_id": f"gh_{repo.replace('/', '_')}_{r['id']}",
                    "title": f"{repo} {r.get('name') or r['tag_name']}",
                    "publication_date": r["published_at"][:10],
                    "source": repo,
                    "source_type": "release_notes",
                    "url": r["html_url"],
                    "text": body,
                    "retrieval_date": str(date.today()),
                    "query_used": url,
                    "metadata": {"tag": r["tag_name"],
                                 "prerelease": r.get("prerelease", False)},
                }
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
                count += 1
                if count >= MAX_PER_REPO:
                    break
            page += 1
            time.sleep(1)
        print(repo, count)
        total += count
print("total", total)