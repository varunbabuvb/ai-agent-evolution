"""SQLite storage for the corpus and the event database (owner: VV).

Tables
  documents       one row per cleaned corpus document (+ FTS5 index `documents_fts` for search)
  events          one row per normalised AI canon event (gold-labelled, extracted or seed)
  event_sources   which documents/URLs support each event (an event can have several sources)
  events_monthly  VIEW: events per month and category (feeds the monthly feature table)

Event record (the brief's fields). Loaders accept dicts / CSV / JSONL with these keys:
  event_id, date (YYYY-MM-DD or YYYY-MM), category, trigger, organization, model_agent, capability,
  action, autonomy_level (0-4 or NA), interaction, impact, phase_hint (1-7),
  confidence (0-1, model score), annotator_confidence (1-3, hand label), notes, classifier_split,
  and the sources as either `sources` = [{"doc_id":..., "url":...}] or `doc_id` + `source_url`.
Allowed values for category / capability / interaction come from configs/taxonomy.yaml, so a taxonomy
change never needs a schema change. Rows that break a rule are REJECTED with a reason, not loaded.

Run through scripts/build_db.py.
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path

import yaml

DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")
AUTONOMY = ("0", "1", "2", "3", "4", "NA")
ORIGINS = ("gold", "extracted", "seed")

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id             TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    publication_date   TEXT NOT NULL,            -- YYYY-MM-DD
    year               INTEGER NOT NULL,
    source             TEXT NOT NULL,            -- arXiv, OpenAI, langchain-ai/langchain, ...
    source_type        TEXT NOT NULL,            -- paper | lab_blog | release_notes | news | incident
    url                TEXT NOT NULL,
    text               TEXT NOT NULL,
    retrieval_date     TEXT,
    query_used         TEXT,
    text_source        TEXT,                     -- full_page | rss_summary (blogs only)
    llm_terms_found    INTEGER,                  -- 0/1 flag from cleaning
    low_signal_release INTEGER,                  -- 0/1 flag from cleaning
    metadata_json      TEXT
);
CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(publication_date);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(source_type);
CREATE INDEX IF NOT EXISTS idx_documents_year ON documents(year);

CREATE TABLE IF NOT EXISTS events (
    event_id             TEXT PRIMARY KEY,
    date                 TEXT NOT NULL,          -- YYYY-MM-DD or YYYY-MM
    month                TEXT NOT NULL,          -- YYYY-MM (derived; used by monthly features)
    category             TEXT NOT NULL,
    "trigger"            TEXT,
    organization         TEXT,
    model_agent          TEXT,
    capability           TEXT,
    action               TEXT,
    autonomy_level       TEXT CHECK (autonomy_level IS NULL OR autonomy_level IN ('0','1','2','3','4','NA')),
    interaction          TEXT,
    impact               TEXT,
    phase_hint           INTEGER CHECK (phase_hint IS NULL OR phase_hint BETWEEN 1 AND 7),
    confidence           REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    annotator_confidence INTEGER CHECK (annotator_confidence IS NULL OR annotator_confidence BETWEEN 1 AND 3),
    origin               TEXT NOT NULL CHECK (origin IN ('gold','extracted','seed')),
    classifier_split     TEXT CHECK (classifier_split IS NULL OR classifier_split IN ('train','holdout')),
    notes                TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_month ON events(month);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);

-- doc_id has no foreign key on purpose: seed-timeline events may have a URL but no corpus document.
CREATE TABLE IF NOT EXISTS event_sources (
    event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    doc_id   TEXT NOT NULL,
    url      TEXT,
    PRIMARY KEY (event_id, doc_id)
);

CREATE VIEW IF NOT EXISTS events_monthly AS
    SELECT month, category, COUNT(*) AS n_events FROM events GROUP BY month, category;
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title, text, content='documents', content_rowid='rowid', tokenize='porter unicode61'
);
"""


# ----------------------------------------------------------------------------- connection / schema
def connect(path) -> sqlite3.Connection:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fts_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp._fts_probe USING fts5(x)")
        conn.execute("DROP TABLE temp._fts_probe")
        return True
    except sqlite3.OperationalError:
        return False


def has_fts_table(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'documents_fts'").fetchone() is not None


def create_schema(conn: sqlite3.Connection) -> bool:
    """Create all tables. Returns True if the FTS5 search index could be created."""
    conn.executescript(SCHEMA)
    fts = fts_available(conn)
    if fts:
        conn.executescript(FTS_SCHEMA)
    conn.commit()
    return fts


def load_taxonomy(path="configs/taxonomy.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ----------------------------------------------------------------------------- documents
def _flag(v):
    return None if v is None else int(bool(v))


def _doc_row(d: dict) -> tuple:
    md = d.get("metadata") or {}
    pub = d["publication_date"]
    return (d["doc_id"], d["title"], pub, int(pub[:4]), d["source"], d["source_type"], d["url"], d["text"],
            d.get("retrieval_date"), d.get("query_used"), md.get("text_source"),
            _flag(md.get("llm_terms_found")), _flag(md.get("low_signal_release")),
            json.dumps(md, ensure_ascii=False))


def load_documents(conn: sqlite3.Connection, path) -> int:
    """Load a corpus JSONL (data/interim/corpus_v1_clean.jsonl). Re-loading replaces rows with the same doc_id."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(_doc_row(json.loads(line)))
    conn.executemany("INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    if has_fts_table(conn):
        conn.execute("INSERT INTO documents_fts(documents_fts) VALUES ('rebuild')")
        conn.commit()
    return len(rows)


def get_document(conn: sqlite3.Connection, doc_id: str):
    r = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    return dict(r) if r else None


def corpus_counts(conn: sqlite3.Connection) -> dict:
    """Counts for the Day-11 metadata report: per year x source_type and per source."""
    by_year = [dict(r) for r in conn.execute(
        "SELECT year, source_type, COUNT(*) AS n FROM documents GROUP BY year, source_type ORDER BY year, source_type")]
    by_source = [dict(r) for r in conn.execute(
        "SELECT source, COUNT(*) AS n FROM documents GROUP BY source ORDER BY n DESC")]
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    return {"total": total, "by_year_and_type": by_year, "by_source": by_source}


def search_documents(conn: sqlite3.Connection, query: str = "", source_types=None, sources=None,
                     year_from=None, year_to=None, limit: int = 50, offset: int = 0) -> list[dict]:
    """Corpus search for the Streamlit page. Every word must match (AND); punctuation and operators in the
    query are ignored, so user input can never break the SQL. Blank query = filters only, newest first."""
    where, params = [], []

    def in_clause(col, vals):
        vals = list(vals)
        where.append(f"{col} IN ({','.join('?' * len(vals))})")
        params.extend(vals)

    if source_types:
        in_clause("d.source_type", source_types)
    if sources:
        in_clause("d.source", sources)
    if year_from is not None:
        where.append("d.year >= ?")
        params.append(int(year_from))
    if year_to is not None:
        where.append("d.year <= ?")
        params.append(int(year_to))
    extra = (" AND " + " AND ".join(where)) if where else ""
    tokens = re.findall(r"\w+", query or "", re.UNICODE)

    if tokens and has_fts_table(conn):
        fts_q = " ".join(f'"{t}"' for t in tokens)
        sql = ("SELECT d.doc_id, d.title, d.publication_date, d.source, d.source_type, d.url, "
               "snippet(documents_fts, 1, '[', ']', ' ... ', 24) AS snippet "
               "FROM documents_fts JOIN documents d ON d.rowid = documents_fts.rowid "
               f"WHERE documents_fts MATCH ?{extra} ORDER BY rank LIMIT ? OFFSET ?")
        args = [fts_q] + params + [limit, offset]
    elif tokens:                                   # fallback when SQLite has no FTS5
        like = " AND ".join("(d.title LIKE ? OR d.text LIKE ?)" for _ in tokens)
        sql = ("SELECT d.doc_id, d.title, d.publication_date, d.source, d.source_type, d.url, "
               "substr(d.text, 1, 240) AS snippet FROM documents d "
               f"WHERE {like}{extra} ORDER BY d.publication_date DESC LIMIT ? OFFSET ?")
        args = [p for t in tokens for p in (f"%{t}%", f"%{t}%")] + params + [limit, offset]
    else:
        sql = ("SELECT d.doc_id, d.title, d.publication_date, d.source, d.source_type, d.url, "
               "substr(d.text, 1, 240) AS snippet FROM documents d "
               f"WHERE 1=1{extra} ORDER BY d.publication_date DESC LIMIT ? OFFSET ?")
        args = params + [limit, offset]
    return [dict(r) for r in conn.execute(sql, args)]


# ----------------------------------------------------------------------------- events
def _clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _to_int(v):
    s = _clean(v)
    if s is None:
        return None
    return int(float(s))


def _to_float(v):
    s = _clean(v)
    return None if s is None else float(s)


def validate_event(e: dict, tax: dict) -> list[str]:
    """Return a list of problems (empty list = the event can be loaded)."""
    problems = []
    cats = {c["id"] for c in tax["categories"]}
    if not _clean(e.get("event_id")):
        problems.append("event_id is missing")
    d = _clean(e.get("date"))
    if not d or not DATE_RE.match(d):
        problems.append(f"date {d!r} is not YYYY-MM-DD or YYYY-MM")
    if _clean(e.get("category")) not in cats:
        problems.append(f"category {_clean(e.get('category'))!r} is not in the taxonomy")
    cap = _clean(e.get("capability"))
    if cap and cap not in tax["capability_tags"]:
        problems.append(f"capability {cap!r} is not in the taxonomy")
    inter = _clean(e.get("interaction"))
    if inter and inter not in tax["interaction"]:
        problems.append(f"interaction {inter!r} is not in the taxonomy")
    aut = _clean(e.get("autonomy_level"))
    if aut and aut not in AUTONOMY:
        problems.append(f"autonomy_level {aut!r} must be 0-4 or NA")
    try:
        ph = _to_int(e.get("phase_hint"))
        if ph is not None and not 1 <= ph <= 7:
            problems.append("phase_hint must be 1-7")
    except ValueError:
        problems.append("phase_hint is not a number")
    try:
        c = _to_float(e.get("confidence"))
        if c is not None and not 0 <= c <= 1:
            problems.append("confidence must be between 0 and 1")
    except ValueError:
        problems.append("confidence is not a number")
    try:
        ac = _to_int(e.get("annotator_confidence"))
        if ac is not None and not 1 <= ac <= 3:
            problems.append("annotator_confidence must be 1-3")
    except ValueError:
        problems.append("annotator_confidence is not a number")
    return problems


def _event_sources(e: dict) -> list[tuple]:
    srcs = e.get("sources")
    if isinstance(srcs, str):                       # CSV cell holding JSON
        try:
            srcs = json.loads(srcs)
        except ValueError:
            srcs = None
    out = []
    if srcs:
        out = [(s["doc_id"], s.get("url")) for s in srcs if s.get("doc_id")]
    elif _clean(e.get("doc_id")):
        out = [(_clean(e["doc_id"]), _clean(e.get("source_url")) or _clean(e.get("url")))]
    return out


def insert_events(conn: sqlite3.Connection, events, tax: dict, origin: str = "gold"):
    """Insert events (replacing the same event_id). Returns (n_loaded, rejected) where rejected is a list of
    (event_id, [problems]). Invalid rows are skipped so one bad row never blocks the rest."""
    if origin not in ORIGINS:
        raise ValueError(f"origin must be one of {ORIGINS}")
    loaded, rejected = 0, []
    for e in events:
        problems = validate_event(e, tax)
        if problems:
            rejected.append((_clean(e.get("event_id")), problems))
            continue
        eid, date = _clean(e["event_id"]), _clean(e["date"])
        split = _clean(e.get("classifier_split"))
        conn.execute(
            'INSERT OR REPLACE INTO events (event_id, date, month, category, "trigger", organization, model_agent, '
            "capability, action, autonomy_level, interaction, impact, phase_hint, confidence, annotator_confidence, "
            "origin, classifier_split, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, date, date[:7], _clean(e["category"]), _clean(e.get("trigger")), _clean(e.get("organization")),
             _clean(e.get("model_agent")), _clean(e.get("capability")), _clean(e.get("action")),
             _clean(e.get("autonomy_level")), _clean(e.get("interaction")), _clean(e.get("impact")),
             _to_int(e.get("phase_hint")), _to_float(e.get("confidence")), _to_int(e.get("annotator_confidence")),
             origin, split, _clean(e.get("notes"))))
        conn.execute("DELETE FROM event_sources WHERE event_id = ?", (eid,))
        conn.executemany("INSERT OR IGNORE INTO event_sources (event_id, doc_id, url) VALUES (?,?,?)",
                         [(eid, doc, url) for doc, url in _event_sources(e)])
        loaded += 1
    conn.commit()
    return loaded, rejected


def load_events_file(conn: sqlite3.Connection, path, tax: dict, origin: str = "gold"):
    """Load events from a .csv (e.g. data/annotations/gold_events_v1.csv) or .jsonl file."""
    p = Path(path)
    if p.suffix.lower() == ".jsonl":
        with open(p, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
    else:
        with open(p, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    return insert_events(conn, rows, tax, origin)


def query_events(conn: sqlite3.Connection, categories=None, organizations=None, capabilities=None,
                 autonomy_levels=None, month_from=None, month_to=None, origins=None, limit=None) -> list[dict]:
    """Filtered events for the timeline / filters panel. Each event carries its `sources` list."""
    where, params = [], []

    def in_clause(col, vals):
        vals = list(vals)
        where.append(f"{col} IN ({','.join('?' * len(vals))})")
        params.extend(vals)

    if categories:
        in_clause("category", categories)
    if organizations:
        in_clause("organization", organizations)
    if capabilities:
        in_clause("capability", capabilities)
    if autonomy_levels:
        in_clause("autonomy_level", [str(a) for a in autonomy_levels])
    if origins:
        in_clause("origin", origins)
    if month_from:
        where.append("month >= ?")
        params.append(month_from)
    if month_to:
        where.append("month <= ?")
        params.append(month_to)
    sql = "SELECT * FROM events" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY date, event_id"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    events = [dict(r) for r in conn.execute(sql, params)]
    by_id = {e["event_id"]: e for e in events}
    for e in events:
        e["sources"] = []
    ids = list(by_id)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        q = ("SELECT s.event_id, s.doc_id, s.url, d.title FROM event_sources s "
             "LEFT JOIN documents d ON d.doc_id = s.doc_id "
             f"WHERE s.event_id IN ({','.join('?' * len(chunk))})")
        for r in conn.execute(q, chunk):
            by_id[r["event_id"]]["sources"].append({"doc_id": r["doc_id"], "url": r["url"], "title": r["title"]})
    return events


# ----------------------------------------------------------------------------- build everything
def build_database(db_path, corpus_path, events_path=None, taxonomy_path="configs/taxonomy.yaml",
                   events_origin: str = "gold") -> dict:
    """Rebuild the database from scratch (safe to re-run: same inputs give the same database)."""
    db = Path(db_path)
    if db.exists():
        try:
            db.unlink()
        except PermissionError as err:
            raise SystemExit(f"Cannot replace {db}: close anything that has it open (Streamlit, a DB viewer) "
                             f"or pause OneDrive sync, then run again. ({err})")
    conn = connect(db)
    fts = create_schema(conn)
    n_docs = load_documents(conn, corpus_path)
    summary = {"db": str(db), "fts_search": fts, "documents": n_docs, "events": 0, "rejected_events": []}
    if events_path:
        n, rejected = load_events_file(conn, events_path, load_taxonomy(taxonomy_path), events_origin)
        summary["events"], summary["rejected_events"] = n, rejected
    conn.close()
    return summary
