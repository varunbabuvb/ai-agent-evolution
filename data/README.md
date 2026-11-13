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

## Corpus v1 (frozen candidate)

File: data/interim/corpus_v1_clean.jsonl (not committed; share through the common drive)
SHA256: 48d3d61e15963f13a78a3b7e030d7882fa9b4a75e3ce3d4b78d2560208a88b09
Documents: 3,018 (papers 984, lab_blog 1,308, release_notes 726), 2017 to Sep 2026.
News and incident documents are collected separately (Saketh) and are not in this file.

| year | lab_blog | paper | release_notes | total |
|------|----------|-------|---------------|-------|
| 2017 | 27 | 41 | 0 | 68 |
| 2018 | 18 | 42 | 0 | 60 |
| 2019 | 18 | 41 | 0 | 59 |
| 2020 | 16 | 42 | 0 | 58 |
| 2021 | 43 | 42 | 0 | 85 |
| 2022 | 92 | 82 | 0 | 174 |
| 2023 | 161 | 153 | 135 | 449 |
| 2024 | 225 | 192 | 176 | 593 |
| 2025 | 337 | 195 | 222 | 754 |
| 2026 | 371 | 154 | 193 | 718 |

Top sources: arXiv 984, OpenAI 613, Hugging Face 434, langchain-ai/langchain 341, crewAIInc/crewAI 175,
Anthropic 149, AutoGPT 115, microsoft/autogen 95, Google DeepMind 61, Google Research 51.

Known gaps: 2017 to 2021 are below the planned 80 documents per year, 2022 is far below 350,
there are no Meta, Mistral, DeepSeek or Qwen sources, and Microsoft Research has only 10 documents.
Documents dated October 2026 are excluded from forecasting by the cutoff in configs/split.yaml.
Caps used in cleaning: OpenAI 15 per month, Hugging Face 8 per month, release notes 8 per repo per month.

## Event database

Built by `py -3.13 scripts/build_db.py --events data/annotations/gold_events_v1.csv` into
data/processed/events.db (git-ignored). Current contents: 3,018 documents and 224 gold events.
Full counts are in docs/corpus_report.txt.