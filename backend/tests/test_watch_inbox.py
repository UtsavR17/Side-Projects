"""Inbox watcher tests: files dropped by a human are imported, moved, and flagged."""
from pathlib import Path

from pipeline.watch_inbox import stage_inbox

FIXTURES_CSV = """date,race_no,venue,race_name,distance_m,race_class,track_condition,horse,jockey,trainer,barrier,weight_kg,odds
2026-06-06,1,Champ de Mars,Inbox Cup,1600,Handicap,good,Inbox Star,J. Smith,T. Brown,1,55,3.4
2026-06-06,1,Champ de Mars,Inbox Cup,1600,Handicap,good,Inbox Comet,A. Test,T. Practice,2,54.5,4.1
"""


def test_stage_inbox_imports_and_moves_file(tmp_path: Path, db):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    (inbox / "card.csv").write_text(FIXTURES_CSV, encoding="utf-8")

    summary = stage_inbox(inbox)

    assert summary["counts"]["imported"] == 1
    assert summary["imported"][0]["races_created"] == 1
    assert not (inbox / "card.csv").exists()
    assert (inbox / "processed" / "card.csv").exists()

    # running again on an empty inbox is a no-op
    again = stage_inbox(inbox)
    assert again["counts"] == {"imported": 0, "failed": 0, "skipped": 0}


def test_stage_inbox_quarantines_unparseable_and_empty_files(tmp_path: Path, db):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    (inbox / "empty.csv").write_text("   ", encoding="utf-8")
    (inbox / "junk.html").write_text("<html><body>nothing useful here</body></html>",
                                     encoding="utf-8")

    summary = stage_inbox(inbox)

    assert summary["counts"]["failed"] == 1          # empty file
    assert summary["counts"]["skipped"] == 1         # HTML with no recognisable race
    assert (inbox / "failed" / "empty.csv").exists()
    assert (inbox / "failed" / "junk.html").exists()


def test_stage_inbox_ignores_unwatched_suffixes(tmp_path: Path, db):
    inbox = tmp_path / "incoming"
    inbox.mkdir()
    (inbox / "notes.md").write_text("# not a data file", encoding="utf-8")

    summary = stage_inbox(inbox)

    assert summary["counts"] == {"imported": 0, "failed": 0, "skipped": 0}
    assert (inbox / "notes.md").exists()  # left untouched
