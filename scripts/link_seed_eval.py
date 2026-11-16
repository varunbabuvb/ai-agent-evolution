"""Test the linking rules on the seed timeline (owner: TS, Day 9).

Two checks:
 A. FALSE MERGES: the 102 seed events are all different events, so any link is an error.
 B. SIMULATED DUPLICATES: every seed event gets a second 'article' with realistic differences (date shifted by
    up to 3 days, model name written differently, organisation alias, reworded action, sometimes no model name).
    We then measure pairwise precision/recall of the grouping. This is OPTIMISTIC: real duplicates will be
    messier. Redo it with the gold set once it exists.
Run: PYTHONPATH=src python scripts/link_seed_eval.py
"""
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from ainevo.normalization.link_events import LinkConfig, link, merge_groups, pairwise_prf
from ainevo.schema import load_taxonomy

ROOT = Path(__file__).resolve().parents[1]
ORG_VARIANT = {"Google DeepMind": "Google", "Google Research": "Google", "Meta AI": "Meta", "Alibaba": "Alibaba Cloud"}


def make_duplicate(row: dict, rng: random.Random):
    d = dict(row)
    kind = rng.choices(["case", "org_prefix", "no_model"], weights=[6, 2, 2])[0]
    if len(d["date"]) == 10:
        y, m, dd = map(int, d["date"].split("-"))
        d["date"] = (date(y, m, dd) + timedelta(days=rng.randint(-3, 3))).isoformat()
    d["organization"] = ORG_VARIANT.get(d["organization"], d["organization"])
    d["action"] = f"announced {d['model_agent']}"
    d["source_doc_ids"] = "dup:" + d["event_id"]
    d["event_id"] = "dup_" + d["event_id"]
    if kind == "case":
        d["model_agent"] = d["model_agent"].lower().replace("-", " ")
    elif kind == "org_prefix":
        d["model_agent"] = f"{d['organization']} {d['model_agent']}"
    else:
        d["model_agent"] = ""
    return d, kind


def main():
    seed = pd.read_csv(ROOT / "data" / "seed" / "seed_timeline.csv", keep_default_na=False)
    tax = load_taxonomy(ROOT / "configs" / "taxonomy.yaml")
    cfg = LinkConfig()

    a = link(seed, cfg)
    merges = len(seed) - a.event_group.nunique()
    print(f"A. false merges among {len(seed)} distinct seed events: {merges}")

    rng = random.Random(7)
    originals = seed.to_dict("records")
    dups, kinds = zip(*(make_duplicate(r, rng) for r in originals))
    both = pd.DataFrame(originals + list(dups)).reset_index(drop=True)
    gold = list(range(len(originals))) * 2
    pred = link(both, cfg)["event_group"].tolist()
    print("B. simulated duplicates:", pairwise_prf(pred, gold))
    for k in ("case", "org_prefix", "no_model"):
        idx = [i for i, kk in enumerate(kinds) if kk == k]
        hit = sum(pred[i] == pred[len(originals) + i] for i in idx)
        print(f"   {k:<10} duplicate recovered: {hit}/{len(idx)}")
    merged = merge_groups(link(both, cfg), [c["id"] for c in tax["categories"]])
    print(f"   merged to {len(merged)} events from {len(both)} mentions (ideal {len(originals)})")


if __name__ == "__main__":
    main()
