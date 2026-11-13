"""Event timeline with filters (owner: VV)."""
import pandas as pd
import plotly.express as px
import streamlit as st

from components.data import ROOT, open_conn, require_db
from ainevo.storage import db

st.set_page_config(page_title="Timeline", layout="wide")
st.title("AI-bot evolution timeline")
require_db()


@st.cache_data(show_spinner=False)
def taxonomy() -> dict:
    return db.load_taxonomy(str(ROOT / "configs" / "taxonomy.yaml"))


@st.cache_data(show_spinner=False)
def options() -> dict:
    conn = open_conn()
    try:
        def distinct(col):
            return [r[0] for r in conn.execute(
                f"SELECT DISTINCT {col} FROM events WHERE {col} IS NOT NULL AND {col} != '' ORDER BY 1")]
        lo, hi = conn.execute("SELECT MIN(month), MAX(month) FROM events").fetchone()
        return {"organization": distinct("organization"), "capability": distinct("capability"),
                "autonomy": distinct("autonomy_level"), "origin": distinct("origin"),
                "months": [r[0] for r in conn.execute("SELECT DISTINCT month FROM events ORDER BY 1")],
                "lo": lo, "hi": hi}
    finally:
        conn.close()


tax, opt = taxonomy(), options()
cats = [c["id"] for c in tax["categories"]]
precedence = tax.get("category_precedence", cats)

if not opt["months"]:
    st.warning("No events in the database yet. Run build_db.py with --events.")
    st.stop()

with st.sidebar:
    st.header("Filters")
    f_cat = st.multiselect("Category", cats)
    f_org = st.multiselect("Organization", opt["organization"])
    f_cap = st.multiselect("Capability", opt["capability"])
    f_aut = st.multiselect("Autonomy level", opt["autonomy"])
    f_org_origin = st.multiselect("Origin", opt["origin"])
    m0, m1 = st.select_slider("Months", options=opt["months"], value=(opt["lo"], opt["hi"]))

conn = open_conn()
try:
    events = db.query_events(conn, categories=f_cat or None, organizations=f_org or None,
                             capabilities=f_cap or None, autonomy_levels=f_aut or None,
                             month_from=m0, month_to=m1, origins=f_org_origin or None)
finally:
    conn.close()

st.write(f"{len(events)} event(s)")
if not events:
    st.warning("No events match these filters.")
    st.stop()

df = pd.DataFrame(events)
df["when"] = pd.to_datetime(df["date"], errors="coerce")
df["label"] = df["model_agent"].fillna("").where(df["model_agent"].fillna("") != "", df["trigger"].fillna(""))
df["n_sources"] = df["sources"].apply(len)

fig = px.scatter(
    df, x="when", y="category", color="category",
    category_orders={"category": precedence},
    hover_name="label",
    hover_data={"organization": True, "capability": True, "autonomy_level": True,
                "trigger": True, "when": False, "category": False},
)
fig.update_traces(marker=dict(size=11, opacity=0.8))
fig.update_layout(height=480, showlegend=False, xaxis_title=None, yaxis_title=None,
                  margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

st.subheader("Events per month")
monthly = df.groupby(["month", "category"]).size().reset_index(name="n_events")
st.plotly_chart(px.bar(monthly, x="month", y="n_events", color="category", height=300),
                use_container_width=True)

st.subheader("Event details and sources")
show = df[["date", "category", "organization", "model_agent", "capability", "autonomy_level",
           "trigger", "n_sources", "event_id"]]
st.dataframe(show, use_container_width=True, hide_index=True)

pick = st.selectbox("Open an event", df["event_id"].tolist(),
                    format_func=lambda i: f"{i}  |  {df.loc[df.event_id == i, 'label'].iloc[0][:70]}")
ev = next(e for e in events if e["event_id"] == pick)
st.markdown(f"**{ev['category']}**, {ev['date']}, {ev.get('organization') or 'unknown organization'}")
for k in ("trigger", "action", "impact", "interaction", "notes"):
    if ev.get(k):
        st.markdown(f"**{k}:** {ev[k]}")
if ev["sources"]:
    st.markdown("**Sources**")
    for s in ev["sources"]:
        st.markdown(f"- {s.get('title') or s['doc_id']}  \n  {s.get('url') or ''}")
else:
    st.caption("No linked source documents for this event.")
