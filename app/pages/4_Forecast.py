"""Forecast panel with evidence links (owner: VV).

Reads data/processed/forecast_latest.json when it exists (written by the forecasting code).
Until then it shows a clearly labelled most-frequent BASELINE computed from the event database,
not a model forecast.
"""
import json
from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st

from components.data import ROOT, open_conn, require_db
from ainevo.storage import db

st.set_page_config(page_title="Forecast", layout="wide")
st.title("Forecast: dominant event category next month")
require_db()

FORECAST = ROOT / "data" / "processed" / "forecast_latest.json"
EXAMPLE = {
    "forecast_month": "2026-10", "model": "gradient_boosting", "predicted_category": "agentic_development",
    "probabilities": {"agentic_development": 0.4, "multi_agent_coordination": 0.3},
    "baselines": {"persistence": "...", "most_frequent": "...", "moving_average": "..."},
    "metrics": {"accuracy": 0.0, "macro_f1": 0.0, "test_months": 21},
    "history": [{"month": "2025-01", "actual": "...", "predicted": "..."}],
    "top_features": [{"feature": "multi_agent_share_3m", "importance": 0.0}],
    "supporting_event_ids": ["EV-..."],
}


@st.cache_data(show_spinner=False)
def taxonomy() -> dict:
    return db.load_taxonomy(str(ROOT / "configs" / "taxonomy.yaml"))


@st.cache_data(show_spinner=False)
def all_events() -> list:
    conn = open_conn()
    try:
        return db.query_events(conn)
    finally:
        conn.close()


def baseline_forecast(events: list, precedence: list) -> dict:
    """Most-frequent category over all events. Placeholder, NOT a model."""
    counts = Counter(e["category"] for e in events)
    top = max(counts.values())
    leaders = [c for c in precedence if counts.get(c) == top]
    total = sum(counts.values())
    return {"forecast_month": "next month", "model": "most-frequent baseline (placeholder)",
            "predicted_category": leaders[0],
            "probabilities": {c: n / total for c, n in counts.most_common()},
            "baselines": {}, "metrics": None, "history": [], "top_features": [], "supporting_event_ids": []}


tax, events = taxonomy(), all_events()
precedence = tax.get("category_precedence", [c["id"] for c in tax["categories"]])
if not events:
    st.warning("No events in the database yet.")
    st.stop()

real = FORECAST.exists()
if real:
    try:
        fc = json.loads(FORECAST.read_text(encoding="utf-8"))
    except Exception as exc:  # malformed file: fall back, but say so
        st.error(f"Could not read {FORECAST.name}: {exc}. Showing the baseline instead.")
        fc, real = baseline_forecast(events, precedence), False
else:
    fc = baseline_forecast(events, precedence)

if not real:
    st.warning("PLACEHOLDER. No model output found (data/processed/forecast_latest.json). "
               "This is the most-frequent baseline over all events, not a forecast.")

a, b, c = st.columns(3)
a.metric("Forecast month", fc.get("forecast_month", "?"))
b.metric("Predicted dominant category", fc.get("predicted_category", "?"))
b.caption(f"Model: {fc.get('model', '?')}")
m = fc.get("metrics")
if m:
    c.metric("Macro-F1 (test)", f"{m.get('macro_f1', 0):.2f}")
    c.caption(f"Accuracy {m.get('accuracy', 0):.2f} over {m.get('test_months', '?')} test months")
else:
    c.metric("Macro-F1 (test)", "pending")

st.subheader("Class probabilities")
probs = pd.DataFrame(sorted(fc.get("probabilities", {}).items(), key=lambda kv: -kv[1]),
                     columns=["category", "probability"])
st.plotly_chart(px.bar(probs, x="probability", y="category", orientation="h", height=320)
                .update_layout(yaxis_title=None, margin=dict(l=10, r=10, t=10, b=10)),
                use_container_width=True)

if fc.get("baselines"):
    st.subheader("Baselines")
    st.dataframe(pd.DataFrame([fc["baselines"]]), hide_index=True, use_container_width=True)

if fc.get("history"):
    st.subheader("Rolling-origin history (actual vs predicted)")
    h = pd.DataFrame(fc["history"])
    h["correct"] = h["actual"] == h["predicted"]
    st.dataframe(h, hide_index=True, use_container_width=True)
    st.caption(f"{h['correct'].mean():.0%} of months predicted correctly.")

if fc.get("top_features"):
    st.subheader("Top features")
    f = pd.DataFrame(fc["top_features"]).sort_values("importance")
    st.plotly_chart(px.bar(f, x="importance", y="feature", orientation="h", height=300),
                    use_container_width=True)

st.subheader("Supporting events")
ids = fc.get("supporting_event_ids") or []
by_id = {e["event_id"]: e for e in events}
support = [by_id[i] for i in ids if i in by_id]
if not support:
    pred = [e for e in events if e["category"] == fc.get("predicted_category")]
    support = sorted(pred, key=lambda e: e["date"] or "", reverse=True)[:5]
    st.caption("No supporting events listed by the model; showing the 5 most recent events in the predicted category.")

for e in support:
    label = e.get("model_agent") or e.get("trigger") or e["event_id"]
    cols = st.columns([6, 1])
    cols[0].markdown(f"**{e['date']}**, {e['category']}, {e.get('organization') or 'unknown'}  \n{label}")
    if cols[1].button("Evidence", key=f"ev_{e['event_id']}"):
        st.session_state["evidence_event"] = e["event_id"]
        st.switch_page("pages/5_Evidence.py")

with st.expander("Expected format of data/processed/forecast_latest.json (for the forecasting code)"):
    st.json(EXAMPLE)
st.caption("Forecasts describe reported AI developments in the corpus, with uncertainty. They are not "
           "predictions of a future 'AI revolution'.")
