# Review of Week 1 data work: what was fixed, what still needs a re-run

Status key: **DONE** = changed and tested offline here. **CODE FIXED, NOT RUN LIVE** = the code was changed but the collectors could not reach arXiv / OpenAI / Anthropic / GitHub from the review workspace, so Varun must run `make data` on a machine with internet and check the counts. **OPEN** = not done.

| # | Problem found | Status | What changed |
|---|---|---|---|
| 1 | Uploaded corpus was the uncleaned merge (2016 and Oct-2026 docs, 51-char texts) | DONE | `corpus_v1_clean.jsonl` produced: 1,983 -> 1,865 documents. Cutoff now read from `configs/split.yaml`. |
| 2 | OpenAI cap of 120 per YEAR dropped the end of each year (no OpenAI posts Nov-Dec 2025 or May-Sep 2026) | CODE FIXED, NOT RUN LIVE | Cap is now 15 per MONTH (`build_corpus.py`, tested). Missing months can only be filled by re-collecting. |
| 3 | arXiv queries pulled classical multi-agent RL / robotics papers | CODE FIXED, NOT RUN LIVE | 2023+ queries need an LLM term AND an agent term; 2017-2022 use language-model-era terms; per-year targets in `sources.yaml` (query text unit-tested, results not checked). The existing 994 papers are only flagged (`llm_terms_found`), not removed. |
| 4 | Blog text was only the RSS summary (median ~150 chars) | CODE FIXED, NOT RUN LIVE | Entries under 400 chars are upgraded to full page text via `web_utils.py` (robots.txt respected, tested on sample HTML). |
| 5 | Sources missing (Anthropic, Microsoft, Meta, Mistral, DeepSeek, Qwen) | PARTLY | Added Microsoft Research RSS and an Anthropic sitemap collector (skips pages without a publication date). Meta, Mistral, DeepSeek, Qwen, MCP/A2A are listed as TODO in `sources.yaml`. Anthropic and Microsoft entries were not tested against the live sites. |
| 6 | GitHub 150-release cap; noisy release notes | CODE FIXED, NOT RUN LIVE (cap); DONE (noise flag) | `max_per_repo` now 1000 (config). 72 low-signal release notes are flagged `low_signal_release`, not deleted. |
| 7 | Year balance below plan (2022-2024) | OPEN | Depends on re-running the collectors; check `data/README.md` counts afterwards. |
| 8 | Repo gaps | DONE | Makefile fixed (tabs), `scripts/run_*.py` added, `requirements.txt` pinned and complete, README, `data/README.md`, CODEOWNERS template, 18 unit tests. LICENSE not added (team must choose). CODEOWNERS needs the real GitHub usernames. |
| 9 | Boilerplate regex deleted the rest of a document | DONE | Patterns now stop at the end of the sentence (tested). |
| 10 | No robots.txt check | DONE for page fetches | `web_utils.allowed()`; unreadable robots.txt means "do not fetch". arXiv and GitHub use their official APIs. |

After re-running: `make data && make pipeline && make test`, compare the new `cleaning_report.json` and `data/README.md` counts, then tell Harshita before the corpus is frozen (her `doc_id`s stay valid because ids come from the URL).
