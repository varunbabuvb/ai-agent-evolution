"""Timeline table (owner: TS, plan T7 / Day 11).

Takes event rows (seed timeline, gold events or merged linked events: anything with the `schema.Event` columns)
and returns one clean, sorted table with a month and a quarter column, cut at the project data cutoff.
Month-only dates ('2024-05') are kept and placed on the 1st of that month for sorting.
"""
from __future__ import annotations

import pandas as pd

from ainevo.schema import load_taxonomy

CUTOFF_DEFAULT = "2026-09"   # configs/split.yaml: last complete month


def build_timeline(df: pd.DataFrame, cutoff_month: str = CUTOFF_DEFAULT, tax: dict | None = None) -> pd.DataFrame:
    """Clean + sort events. Adds: date_start (Timestamp), month ('YYYY-MM'), quarter ('YYYYQn'), year,
    autonomy (float, NaN for NA). Drops rows with an unparseable date, a category outside the taxonomy,
    and events after `cutoff_month` (they would leak into the test period)."""
    tax = tax or load_taxonomy()
    cats = {c["id"] for c in tax["categories"]}
    out = df.copy()
    d = out["date"].astype(str).str.strip()
    out["date_start"] = pd.to_datetime(d.where(d.str.len() == 10, d + "-01"), errors="coerce")
    out = out[out["date_start"].notna() & out["category"].isin(cats)].copy()
    out["month"] = out["date_start"].dt.strftime("%Y-%m")
    out["year"] = out["date_start"].dt.year
    out["quarter"] = out["date_start"].dt.year.astype(str) + "Q" + out["date_start"].dt.quarter.astype(str)
    out["autonomy"] = pd.to_numeric(out.get("autonomy_level"), errors="coerce")
    out = out[out["month"] <= cutoff_month]
    return out.sort_values(["date_start", "event_id"]).reset_index(drop=True)


PLACEHOLDER_ORGS = {"arxiv", "unknown", "n/a", "na", "none"}
PLACEHOLDER_MODELS = {"model/agent", "model", "agent", "unknown", "n/a", "na", "none"}


def from_gold(df: pd.DataFrame) -> pd.DataFrame:
    """Adapt gold_events_v1.csv (one row per annotated document) to the event-row format used here.
    doc_id -> source_doc_ids, annotator_confidence -> confidence. A source name that was typed into
    `organization` ('arXiv') or the template word 'Model/Agent' is not an entity: it is blanked, otherwise
    it would count as a 'new organisation' in the novelty feature and as a shared name in linking."""
    out = df.copy()
    if "source_doc_ids" not in out and "doc_id" in out:
        out["source_doc_ids"] = out["doc_id"].astype(str)
    if "confidence" not in out and "annotator_confidence" in out:
        out["confidence"] = out["annotator_confidence"]
    out["organization"] = out["organization"].where(~out["organization"].astype(str).str.strip().str.lower().isin(PLACEHOLDER_ORGS), "")
    out["model_agent"] = out["model_agent"].where(~out["model_agent"].astype(str).str.strip().str.lower().isin(PLACEHOLDER_MODELS), "")
    return out

def apply_merges(df: pd.DataFrame, merges: pd.DataFrame, id_col: str = "annotation_id") -> pd.DataFrame:
    """Merge gold events that report the same real-world event (decided by HA). Refer to events by annotation_id,
    because event_id is renumbered between gold versions. For each (keep, drop) pair the dropped row is removed and
    its document is added to the kept row's source_doc_ids. The kept row keeps its own date and fields."""
    out = df.copy().reset_index(drop=True)
    for _, m in merges.iterrows():
        keep, drop = str(m["keep_annotation_id"]).strip(), str(m["drop_annotation_id"]).strip()
        ik = out.index[out[id_col].astype(str) == keep]
        idr = out.index[out[id_col].astype(str) == drop]
        if len(ik) != 1 or len(idr) != 1:
            raise ValueError(f"merge {keep} <- {drop}: need exactly one row for each id, found {len(ik)} and {len(idr)}")
        docs = [d for d in str(out.at[ik[0], "source_doc_ids"]).split(";") + str(out.at[idr[0], "source_doc_ids"]).split(";") if d]
        out.at[ik[0], "source_doc_ids"] = ";".join(dict.fromkeys(docs))
        out = out.drop(index=idr[0])
    return out.reset_index(drop=True)


def from_extractions(df: pd.DataFrame, threshold: float = 0.5) -> pd.DataFrame:
    """Adapt extractions_final.csv (one row per corpus document, from the extraction + classifier pipeline) to
    event rows. Keeps documents with p_event >= threshold. First organisation / first system name only.
    NOTE: the has_event classifier over-predicts (about 90% of blogs and papers), so counts built from this
    are over-counts; use them to test the pipeline, not to quote."""
    out = df.copy()
    out["p_event"] = pd.to_numeric(out["p_event"], errors="coerce").fillna(0.0)
    out = out[out["p_event"] >= threshold].copy()
    first = lambda s: s.astype(str).str.split(";").str[0].str.strip()
    out["date"] = out["event_date"]
    out["category"] = out["category_pred"]
    out["organization"] = first(out["organizations"])
    out["model_agent"] = first(out["systems"])
    out["capability"] = out["capability_pred"]
    out["autonomy_level"] = out["autonomy_pred"].replace("", "NA")
    out["interaction"] = out["interaction_pred"]
    out["source_doc_ids"] = out["doc_id"].astype(str)
    out["event_id"] = "X-" + out["doc_id"].astype(str)
    out["confidence"] = 2
    return out.reset_index(drop=True)