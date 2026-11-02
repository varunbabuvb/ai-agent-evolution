# Annotation guidelines — AI canon events (DRAFT v0)

Owner: Harshita (HA). Status: draft until the agreement meeting; then frozen as v1 (changes only via `docs/decisions.md`).
Taxonomy source of truth: `configs/taxonomy.yaml`.

## 1. What you are labelling
The unit is an **AI canon event**: a significant, dated change in the capability, autonomy, interaction, deployment or ecosystem of AI systems.
You read one document (title + excerpt; open the URL if the excerpt is not enough) and record **the one main event it reports**.
If a document reports several, label the most significant one and write the others in `notes`.

## 2. Scope: is this about our topic?
In scope: language-model-based or agentic systems (LLMs, LLM agents, tool/computer-using agents, multi-agent LLM systems, agent frameworks and platforms) and the language-model milestones leading up to them.
Out of scope → `no_off_topic`: classical reinforcement learning, robotics, traffic, wireless, game-AI or path-finding papers with no language-model component (for example "Multi-Agent Path Finding with Deadlines"). The word "agent" alone does not make a document in scope.

## 3. Step 1 — `has_event`
| value | use when |
|---|---|
| `yes` | The text states something new that happened or was released/shown, and a reader could put it on a timeline. |
| `no_not_significant` | Dependency or patch bump, bug-fix-only release, survey, tutorial, opinion/policy essay, incremental paper with no new capability. |
| `no_off_topic` | Out of scope (section 2). |
| `no_unclear_text` | Text too short or garbled to judge, even after opening the URL. |

For any `no_*` value leave all other yellow columns empty.

## 4. Step 2 — fields (only if `has_event = yes`)
| field | rule |
|---|---|
| `event_date` | When the event happened. `YYYY-MM-DD`, or `YYYY-MM` if only the month is known. Fall back to `publication_date` only if the text gives nothing else. |
| `category` | One of 8 ids (section 5). |
| `trigger` | The exact words in the text that signal the event ("introducing", "released", "we demonstrate"). Copy, do not paraphrase. |
| `organization` | Lab/company/institution (e.g. OpenAI). For papers, the lead institution if stated, otherwise leave blank. |
| `model_agent` | Name of the model, bot, agent or framework (e.g. Auto-GPT v0.4.0). |
| `capability` | One primary tag from `capability_tags`. |
| `action` | Short phrase: what the system does or what was done ("browses the web to complete tasks"). |
| `autonomy_level` | 0–4 scale (section 6), or `NA`. |
| `interaction` | Main interaction type (section 7). |
| `impact` | Evidence of consequence: numbers, users, benchmark gain, incident outcome. Blank if none is stated. |
| `phase_hint` | 1–7 from the brief's framework. Never 8 (that phase is model-derived). Use the default phase of the category unless the text clearly shows another. |
| `confidence` | 1 unsure · 2 fairly sure · 3 certain. |

## 5. Choosing the category
Ask in order and stop at the first "yes":
1. Is it an incident, security/control problem, or behaviour the designers did not expect? → `unexpected_behavior_incident`
2. Do several LLM-based agents communicate, delegate or coordinate? → `multi_agent_coordination`
3. Does a system act in an environment with little human intervention (long-running, end-to-end tasks)? → `autonomous_action`
4. Does the text report large-scale use (users, customers, rollout)? → `adoption_scale`
5. Is it a platform, API, protocol, compute or deployment infrastructure? → `infrastructure_ecosystem`
6. Is it a new single agent, workflow, memory or multi-step task system? → `agentic_development`
7. Is it a new/improved model capability (reasoning, coding, multimodal, tool-use)? → `capability_breakthrough`
8. Otherwise, a research result that materially changes what agents can do → `research_milestone`

This order equals `category_precedence` in the taxonomy. Judge by the **main claim**, not by buzzwords in the text.

Recurring edge cases (decide as shown unless the pilot changes the rule):
- **Partnership announcements** (e.g. "OpenAI and Amazon announce strategic partnership"): compute/platform/distribution deal → `infrastructure_ecosystem`; stated usage numbers or rollout → `adoption_scale`.
- **System cards** (e.g. "Sora 2 System Card"): label the capability being released (`capability_breakthrough`), not the safety document.
- **Paper on LLM agents with no released system** → `research_milestone`, unless it clearly fits a higher-precedence category (e.g. an LLM multi-agent method → `multi_agent_coordination`).
- **Release notes**: new feature that changes what agents can do → `agentic_development`/`infrastructure_ecosystem`; "bump dependency", "fix typo", "update tests" → `no_not_significant`.

## 6. Autonomy scale
| level | meaning |
|---|---|
| 0 | No autonomy: static model output |
| 1 | Assisted: one tool/API call per request, human drives each step |
| 2 | Supervised multi-step: plans and runs several steps, human approves or steers |
| 3 | Autonomous task: finishes a whole task end-to-end with minimal human input |
| 4 | Self-directed/persistent: runs continuously, sets sub-goals, open environments or with other agents |

Rate what the system **does in the text**, not what it might do in future.

## 7. Interaction types
`human_model` (chat/prompt) · `human_agent` (user delegates tasks) · `agent_tool` (calls tools/APIs/code) · `agent_agent` (agents talk to each other) · `agent_environment` (acts in a real or simulated environment) · `ecosystem` (many agents/users/platforms).

## 8. Illustrative examples (title-level; confirm in the pilot)
| document | has_event | category |
|---|---|---|
| "Learning from human preferences" (OpenAI, 2017) | yes | `research_milestone` |
| "Introducing deep research" (2025) | yes | `agentic_development` |
| "GPT-4 API general availability and deprecation of older models in the Completions API" (2024) | yes | `infrastructure_ecosystem` |
| "Theory of Mind for Multi-Agent Collaboration via Large Language Models" (2023) | yes | `multi_agent_coordination` |
| "Multi-Agent Path Finding with Deadlines" (2018) | no_off_topic | — |
| "langchain-openai==1.5.2" (version bump, no new capability) | no_not_significant | — |

## 9. Pilot and agreement protocol
1. Everyone labels the same 15 pilot documents **alone**.
2. Harshita runs `python -m ainevo.evaluation.agreement` on the four pilot files: Fleiss' kappa across all four, Cohen's kappa for each pair, on `has_event`, `category` and `autonomy_level`.
3. Targets: kappa ≥ 0.70 good; 0.60–0.70 acceptable; below 0.60 → rewrite the rule that caused the disagreements and re-label those items.
4. Meeting: go through every disagreement, update this file and `taxonomy.yaml`, then freeze v1.
5. 15 documents are few, so kappa is rough. Also look at the disagreements themselves. The ~75-document batches overlap with a 10% shared re-check later to measure agreement again.
6. Quality checks: each person reviews 10 labels from another batch (the QA step in the plan).

## 10. Frozen rules
After the freeze, categories and scales do not change. A correction goes into `docs/decisions.md` with date, reason and who approved, and earlier labels are re-checked.
