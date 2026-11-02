from datetime import date
from ainevo.preprocessing.clean_dedup import clean_text, process, low_signal_release, load_cutoff


def doc(i, text, d="2024-05-01", st="lab_blog", title="t"):
    return {"doc_id": str(i), "title": title, "publication_date": d, "source_type": st, "source": "x", "url": f"u{i}", "text": text, "metadata": {}}


def test_boilerplate_removes_only_the_fragment():
    t = clean_text("We release a new agent that can browse. Sign up for early access to the beta. It scores 80% on the benchmark.")
    assert "early access" not in t and "80% on the benchmark" in t and "new agent" in t


def test_urls_and_html_removed():
    assert clean_text("see <b>this</b> https://x.com/a now") == "see this now"


def test_out_of_range_short_and_duplicates():
    long = "an agent uses tools to complete tasks " * 8
    rows = [doc(1, long, "2016-12-31"), doc(2, long, "2026-10-05"), doc(3, "short"), doc(4, long), doc(5, long),
            doc(6, "completely different text about robots and planning in a warehouse " * 6)]
    final, s = process(rows, date(2026, 9, 30))
    assert s["dropped_out_of_range"] == 2 and s["dropped_too_short"] == 1 and s["dropped_exact_dup"] == 1
    assert [d["doc_id"] for d in final] == ["4", "6"]


def test_near_duplicate_keeps_earliest():
    a = " ".join(f"word{i}" for i in range(120))       # 120 distinct words -> many distinct shingles
    final, s = process([doc(1, a + " extra", "2024-06-01"), doc(2, a, "2024-05-01")], date(2026, 9, 30))
    assert s["dropped_near_dup"] == 1 and final[0]["doc_id"] == "2"


def test_flags():
    bump = doc(1, "Bump requests from 2.31 to 2.32 and update dependencies for the project " * 2, st="release_notes")
    assert low_signal_release({**bump, "text": bump["text"]})
    final, _ = process([bump], date(2026, 9, 30))
    assert final[0]["metadata"]["low_signal_release"] is True and final[0]["metadata"]["llm_terms_found"] is False


def test_cutoff_reads_split_yaml(tmp_path):
    p = tmp_path / "s.yaml"; p.write_text("cutoff_month: 2026-02\n")
    assert load_cutoff(str(p)) == date(2026, 2, 28)
