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


def db_ready() -> bool:
    return DB_PATH.exists()


def require_db() -> None:
    """Stop the page with a clear message if the database has not been built."""
    if not db_ready():
        st.error("Database not found. From the repo root run:  "
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
