# Data dictionary and corpus report

Raw collections (`data/raw/`) are git-ignored; share them through the team drive. Re-download with `make data`, then `make pipeline`.

## Document fields (every row of corpus_v1_clean.jsonl)
| field | meaning |
|---|---|
| doc_id | stable id = type prefix + first 10 hex of md5(url); does not change between runs |
| title, text | cleaned title and body (HTML, raw URLs and boilerplate removed; whitespace collapsed) |
| publication_date | ISO `YYYY-MM-DD` |
| source, source_type | e.g. OpenAI / arXiv / repo name; `paper`, `lab_blog`, `release_notes` |
| url | original page |
| retrieval_date, query_used | when and how it was collected |
| metadata | source extras, plus advisory flags `low_signal_release` (tiny / dependency-bump release notes) and `llm_terms_found` (mentions LLM/agent-era terms). Flags never delete a document. |

## corpus_v1_clean.jsonl: 1865 documents (cutoff 2026-09-30)
| year | papers | lab_blog | release_notes | total |
|---|---|---|---|---|
| 2017 | 79 | 13 | 0 | 92 |
| 2018 | 80 | 9 | 0 | 89 |
| 2019 | 80 | 16 | 0 | 96 |
| 2020 | 80 | 4 | 0 | 84 |
| 2021 | 80 | 8 | 0 | 88 |
| 2022 | 120 | 15 | 0 | 135 |
| 2023 | 120 | 25 | 36 | 181 |
| 2024 | 120 | 55 | 53 | 228 |
| 2025 | 120 | 108 | 120 | 348 |
| 2026 | 115 | 135 | 274 | 524 |

By source:
- arXiv: 994
- OpenAI: 369
- crewAIInc/crewAI: 142
- langchain-ai/langchain: 131
- Significant-Gravitas/AutoGPT: 115
- microsoft/autogen: 95
- Google DeepMind: 19

Cleaning report: see `data/interim/cleaning_report.json` (1,983 in -> 1,865 out: 32 outside 2017-01..cutoff, 81 under 100 characters, 1 exact and 4 near duplicates).
Flags: 72 low-signal release notes; 1077 documents with no LLM/agent-era term (mostly 2017-2022 papers).

## Known gaps in this version (collected before the fixes; re-run `make data` to close them)
- OpenAI posts per month since 2025 (old per-YEAR cap kept the earliest posts): 2025-01:4, 2025-02:7, 2025-03:7, 2025-04:12, 2025-05:8, 2025-06:6, 2025-07:9, 2025-08:22, 2025-09:24, 2025-10:7, 2025-11:0, 2025-12:0, 2026-01:30, 2026-02:26, 2026-03:25, 2026-04:37, 2026-05:0, 2026-06:0, 2026-07:0, 2026-08:0, 2026-09:0
- Lab-blog text is mostly the RSS summary (median about 150 characters); the new collector fetches full pages.
- No Anthropic, Meta, Microsoft, Mistral, DeepSeek, Qwen documents; Google DeepMind only from Dec 2025; no news or incident data (Saketh).
- GitHub releases: langchain only from May 2026, crewAI from Jul 2025, autogen stops Sep 2025 (old 150-release cap).
- Lowest-volume months since 2022 (documents): [('2022-04', 4), ('2024-09', 5), ('2022-02', 7), ('2022-08', 7), ('2023-08', 8)]

## Checksums (sha256)
- corpus_v1.jsonl (raw merge, as received): `1b8a8fa73b52ea8a391466100772cba2c84d43ec860432affcc74c89bfb1db2c`
- corpus_v1_clean.jsonl: `62fb8ac193a29c07a0ec84dd19cdddccffa96270374d76d52ddd7abc1ee57448`
