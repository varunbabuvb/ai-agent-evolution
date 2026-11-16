"""Seed timeline (owner: TS): dated milestone events from Epoch AI + Stanford AI Index 2026.

Purpose (plan T7): give the timeline and the linking step a head start and a coverage check by year.
This is NOT the gold set. Every row is an `ainevo.schema.Event` with origin='seed'.

How events are chosen
- Epoch AI 'notable_ai_models.csv' lists thousands of models, mostly minor variants. Selecting by rule alone
  picked variants ('GPT-4o (Jan 2025)') over milestones, so the landmark releases are NAMED in SEED_MODELS
  (one flagship per lab/family, no size or date variants). Dates, organisations, links and size come from
  Epoch's own row, so nothing about a model is typed in by hand except the name.
- AI Index 2026 events (AI_INDEX_EVENTS) are copied from its two dated timelines (p.74 model releases,
  pp.176-178 economy). Where an AI Index model event matches an Epoch row, the two are merged into one event.

Rules used to fill fields (all rule-based, hence confidence 2 unless noted; confidence 1 = check by hand)
- category: Epoch accessibility 'Unreleased' -> research_milestone; otherwise capability_breakthrough.
  Agent products listed in AGENTIC override this.
- capability: from the model name / Epoch domain (coding, reasoning, multimodal, else text_generation).
- autonomy_level 0 and interaction human_model for plain models; agentic overrides set their own values.

Epoch AI data is CC BY 4.0: cite 'Epoch AI, Data on AI models, epoch.ai/data/ai-models'.
Run: PYTHONPATH=src python scripts/build_seed_timeline.py
"""
from __future__ import annotations

import re

import pandas as pd

from ainevo.schema import EVENT_COLUMNS, Event, make_event_id

EPOCH_URL = "https://epoch.ai/data/ai-models"
AI_INDEX_URL = "https://hai.stanford.edu/ai-index/2026-ai-index-report"
CUTOFF = "2026-09-30"          # last complete month is 2026-09 (configs/split.yaml)

# One flagship per lab/family. Names must match Epoch's 'Model' column exactly.
SEED_MODELS = [
    # 2017-2019
    "Transformer", "ELMo", "GPT-1", "BERT-Large", "Transformer-XL (257M)", "GPT-2 (1.5B)", "XLNet",
    "RoBERTa Large", "Megatron-LM (8.3B)", "T5-11B",
    # 2020-2021
    "Meena", "Retrieval-Augmented Generator", "GPT-3 175B (davinci)", "GShard (dense)", "CLIP (ViT L/14@336px)",
    "Switch", "Codex", "Jurassic-1-Jumbo", "FLAN 137B", "HyperCLOVA 204B", "Megatron-Turing NLG 530B",
    "Gopher (280B)",
    # 2022
    "InstructGPT 175B", "GPT-NeoX-20B", "LaMDA", "Chinchilla", "PaLM (540B)", "Flamingo", "OPT-175B",
    "Minerva (540B)", "BLOOM-176B", "Flan-PaLM 540B",
    # 2023
    "LLaMA-65B", "Claude", "GPT-4 (Mar 2023)", "PaLM 2", "Claude 2", "Llama 2-70B", "Falcon-180B", "GPT-4V",
    "GPT-4 Turbo (Nov 2023)", "Claude 2.1", "Grok-1", "Qwen-72B", "Gemini 1.0 Ultra", "Mixtral 8x7B", "CogAgent",
    # 2024
    "Gemini 1.5 Pro", "Claude 3 Opus", "Mistral Large", "Llama 3-70B", "GPT-4o", "Claude 3.5 Sonnet",
    "Llama 3.1-405B", "Mistral Large 2", "Grok-2", "Qwen2.5-72B", "Claude 3.5 Sonnet (October 2024)",
    "o1", "Gemini 2.0 Pro", "o3", "DeepSeek-V3",
    # 2025
    "DeepSeek-R1", "Computer-Using Agent (CUA)", "Grok 3", "Claude 3.7 Sonnet", "GPT-4.5",
    "Gemini 2.5 Pro (Mar 2025)", "Llama 4 Maverick", "Qwen3-235B-A22B", "Claude Opus 4", "Kimi K2", "Grok 4",
    "gpt-oss-120b", "GPT-5", "AgentFounder-30B", "Claude Sonnet 4.5", "GPT-5.1", "Gemini 3 Pro",
    "GPT-5.1-Codex-Max", "Claude Opus 4.5",
    # 2026
    "GPT-5.3 Codex", "GLM-5", "Qwen3.5 397B-A17B", "GPT-5.4", "Claude Mythos Preview", "Muse Spark", "GPT-5.5",
    "DeepSeek-V4-Pro", "Gemini 3.5 Flash", "Claude Opus 4.8", "Claude Fable 5", "Kimi K3", "Claude Opus 5",
    "Claude Fable 5.1", "GPT-6 Astra", "Gemini 4 Argon",
]

# Agent products: category/capability/autonomy are set by hand (confidence 1 = verify against the source).
AGENTIC = {
    "CogAgent": dict(category="agentic_development", capability="computer_use", autonomy=2, interaction="human_agent",
                     phase=3, action="releases a visual language model built to operate GUIs as an agent", conf=1),
    "Computer-Using Agent (CUA)": dict(category="autonomous_action", capability="computer_use", autonomy=3,
                     interaction="human_agent", phase=4, conf=2,
                     action="releases an agent that operates a browser/computer through screenshots to finish tasks"),
    "Claude 3.5 Sonnet (October 2024)": dict(category="agentic_development", capability="computer_use", autonomy=2,
                     interaction="human_agent", phase=3, conf=1,
                     action="updated model released with a computer-use beta (check this against the source)"),
    "AgentFounder-30B": dict(category="agentic_development", capability="planning", autonomy=2,
                     interaction="human_agent", phase=3, conf=1, action="releases an agent-focused foundation model"),
    "Claude Sonnet 4.5": dict(category="agentic_development", capability="computer_use", autonomy=3,
                     interaction="human_agent", phase=3, conf=1,
                     action="releases a model reaching 61.4% on OSWorld computer-use tasks, with the Claude Agent SDK for long-running autonomous workflows"),
    "GPT-5.1-Codex-Max": dict(category="agentic_development", capability="coding", autonomy=3,
                     interaction="human_agent", phase=3, conf=1, action="releases an agentic coding model (check this against the source)"),
    "GPT-5.3 Codex": dict(category="agentic_development", capability="coding", autonomy=3,
                     interaction="human_agent", phase=3, conf=1, action="releases an agentic coding model (check this against the source)"),
}

# AI Index 2026 facts for models that are also Epoch rows (merged into one event; AI Index date wins).
AI_INDEX_MODEL_FACTS = {
    "DeepSeek-R1": dict(date="2025-01-20", impact="Introduced GRPO reasoning training; US tech stocks lost over $1 trillion in market value soon after release", page="p.74"),
    "Gemini 2.5 Pro (Mar 2025)": dict(date="2025-03-25", impact="1M-token context; ~63.8% on SWE-bench Verified; #1 on LMArena", page="p.74"),
    "Claude Sonnet 4.5": dict(date="2025-09-29", impact="61.4% on OSWorld; 77.2%+ on SWE-bench Verified; shipped Claude Agent SDK", page="p.74"),
    "GPT-5.1": dict(date="2025-11-12", impact="~76.3% on SWE-bench Verified vs ~72.8% for GPT-5; adjusts reasoning effort to task", page="p.74"),
}

# Events from the AI Index 2026 economy timeline (pp.176-178). Only compute/platform/adoption/agentic-AI items.
AI_INDEX_EVENTS = [
    dict(date="2025-01-21", category="infrastructure_ecosystem", org="OpenAI; SoftBank; Oracle; MGX", model="Stargate Project",
         action="announces the Stargate AI data-centre joint venture", impact="Plans to invest $100-500 billion in US AI data centres by 2029", page="p.176", conf=2),
    dict(date="2025-01-27", category="adoption_scale", org="DeepSeek", model="DeepSeek app",
         action="reaches No. 1 as most downloaded free app on Apple's US App Store", impact="No. 1 free app on the US App Store", page="p.176", conf=2),
    dict(date="2025-03-10", category="infrastructure_ecosystem", org="ServiceNow", model="Moveworks acquisition",
         action="announces plans to acquire Moveworks to drive its agentic AI platform", impact="", page="p.176", conf=1),
    dict(date="2025-05-13", category="infrastructure_ecosystem", org="AWS; HUMAIN", model="AWS-HUMAIN AI infrastructure deal",
         action="announce an AI infrastructure deal to accelerate AI adoption in Saudi Arabia and globally", impact="$5 billion", page="p.176", conf=2),
    dict(date="2025-09-10", category="infrastructure_ecosystem", org="OpenAI; Oracle", model="OpenAI-Oracle cloud contract",
         action="signs a five-year cloud contract to supply compute for Stargate", impact="$300 billion; 4.5 gigawatts of computing capacity", page="p.177", conf=2),
]


def _fmt(x: float) -> str:
    return f"{x:.1e}".replace("e+0", "e").replace("e+", "e")


def _impact(row: pd.Series) -> str:
    parts = []
    p = row.get("Parameters")
    if pd.notna(p) and p:
        if p >= 1e12:
            parts.append(f"{p / 1e12:.3g}T parameters")
        elif p >= 1e9:
            parts.append(f"{p / 1e9:.3g}B parameters")
        else:
            parts.append(f"{p / 1e6:.3g}M parameters")
    c = row.get("Training compute (FLOP)")
    if pd.notna(c) and c:
        parts.append(f"{_fmt(float(c))} FLOP training compute")
    return "; ".join(parts)


def _capability(model: str, domain: str) -> str:
    n = model.lower()
    if re.search(r"codex|coder|code", n):
        return "coding"
    if re.search(r"\bo[134]\b|r1|think|deep think|reason", n):
        return "reasoning"
    if "multimodal" in domain.lower() or "vision" in domain.lower():
        return "multimodal"
    return "text_generation"


def _first_org(org) -> str:
    return "" if pd.isna(org) else str(org).split(",")[0].strip()


def epoch_events(df: pd.DataFrame, models=SEED_MODELS) -> tuple[list[Event], list[dict], list[str]]:
    """Build events for the named Epoch rows. Returns (events, extras, names_not_found)."""
    by_name = df.drop_duplicates("Model").set_index("Model")
    events, extras, missing = [], [], []
    for name in models:
        if name not in by_name.index:
            missing.append(name)
            continue
        r = by_name.loc[name]
        date = str(r["Publication date"])[:10]
        if date > CUTOFF:
            continue
        access = r.get("Model accessibility")
        released = pd.notna(access) and access != "Unreleased"
        ag = AGENTIC.get(name)
        if ag:
            cat, cap, aut, inter, phase, conf, action = (ag["category"], ag["capability"], ag["autonomy"],
                                                         ag["interaction"], ag["phase"], ag["conf"], ag["action"])
        else:
            cat = "capability_breakthrough" if released or pd.isna(access) else "research_milestone"
            cap, aut, inter, phase = _capability(name, str(r.get("Domain", ""))), 0, "human_model", 1
            conf = 2 if pd.notna(access) else 1
            action = f"releases {name}" if cat == "capability_breakthrough" else f"presents {name} (no public release)"
        impact, src_ids, seed_src, page = _impact(r), [f"epoch:{name}"], "epoch", ""
        facts = AI_INDEX_MODEL_FACTS.get(name)
        if facts:
            date, impact, page = facts["date"], facts["impact"], facts["page"]
            src_ids.append(f"ai_index_2026:{name}")
            seed_src = "epoch+ai_index"
        ev = Event(event_id=make_event_id(*src_ids), date=date, category=cat, organization=_first_org(r["Organization"]),
                   model_agent=name, capability=cap, action=action, autonomy_level=aut, interaction=inter, impact=impact,
                   source=AI_INDEX_URL if facts else (r["Link"] if pd.notna(r["Link"]) else EPOCH_URL),
                   confidence=conf, publication_date=str(r["Publication date"])[:10], phase_hint=phase,
                   source_doc_ids=src_ids, origin="seed")
        events.append(ev)
        extras.append(dict(seed_source=seed_src, epoch_criteria=str(r.get("Notability criteria", "")),
                           epoch_accessibility="" if pd.isna(access) else access, ai_index_page=page,
                           needs_review="Y" if conf == 1 else ""))
    return events, extras, missing


def ai_index_events() -> tuple[list[Event], list[dict]]:
    events, extras = [], []
    for e in AI_INDEX_EVENTS:
        ids = [f"ai_index_2026:{e['model']}"]
        ev = Event(event_id=make_event_id(*ids), date=e["date"], category=e["category"], organization=e["org"],
                   model_agent=e["model"], capability="infrastructure" if e["category"] == "infrastructure_ecosystem" else "other",
                   action=e["action"], autonomy_level=None, interaction="ecosystem", impact=e["impact"],
                   source=AI_INDEX_URL, confidence=e["conf"], publication_date=e["date"], phase_hint=7,
                   source_doc_ids=ids, origin="seed")
        events.append(ev)
        extras.append(dict(seed_source="ai_index", epoch_criteria="", epoch_accessibility="", ai_index_page=e["page"],
                           needs_review="Y" if e["conf"] == 1 else ""))
    return events, extras


def build_seed(df: pd.DataFrame, tax: dict) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Return (seed table sorted by date, names not found in Epoch, validation problems)."""
    ev1, ex1, missing = epoch_events(df)
    ev2, ex2 = ai_index_events()
    rows, problems = [], []
    for ev, ex in zip(ev1 + ev2, ex1 + ex2):
        problems += [f"{ev.model_agent}: {m}" for m in ev.validate(tax)]
        rows.append({**ev.to_dict(), **ex})
    out = pd.DataFrame(rows, columns=EVENT_COLUMNS + ["seed_source", "epoch_criteria", "epoch_accessibility",
                                                      "ai_index_page", "needs_review"])
    out = out.sort_values(["date", "model_agent"]).reset_index(drop=True)
    return out, missing, problems
