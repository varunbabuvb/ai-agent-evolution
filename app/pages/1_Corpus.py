"""Corpus search page (owner: VV)."""
import streamlit as st

from components.data import filter_options, open_conn, require_db
from ainevo.storage import db

st.set_page_config(page_title="Corpus search", layout="wide")
st.title("Corpus search")
require_db()
opts = filter_options()

with st.sidebar:
    st.header("Filters")
    types = st.multiselect("Source type", opts["source_types"])
    sources = st.multiselect("Source", opts["sources"])
    y0, y1 = st.slider("Years", opts["year_min"], opts["year_max"], (opts["year_min"], opts["year_max"]))
    limit = st.select_slider("Max results", [25, 50, 100, 200], value=50)

query = st.text_input("Search title and text (every word must match)", placeholder="e.g. computer use agent")

conn = open_conn()
try:
    rows = db.search_documents(conn, query=query, source_types=types or None, sources=sources or None,
                               year_from=y0, year_to=y1, limit=limit)
finally:
    conn.close()

st.write(f"{len(rows)} result(s)" + (f" (showing the first {limit})" if len(rows) == limit else ""))
if not rows:
    st.warning("No documents match. Try fewer words or wider filters.")

for r in rows:
    with st.expander(f"{r['publication_date']}  |  {r['source']}  |  {r['title']}"):
        st.markdown(f"**Type:** {r['source_type']}  \n**Link:** {r['url']}")
        st.markdown(f"*{r['snippet']}*")
        if st.button("Show full text", key=f"full_{r['doc_id']}"):
            conn = open_conn()
            try:
                doc = db.get_document(conn, r["doc_id"])
            finally:
                conn.close()
            st.text_area("Full text", doc["text"], height=300, key=f"txt_{r['doc_id']}")
