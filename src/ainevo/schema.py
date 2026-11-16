"""AI canon-event record + validation (owner: TS; shared file, changes need approval from all four).

One `Event` = one normalised AI canon event (brief section 9). All allowed values come from
configs/taxonomy.yaml, so the schema, the annotation sheets and the forecasting code cannot drift apart.

Typical use:
    tax = load_taxonomy()
    ev = Event.from_gold_row(row)            # a row of data/annotations/gold_events_v1.csv
    problems = ev.validate(tax)              # [] if fine
    ev.month                                 # '2024-05'  (key for monthly features)
Later steps (T7 linking) fill `source_doc_ids` with every document that reports the same real event.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml

DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")
AUTONOMY_NA = None  # autonomy_level 'NA' is stored as None


def load_taxonomy(path: str | Path = "configs/taxonomy.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def make_event_id(*doc_ids: str) -> str:
    """Stable id: md5 of the sorted source doc_ids (same documents -> same id)."""
    key = "|".join(sorted(doc_ids))
    return "ev_" + hashlib.md5(key.encode("utf-8")).hexdigest()[:10]


def _blank(v) -> str:
    return "" if v is None else str(v).strip()


@dataclass
class Event:
    # --- brief section 9 fields
    event_id: str
    date: str                      # event date: YYYY-MM-DD, or YYYY-MM if only the month is known
    category: str                  # one of taxonomy.categories[].id
    trigger: str = ""              # exact words in the text that signal the event
    organization: str = ""
    model_agent: str = ""
    capability: str = ""           # one of taxonomy.capability_tags
    action: str = ""
    autonomy_level: int | None = None   # 0-4, None = NA / cannot be judged
    interaction: str = ""          # one of taxonomy.interaction
    impact: str = ""
    source: str = ""               # URL of the main report
    confidence: int = 2            # 1-3 (annotation confidence; later also linking confidence)
    # --- extra fields used by the timeline / features
    publication_date: str = ""
    phase_hint: int | None = None  # 1-7 (never 8: that phase is model-derived)
    source_doc_ids: list[str] = field(default_factory=list)   # all reports of this event (after linking)
    origin: str = "gold"           # gold | extracted | seed

    # ------------------------------------------------------------------ derived
    @property
    def month(self) -> str:
        """'YYYY-MM' key used by monthly features and the forecasting split."""
        return self.date[:7]

    @property
    def year(self) -> int:
        return int(self.date[:4])

    @property
    def date_start(self) -> str:
        """Full date for sorting/plotting: a month-only date becomes the 1st of that month."""
        return self.date if len(self.date) == 10 else self.date + "-01"

    # ------------------------------------------------------------------ validation
    def validate(self, tax: dict) -> list[str]:
        """Return a list of problems (empty list = valid). Mirrors evaluation.gold.validate."""
        cats = [c["id"] for c in tax["categories"]]
        default_phase = {c["id"]: c["default_phase"] for c in tax["categories"]}
        p: list[str] = []

        if not self.event_id:
            p.append("event_id is empty")
        if not DATE_RE.match(self.date or ""):
            p.append(f"date {self.date!r} is not YYYY-MM-DD or YYYY-MM")
        elif self.date[:4] < "2017":
            p.append("date is before 2017 (outside the project range)")
        if self.category not in cats:
            p.append(f"category {self.category!r} is not in the taxonomy")
        if self.capability and self.capability not in tax["capability_tags"]:
            p.append(f"capability {self.capability!r} is not in capability_tags")
        if self.interaction and self.interaction not in tax["interaction"]:
            p.append(f"interaction {self.interaction!r} is not in the taxonomy")
        if self.autonomy_level is not None and self.autonomy_level not in (0, 1, 2, 3, 4):
            p.append(f"autonomy_level {self.autonomy_level!r} must be 0-4 or None")
        if self.confidence not in (1, 2, 3):
            p.append(f"confidence {self.confidence!r} must be 1, 2 or 3")
        if self.phase_hint is not None and self.phase_hint not in range(1, 8):
            p.append(f"phase_hint {self.phase_hint!r} must be 1-7 (8 is model-derived only)")
        if self.category == "autonomous_action" and self.autonomy_level in (0, 1, 2):
            p.append("autonomous_action usually means autonomy 3-4")
        if self.category == "multi_agent_coordination" and self.interaction not in ("", "agent_agent"):
            p.append("multi_agent_coordination usually has interaction = agent_agent")
        if self.category in default_phase and self.phase_hint is not None \
                and self.phase_hint not in default_phase[self.category]:
            p.append("phase_hint differs from the category's default phase (fine if the text shows it)")
        return p

    # ------------------------------------------------------------------ conversion
    def to_dict(self) -> dict:
        d = asdict(self)
        d["source_doc_ids"] = ";".join(self.source_doc_ids)   # flat string for CSV / SQLite
        d["autonomy_level"] = "NA" if self.autonomy_level is None else self.autonomy_level
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        """Inverse of to_dict (also accepts blank strings from CSV)."""
        a = _blank(d.get("autonomy_level"))
        ph = _blank(d.get("phase_hint"))
        ids = d.get("source_doc_ids") or ""
        if isinstance(ids, str):
            ids = [i for i in ids.split(";") if i]
        return cls(
            event_id=_blank(d.get("event_id")), date=_blank(d.get("date")), category=_blank(d.get("category")),
            trigger=_blank(d.get("trigger")), organization=_blank(d.get("organization")),
            model_agent=_blank(d.get("model_agent")), capability=_blank(d.get("capability")),
            action=_blank(d.get("action")),
            autonomy_level=None if a in ("", "NA") else int(float(a)),
            interaction=_blank(d.get("interaction")), impact=_blank(d.get("impact")),
            source=_blank(d.get("source")), confidence=int(float(_blank(d.get("confidence")) or 2)),
            publication_date=_blank(d.get("publication_date")),
            phase_hint=None if ph == "" else int(float(ph)),
            source_doc_ids=list(ids), origin=_blank(d.get("origin")) or "gold",
        )

    @classmethod
    def from_gold_row(cls, r: dict) -> "Event":
        """Build an Event from one row of the gold file. Accepts both the annotation-sheet column names
        (event_date, url, confidence) and the merged gold_events_v1.csv names (date, source_url, annotator_confidence)."""
        def pick(*names):
            for n in names:
                v = _blank(r.get(n))
                if v:
                    return v
            return None

        doc_id = _blank(r.get("doc_id"))
        return cls.from_dict({
            "event_id": make_event_id(doc_id), "date": pick("event_date", "date", "publication_date"),
            "category": r.get("category"), "trigger": r.get("trigger"), "organization": r.get("organization"),
            "model_agent": r.get("model_agent"), "capability": r.get("capability"), "action": r.get("action"),
            "autonomy_level": r.get("autonomy_level"), "interaction": r.get("interaction"),
            "impact": r.get("impact"), "source": pick("url", "source_url"),
            "confidence": pick("confidence", "annotator_confidence"),
            "publication_date": r.get("publication_date"), "phase_hint": r.get("phase_hint"),
            "source_doc_ids": [doc_id] if doc_id else [], "origin": "gold",
        })


EVENT_COLUMNS = [f.name for f in fields(Event)]