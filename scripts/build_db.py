"""Build the SQLite database (owner: VV). Run from the repo root:

  py -3.13 scripts/build_db.py                                      # corpus only
  py -3.13 scripts/build_db.py --events data/annotations/gold_events_v1.csv
  py -3.13 scripts/build_db.py --stats                              # only print counts (no rebuild)

The database is rebuilt from scratch every time, so re-running is always safe.
Output: data/processed/events.db (git-ignored: *.db).
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ainevo.storage import db  # noqa: E402


def print_stats(conn):
    c = db.corpus_counts(conn)
    print(f"\ndocuments: {c['total']}")
    years = sorted({r["year"] for r in c["by_year_and_type"]})
    types = sorted({r["source_type"] for r in c["by_year_and_type"]})
    cell = {(r["year"], r["source_type"]): r["n"] for r in c["by_year_and_type"]}
    print("year  " + "  ".join(f"{t:>13}" for t in types) + "   total")
    for y in years:
        vals = [cell.get((y, t), 0) for t in types]
        print(f"{y}  " + "  ".join(f"{v:>13}" for v in vals) + f"   {sum(vals):>5}")
    print("\nper source:", ", ".join(f"{r['source']} {r['n']}" for r in c["by_source"]))
    n_ev = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    print(f"\nevents: {n_ev}")
    for r in conn.execute("SELECT origin, category, COUNT(*) n FROM events GROUP BY origin, category ORDER BY origin, n DESC"):
        print(f"  {r['origin']:<10} {r['category']:<30} {r['n']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(ROOT / "data" / "processed" / "events.db"))
    ap.add_argument("--corpus", default=str(ROOT / "data" / "interim" / "corpus_v1_clean.jsonl"))
    ap.add_argument("--events", default=None, help="events CSV/JSONL, e.g. data/annotations/gold_events_v1.csv")
    ap.add_argument("--origin", default="gold", choices=db.ORIGINS, help="origin tag for --events (default gold)")
    ap.add_argument("--taxonomy", default=str(ROOT / "configs" / "taxonomy.yaml"))
    ap.add_argument("--stats", action="store_true", help="only print counts from the existing database")
    a = ap.parse_args()

    if not a.stats:
        if not Path(a.corpus).exists():
            raise SystemExit(f"Corpus not found: {a.corpus}. Run scripts/run_pipeline.py first.")
        s = db.build_database(a.db, a.corpus, a.events, a.taxonomy, a.origin)
        print(f"built {s['db']}: {s['documents']} documents, {s['events']} events, "
              f"full-text search: {'on' if s['fts_search'] else 'OFF (this SQLite has no FTS5; LIKE fallback)'}")
        if s["rejected_events"]:
            print(f"\n{len(s['rejected_events'])} event row(s) rejected:")
            for eid, problems in s["rejected_events"]:
                print(f"  {eid}: {'; '.join(problems)}")
    elif not Path(a.db).exists():
        raise SystemExit(f"{a.db} does not exist yet. Run without --stats first.")
    conn = db.connect(a.db)
    print_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
