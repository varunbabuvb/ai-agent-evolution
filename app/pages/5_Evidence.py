"""Evidence page: one event with its sources and source text (owner: VV)."""
import streamlit as st

from components.data import open_conn, require_db
from ainevo.storage import db

st.set_page_config(page_title="Evidence", layout="wide")
st.title("Evidence")
require_db()


@st.cache_data(show_spinner=False)
def all_events() -> list:
    conn = open_conn()
    try:
        return db.query_events(conn)
    finally:
        conn.close()


events = sorted(all_events(), key=lambda e: e["date"] or "", reverse=True)
if not events:
    st.warning("No events in the database yet.")
    st.stop()

ids = [e["event_id"] for e in events]
by_id = {e["event_id"]: e for e in events}
start = st.session_state.get("evidence_event")
index = ids.index(start) if start in ids else 0


def fmt(i: str) -> str:
    e = by_id[i]
    return f"{e['date']} | {e['category']} | {(e.get('model_agent') or e.get('trigger') or i)[:60]}"


pick = st.selectbox("Event", ids, index=index, format_func=fmt)
st.session_state["evidence_event"] = pick
ev = by_id[pick]

st.subheader(f"{ev['category']}, {ev['date']}")
left, right = st.columns(2)
with left:
    for k in ("organization", "model_agent", "capability", "autonomy_level", "interaction", "origin"):
        st.markdown(f"**{k}:** {ev.get(k) or 'n/a'}")
with right:
    for k in ("trigger", "action", "impact", "notes"):
        if ev.get(k):
            st.markdown(f"**{k}:** {ev[k]}")
    if ev.get("confidence") is not None:
        st.markdown(f"**confidence:** {ev['confidence']}")

st.subheader("Source documents")
if not ev["sources"]:
    st.caption("No linked source documents for this event.")
for s in ev["sources"]:
    conn = open_conn()
    try:
        doc = db.get_document(conn, s["doc_id"])
    finally:
        conn.close()
    title = (doc["title"] if doc else None) or s.get("title") or s["doc_id"]
    with st.expander(title):
        if doc:
            st.markdown(f"**{doc['source']}**, {doc['publication_date']}  \n{doc['url']}")
            trig = ev.get("trigger") or ""
            text = doc["text"]
            if trig and trig.lower() in text.lower():
                i = text.lower().index(trig.lower())
                st.markdown("**Trigger in context:**")
                st.info(text[max(0, i - 200): i + len(trig) + 300])
            st.text_area("Full text", text, height=260, key=f"t_{s['doc_id']}")
        else:
            st.caption(f"Document {s['doc_id']} not found in the corpus table.")
