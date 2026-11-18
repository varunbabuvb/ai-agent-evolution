"""Shared database helpers for the Streamlit app (owner: VV). Read-only."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import streamlit as st  # noqa: E402

from ainevo.storage import db  # noqa: E402

DB_PATH = ROOT / "data" / "processed" / "events.db"
# The full corpus is kept out of Git; the repository carries a copy with secret-looking strings redacted.
CORPUS_CANDIDATES = [ROOT / "data" / "interim" / "corpus_v1_clean.jsonl",
                     ROOT / "data" / "deploy" / "corpus_public.jsonl"]
CORPUS_PATH = next((p for p in CORPUS_CANDIDATES if p.exists()), CORPUS_CANDIDATES[0])
GOLD_PATH = ROOT / "data" / "annotations" / "gold_events_v1.csv"
EXTRACTED_PATH = ROOT / "data" / "processed" / "extracted_events.csv"
TAXONOMY_PATH = ROOT / "configs" / "taxonomy.yaml"


@st.cache_resource(show_spinner="Building the database from the corpus (first start only, about a minute)...")
def build_if_missing() -> bool:
    """Build events.db from the corpus when it does not exist (for example on Streamlit Cloud, where the
    generated database is not in the repository). Returns True if a database is available."""
    if DB_PATH.exists():
        return True
    if not CORPUS_PATH.exists():
        return False
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db.build_database(DB_PATH, CORPUS_PATH, GOLD_PATH if GOLD_PATH.exists() else None, str(TAXONOMY_PATH))
    if EXTRACTED_PATH.exists():
        conn = db.connect(DB_PATH)
        try:
            db.load_events_file(conn, EXTRACTED_PATH, db.load_taxonomy(str(TAXONOMY_PATH)), origin="extracted")
        finally:
            conn.close()
    return DB_PATH.exists()


def db_ready() -> bool:
    return DB_PATH.exists()


def require_db() -> None:
    """Make sure the database exists (building it if the corpus is present), else stop with a clear message."""
    if not db_ready():
        build_if_missing()
    if not db_ready():
        st.error("Database not found and the corpus file is missing. From the repo root run:  "
                 "py -3.13 scripts/build_db.py --events data/annotations/gold_events_v1.csv")
        st.stop()


def open_conn():
    return db.connect(DB_PATH)


@st.cache_data(show_spinner=False)
def counts() -> dict:
    conn = open_conn()
    try:
        return db.corpus_counts(conn)
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def filter_options() -> dict:
    conn = open_conn()
    try:
        types = [r[0] for r in conn.execute("SELECT DISTINCT source_type FROM documents ORDER BY 1")]
        sources = [r[0] for r in conn.execute(
            "SELECT source FROM documents GROUP BY source ORDER BY COUNT(*) DESC")]
        y0, y1 = conn.execute("SELECT MIN(year), MAX(year) FROM documents").fetchone()
        n_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        return {"source_types": types, "sources": sources, "year_min": y0, "year_max": y1,
                "n_events": n_events}
    finally:
        conn.close()
