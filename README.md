# ai-agent-evolution
NLP-based AI canon-event extraction, evolution timeline and forecasting of AI-agent development (course project, 4 members).
See `docs/` for the brief-based plan, `docs/annotation_guidelines.md` for labelling rules and `docs/decisions.md` for team decisions.

## Setup
```
pip install -r requirements.txt
cp .env.example .env        # add GITHUB_TOKEN (optional, raises the GitHub API rate limit)
```
## Run
| command | what it does |
|---|---|
| `make data` | collect arXiv, lab blogs, GitHub releases into `data/raw/` (needs internet; raw data is git-ignored) |
| `make pipeline` | merge + clean + deduplicate -> `data/interim/corpus_v1_clean.jsonl` and `cleaning_report.json` |
| `make test` | run the unit tests |
| `make forecast`, `make app` | Week 3 (placeholders) |

Collectors respect robots.txt where they fetch web pages, log `retrieval_date` and `query_used`, and never guess a missing date.
Data dictionary and corpus statistics: `data/README.md`. Branches: `feat/<initials>-<task>`, PRs need one review.
