# Decision log
Format: ID · date · decision · reason · owner · approved by.

- **D-001 · 2026-11-01 · Scope rule added: classical RL/robotics papers are `no_off_topic`.**
  Reason: in corpus_v1 381 of the 520 arXiv papers dated 2017–2022 match reinforcement-learning/robotics/path-finding keywords and mention no language-model terms (keyword check; only 2 of the 520 mention LLM-style terms; the rest match neither pattern and need a manual look). Even in 2023, 86 of 120 papers are of this kind. Labelling them as events would put non-LLM work on an LLM-agent timeline. Owner: HA. Approval needed from all four (affects Varun's collectors and Saketh's timeline).
- **D-002 · 2026-11-01 · Provisional data cutoff = Sep 2026** (`configs/split.yaml`, `locked: false`).
  Reason: corpus_v1 has 29 docs dated Oct 2026; incomplete months are dropped. Locked at corpus freeze. Owner: HA.
- **D-003 · 2026-11-01 · Annotation pool drawn from corpus_v1 with a fixed seed** (`scripts/make_annotation_pool.py`).
  Stratified by year and source type; release notes under 300 characters excluded; post-2022 papers must mention LLM/agent terms. Early years (2017–2021) rely mainly on lab blogs and the future seed timeline. Owner: HA.
- **D-004 · 2026-11-01 · Tie-break precedence for categories** is stored in `taxonomy.yaml` and reused as the tie-break for the monthly dominant-category label. Owner: HA.
- **D-005 · 2026-11-01 · Cleaning adds advisory flags instead of deleting** (`low_signal_release`, `llm_terms_found` in `metadata`). Reason: deleting by keyword would silently change the corpus; downstream steps can filter. Owner: Varun (review: HA).
- **D-006 · 2026-11-01 · OpenAI cap is per month (15), not per year (120).** Reason: the per-year cap kept the earliest posts and removed the end of 2025 and the months after Apr 2026, which fall in the forecasting test block. Owner: Varun.
- **D-007 · 2026-11-01 · Annotation pool is drawn from `corpus_v1_clean.jsonl`** (replaces the raw file used in D-003). `doc_id` is md5(url), so labels stay valid if the corpus is re-collected. Owner: HA.
