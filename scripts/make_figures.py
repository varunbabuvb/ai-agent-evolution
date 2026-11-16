"""Day 18: phase and trend charts (owner: TS). Static PNGs for the report, in results/figures/.
Run: python scripts/make_figures.py        (needs matplotlib: pip install matplotlib)
Inputs: results/tables/{features_monthly_gold,counts_quarterly,quarterly_view_gold}.csv, data/processed/timeline_gold.csv,
        data/interim/corpus_v1_clean.jsonl, results/tables/changepoints_gold*.csv
Colours: the validated 8-slot categorical palette, assigned to the 8 event categories in taxonomy order (a category keeps
its colour in every chart). Light surface; text in ink tokens, never in series colours.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from ainevo.analysis.trends import category_counts_by_month, category_mix_by_year
from ainevo.schema import load_taxonomy

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "results" / "figures"
TAB = ROOT / "results" / "tables"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
LABEL = {"capability_breakthrough": "Capability breakthrough", "agentic_development": "Agentic development",
         "multi_agent_coordination": "Multi-agent coordination", "autonomous_action": "Autonomous action",
         "unexpected_behavior_incident": "Unexpected behaviour / incident", "infrastructure_ecosystem": "Infrastructure / ecosystem",
         "adoption_scale": "Adoption / scale", "research_milestone": "Research milestone"}


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.patch.set_facecolor(SURFACE)
    fig.savefig(FIG / name, dpi=200, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print("saved", (FIG / name).relative_to(ROOT))


def first_breaks():
    """Break months: all-series run and shares-only run (from the tables written by run_changepoints.py)."""
    out = {}
    for tag, key in (("gold", "all series"), ("gold_shares", "shares only")):
        p = TAB / f"changepoints_{tag}.csv"
        if p.exists():
            seg = pd.read_csv(p)
            out[key] = list(seg["start"].iloc[1:])
    return out


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    tax = load_taxonomy()
    cats = [c["id"] for c in tax["categories"]]
    col = dict(zip(cats, SLOTS))
    tl = pd.read_csv(ROOT / "data" / "processed" / "timeline_gold.csv", keep_default_na=False)
    mf = pd.read_csv(TAB / "features_monthly_gold.csv", keep_default_na=False, na_values=[""])
    months = mf["month"].tolist()
    x = pd.to_datetime([m + "-01" for m in months])
    breaks = first_breaks()
    bx = {k: [pd.Timestamp(m + "-01") for m in v] for k, v in breaks.items()}

    # ---- 1. monthly events by category, stacked, with 3-month moving average
    cc = category_counts_by_month(tl[tl["month"].isin(months)], months, cats)
    fig, ax = plt.subplots(figsize=(11, 4.6))
    style(ax)
    bottom = pd.Series(0.0, index=cc.index)
    for c in cats:
        ax.bar(x, cc[c].values, bottom=bottom.values, width=24, color=col[c], edgecolor=SURFACE, linewidth=0.8)
        bottom += cc[c]
    ma = cc.sum(axis=1).rolling(3, min_periods=1).mean()
    ax.plot(x, ma.values, color=INK, linewidth=1.8)
    top = ax.get_ylim()[1]
    for i, (key, xs) in enumerate(bx.items()):
        for v in xs:
            ax.axvline(v, color=INK2, linestyle=(0, (4, 3)), linewidth=1.2)
            # first label sits left of its line, second right of its line, so they never collide
            ax.text(v + pd.Timedelta(days=(-6 if i == 0 else 6)), top * 0.97, f"shift {v:%Y-%m}\n({key})", color=INK2,
                    fontsize=8, va="top", ha=("right" if i == 0 else "left"))
    ax.set_ylabel("Annotated events per month", color=INK2, fontsize=9)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_title("Gold events per month by category, 2022-2026", loc="left", color=INK, fontsize=12, fontweight="bold")
    handles = [Patch(facecolor=col[c], edgecolor=SURFACE, label=LABEL[c]) for c in cats]
    handles.append(Line2D([0], [0], color=INK, linewidth=1.8, label="3-month average (all categories)"))
    ax.legend(handles=handles, ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=8.5, labelcolor=INK2)
    save(fig, "fig1_monthly_events_by_category.png")

    # ---- 2. mix trends: category shares and autonomy (small multiples, one axis each)
    rf = pd.read_csv(TAB / "features_rolling_gold.csv", keep_default_na=False, na_values=[""])
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.2), sharex=True)
    for a in axes:
        style(a)
    thin = (mf["n_events"].rolling(3, min_periods=1).sum() < 3).to_numpy()
    last_thin = int(max([i for i, t in enumerate(thin) if t], default=-1))
    for a in axes:
        if last_thin >= 0:
            a.axvspan(x[0] - pd.Timedelta(days=15), x[last_thin] + pd.Timedelta(days=15), color=GRID, alpha=0.55, linewidth=0)
    axes[0].text(0.01, 0.95, "fewer than 3 events in the\n3-month window: shares\nnot measurable", color=INK2, fontsize=8, va="top",
                 transform=axes[0].transAxes)
    a = axes[0]
    for name, c, lab in (("multi_agent_share_ma3", "multi_agent_coordination", "Multi-agent coordination"),
                         ("incident_share_ma3", "unexpected_behavior_incident", "Unexpected behaviour / incident")):
        y = rf[name].where(~thin)
        a.plot(x, y, color=col[c], linewidth=2)
        a.text(x[-1] + pd.Timedelta(days=12), y.iloc[-1], lab, color=INK, fontsize=9, va="center")
    a.set_ylabel("Share of the month's events\n(3-month trailing mean)", color=INK2, fontsize=9)
    a.set_title("The event mix shifts in 2023", loc="left", color=INK, fontsize=12, fontweight="bold")
    a = axes[1]
    a.plot(x, rf["mean_autonomy_ma3"].where(~thin), color=SLOTS[0], linewidth=2)
    a.text(x[-1] + pd.Timedelta(days=12), rf["mean_autonomy_ma3"].iloc[-1], "Mean autonomy level", color=INK, fontsize=9, va="center")
    a.set_ylabel("Autonomy level (0-4)\n(3-month trailing mean)", color=INK2, fontsize=9)
    for a in axes:
        for key, xs in bx.items():
            for v in xs:
                a.axvline(v, color=INK2, linestyle=(0, (4, 3)), linewidth=1.2)
    axes[1].xaxis.set_major_locator(mdates.YearLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[1].set_xlim(x[0] - pd.Timedelta(days=15), x[-1] + pd.Timedelta(days=300))
    axes[1].set_xticks([pd.Timestamp(f"{y}-01-01") for y in range(2022, 2027)])
    ks = " and ".join(f"{v:%Y-%m} ({k})" for k, vs in bx.items() for v in vs)
    fig.text(0.01, -0.01, f"Dashed lines: detected shifts at {ks}. Grey: months where the data is too thin to measure a share.", color=INK2, fontsize=8)
    save(fig, "fig2_mix_and_autonomy_trends.png")

    # ---- 3. category mix by year (100% stacked), n above each bar
    mix = category_mix_by_year(tl, cats).reindex(range(2017, 2027), fill_value=0)
    mix["n"] = mix["n"].astype(int)
    fig, ax = plt.subplots(figsize=(11, 4.4))
    style(ax)
    ax.yaxis.grid(False)
    left = pd.Series(0.0, index=mix.index)
    for c in cats:
        ax.bar(mix.index.astype(int), mix[c].values, bottom=left.values, width=0.7, color=col[c], edgecolor=SURFACE, linewidth=0.8)
        left += mix[c]
    for yr, n in mix["n"].items():
        ax.text(int(yr), 1.02, f"n={int(n)}", ha="center", color=INK2, fontsize=8.5)
    ax.set_ylim(0, 1.1)
    ax.set_xticks(mix.index.astype(int))
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.set_title("Category mix by year (gold events)", loc="left", color=INK, fontsize=12, fontweight="bold")
    ax.legend(handles=[Patch(facecolor=col[c], edgecolor=SURFACE, label=LABEL[c]) for c in cats], ncol=4, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=8.5, labelcolor=INK2)
    fig.text(0.01, -0.16, "2017-2021 have only 0-6 events a year: read those bars as examples, not shares.", color=INK2, fontsize=8)
    save(fig, "fig3_category_mix_by_year.png")

    # ---- 4. quarterly view 2017-2021: seed timeline vs gold (grouped bars)
    q = pd.read_csv(TAB / "quarterly_view_gold.csv")
    q = q[q["quarter"].str[:4].astype(int) <= 2021]
    fig, ax = plt.subplots(figsize=(11, 3.8))
    style(ax)
    pos = range(len(q))
    ax.bar([p - 0.2 for p in pos], q["seed_events"], width=0.38, color=SLOTS[0], edgecolor=SURFACE, linewidth=0.8)
    ax.bar([p + 0.2 for p in pos], q["gold_events"], width=0.38, color=SLOTS[1], edgecolor=SURFACE, linewidth=0.8)
    ax.set_xticks(list(pos))
    ax.set_xticklabels(q["quarter"], rotation=60, fontsize=8)
    ax.set_yticks(range(0, int(max(q["seed_events"].max(), q["gold_events"].max())) + 2))
    ax.set_ylabel("Events per quarter", color=INK2, fontsize=9)
    ax.set_title("2017-2021: notable-model seed events vs annotated documents", loc="left", color=INK, fontsize=12, fontweight="bold")
    ax.legend(handles=[Patch(facecolor=SLOTS[0], label="Seed timeline (Epoch AI / AI Index)"), Patch(facecolor=SLOTS[1], label="Gold events")],
              ncol=2, frameon=False, loc="upper left", fontsize=9, labelcolor=INK2)
    save(fig, "fig4_quarterly_2017_2021.png")

    # ---- 5. control: corpus volume vs gold events (two panels, one axis each)
    docs = [json.loads(l) for l in open(ROOT / "data" / "interim" / "corpus_v1_clean.jsonl", encoding="utf-8")]
    dm = pd.Series([d["publication_date"][:7] for d in docs]).value_counts().reindex(months, fill_value=0)
    fig, axes = plt.subplots(2, 1, figsize=(11, 5.4), sharex=True)
    for a in axes:
        style(a)
    axes[0].bar(x, dm.values, width=24, color=SLOTS[0], edgecolor=SURFACE, linewidth=0.8)
    axes[0].set_ylabel("Corpus documents\nper month", color=INK2, fontsize=9)
    axes[0].set_title("Corpus coverage grows at the same time as the shift", loc="left", color=INK, fontsize=12, fontweight="bold")
    axes[1].bar(x, mf["n_events"].values, width=24, color=SLOTS[1], edgecolor=SURFACE, linewidth=0.8)
    axes[1].set_ylabel("Gold events\nper month", color=INK2, fontsize=9)
    for a in axes:
        for key, xs in bx.items():
            for v in xs:
                a.axvline(v, color=INK2, linestyle=(0, (4, 3)), linewidth=1.2)
    axes[1].xaxis.set_major_locator(mdates.YearLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ks = " and ".join(f"{v:%Y-%m}" for vs in bx.values() for v in vs)
    fig.text(0.01, -0.01, f"Dashed lines: detected shifts ({ks}). Event counts follow document counts (correlation 0.8), so shares, not counts, carry the evidence.",
             color=INK2, fontsize=8)
    save(fig, "fig5_corpus_volume_vs_events.png")


if __name__ == "__main__":
    main()
