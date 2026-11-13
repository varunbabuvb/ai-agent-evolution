"""AI-Bot Evolution app: home page (owner: VV).  Run from the repo root:  py -3.13 -m streamlit run app/streamlit_app.py"""
import pandas as pd
import streamlit as st

from components.data import counts, filter_options, require_db

st.set_page_config(page_title="AI-Bot Evolution", layout="wide")
st.title("AI-Bot Evolution: canon events and forecast")
st.caption("NLP-based canon event extraction from AI news and technical reports. "
           "Results describe reported developments, not guaranteed predictions.")

require_db()
c, opts = counts(), filter_options()

a, b, d = st.columns(3)
a.metric("Documents", f"{c['total']:,}")
b.metric("Events in database", f"{opts['n_events']:,}")
d.metric("Years covered", f"{opts['year_min']}-{opts['year_max']}")

st.subheader("Corpus by year and source type")
df = pd.DataFrame(c["by_year_and_type"]).pivot_table(
    index="year", columns="source_type", values="n", aggfunc="sum", fill_value=0)
df["total"] = df.sum(axis=1)
st.dataframe(df, use_container_width=True)

st.subheader("Top sources")
st.dataframe(pd.DataFrame(c["by_source"]).head(15), use_container_width=True, hide_index=True)

st.info("Use the sidebar pages. Corpus search is ready; Timeline, Phases, Forecast and Evidence are added as the "
        "team's outputs arrive.")
