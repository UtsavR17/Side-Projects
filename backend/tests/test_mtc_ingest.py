"""MTC ingest tests: the parsed documents must land in the schema correctly."""
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import Horse, Jockey, Race, RaceEntry, RaceResult, Trainer
from pipeline.import_files import import_text

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_HTML = (FIXTURES / "mtc_race_page.html").read_text(encoding="utf-8")
PDF_TEXT = (FIXTURES / "mtc_result_pdf_text.txt").read_text(encoding="utf-8")


def test_import_mtc_race_page_creates_full_result(db):
    stats = import_text(db, PAGE_HTML, kind="auto", label="mtc-race-page.html")
    assert stats["kind"] == "mtc-html"
    assert stats["races_created"] == 1
    assert stats["entries"] == 3
    assert stats["results_written"] == 3

    race = db.scalars(select(Race)).one()
    assert race.status == "completed"
    assert race.meeting_no == 16
    assert race.distance_m == 1400
    assert race.race_class == "0-25"
    assert race.win_time_s == pytest.approx(84.88)
    assert race.race_name and "Great Gusto" in race.race_name
    assert race.tote_dividends["Exacta"]["1-3"] == pytest.approx(122.0)
    assert race.sectional_times["400m"] == pytest.approx(26.93)

    entries = db.scalars(select(RaceEntry).order_by(RaceEntry.saddle_no)).all()
    assert [e.saddle_no for e in entries] == [1, 3, 6]
    winner = entries[0]
    assert winner.barrier == 3
    assert winner.weight_kg == pytest.approx(61.5)
    assert winner.sp_odds == pytest.approx(20.0)
    assert winner.odds == pytest.approx(20.0)      # SP also feeds the market feature
    assert winner.rating == 26
    assert winner.gear == "XNA"
    assert winner.body_weight_kg == 465.0
    assert winner.jockey.name == "S RAMA"
    assert winner.trainer.name == "V RUHEE"
    assert winner.horse.external_id == "2298678"
    assert winner.notes is None

    third = entries[2]
    assert third.jockey.name == "B ECROIGNARD"
    assert third.body_weight_delta == 2.0
    assert third.notes == "jockey claim -4.0kg"

    results = db.scalars(select(RaceResult).order_by(RaceResult.finish_position)).all()
    assert [r.finish_position for r in results] == [1, 2, 3]
    assert results[0].time_s == pytest.approx(84.88)
    assert results[0].win_dividend == pytest.approx(20.0)
    assert results[0].place_dividend == pytest.approx(11.0)
    assert results[0].margin == "0.8"
    assert results[1].win_dividend is None


def test_import_mtc_race_page_is_idempotent(db):
    import_text(db, PAGE_HTML, kind="auto", label="page.html")
    again = import_text(db, PAGE_HTML, kind="auto", label="page.html")

    assert again["races_created"] == 0
    assert again["races_updated"] == 1
    assert again["entries"] == 0                     # no duplicate runners
    assert again["results_written"] == 3             # results refreshed in place
    assert len(db.scalars(select(Race)).all()) == 1
    assert len(db.scalars(select(RaceEntry)).all()) == 3
    assert len(db.scalars(select(Horse)).all()) == 3
    assert len(db.scalars(select(Jockey)).all()) == 3
    assert len(db.scalars(select(Trainer)).all()) == 3


def test_import_mtc_result_pdf_text(db):
    stats = import_text(db, PDF_TEXT, kind="auto", label="Race-Result-392-R1.pdf")
    assert stats["kind"] == "mtc-pdf"
    assert stats["races_created"] == 1
    assert stats["entries"] == 3
    assert stats["results_written"] == 3

    race = db.scalars(select(Race)).one()
    assert race.date.hour == 12 and race.date.minute == 30      # from "12:30"
    assert race.prize == "Rs 188000"
    assert race.meeting_no == 16

    entries = db.scalars(select(RaceEntry).order_by(RaceEntry.saddle_no)).all()
    assert [e.saddle_no for e in entries] == [1, 3, 6]
    winner = entries[0]
    assert winner.jockey.name == "S RAMA"        # jockey from the continuation line
    assert winner.trainer.name == "V RUHEE"
    assert winner.sp_odds == pytest.approx(20.0)
    assert winner.rating == 26
    assert winner.body_weight_kg == 465.0
    assert entries[2].jockey.name == "B ECROIGNARD"
    assert entries[2].notes == "jockey claim -4.0kg"   # claim kept in notes

    results = db.scalars(select(RaceResult).order_by(RaceResult.finish_position)).all()
    assert results[0].win_dividend == pytest.approx(20.0)

    # re-importing the same document updates in place
    again = import_text(db, PDF_TEXT, kind="auto", label="Race-Result-392-R1.pdf")
    assert again["races_created"] == 0 and again["entries"] == 0
    assert len(db.scalars(select(RaceEntry)).all()) == 3
