"""MTC parsers + ingest tests, using trimmed fixtures derived from a real page.

The structures (and the values in them) come from a saved MTC race page and the
official `Race-Result-*.pdf` export for Meeting 16 / 19 Sep 2026.
"""
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import Horse, Race, RaceEntry, RaceResult
from pipeline.import_files import import_text
from pipeline.mtc_parse import (
    looks_like_mtc_page,
    looks_like_mtc_result_pdf,
    parse_hwt,
    parse_mtc_race_page,
    parse_mtc_result_pdf,
    pdf_text,
)

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_HTML = (FIXTURES / "mtc_race_page.html").read_text(encoding="utf-8")
PDF_TEXT = (FIXTURES / "mtc_result_pdf_text.txt").read_text(encoding="utf-8")


def test_parse_hwt():
    assert parse_hwt("465") == (465.0, None)
    assert parse_hwt("503 (+17)") == (503.0, 17.0)
    assert parse_hwt("439 (-1)") == (439.0, -1.0)


def test_detectors():
    assert looks_like_mtc_page(PAGE_HTML) is True
    assert looks_like_mtc_result_pdf(PDF_TEXT) is True
    assert looks_like_mtc_page("<html>hello</html>") is False


def test_parse_mtc_race_page_meta_and_runners():
    parsed, warnings = parse_mtc_race_page(PAGE_HTML)
    assert warnings == []
    assert parsed["meeting_no"] == 16
    assert parsed["race_no"] == 1
    assert parsed["distance_m"] == 1400
    assert parsed["race_class"] == "0-25"
    assert parsed["win_time_s"] == pytest.approx(84.88)
    assert parsed["date"].date().isoformat() == "2026-09-19"
    assert parsed["race_name"] and "Great Gusto" in parsed["race_name"]
    assert len(parsed["runners"]) == 3


def test_parse_mtc_race_page_runner_fields():
    parsed, _ = parse_mtc_race_page(PAGE_HTML)
    winner, second, third = parsed["runners"]

    assert winner["finish_position"] == 1
    assert winner["saddle_no"] == 1
    assert winner["horse"] == "FLAG CHAMP"
    assert winner["external_id"] == "2298678"          # MTC horse id from the link
    assert winner["trainer"] == "V RUHEE"
    assert winner["jockey"] == "S RAMA"
    assert winner["gear"] == "XNA"
    assert winner["body_weight_kg"] == 465.0
    assert winner["body_weight_delta"] is None
    assert winner["barrier"] == 3
    assert winner["weight_kg"] == pytest.approx(61.5)
    assert winner["sp_odds"] == pytest.approx(20.0)
    assert winner["win_dividend"] == pytest.approx(20.0)
    assert winner["place_dividend"] == pytest.approx(11.0)
    assert winner["time_s"] == pytest.approx(84.88)
    assert winner["rating"] == 26

    assert second["horse"] == "KAISARISSA"
    assert second["body_weight_kg"] == 503.0
    assert second["body_weight_delta"] == 17.0
    assert second["win_dividend"] is None               # non-winner

    assert third["jockey"] == "B ECROIGNARD"            # claim suffix stripped
    assert third["claim_kg"] == 4.0
    assert third["gear"] == "SN *"
    assert third["rating"] == 18


def test_parse_mtc_race_page_dividends_and_sectionals():
    parsed, _ = parse_mtc_race_page(PAGE_HTML)
    dividends = parsed["tote_dividends"]
    assert dividends["Win"]["1"] == pytest.approx(20.0)
    assert dividends["Place"]["3"] == pytest.approx(19.0)
    assert dividends["Exacta"]["1-3"] == pytest.approx(122.0)
    assert parsed["sectional_times"] == {"1000m": 59.21, "800m": 48.69,
                                         "600m": 37.72, "400m": 26.93}


def test_parse_mtc_race_page_reads_sectional_table():
    """MTC renders sectionals as a marks-row + times-row table."""
    html = """
    <table class="race-card-mtc"><tr><th>FP</th><th>Horse</th></tr>
      <tr><td>1</td><td><a href="/horse/x/1">1. X</a></td></tr></table>
    <table class="table">
      <tr><td>1000m</td><td>800m</td><td>600m</td><td>400m</td></tr>
      <tr><td>0:59.21</td><td>0:48.69</td><td>0:37.72</td><td>0:26.93</td></tr>
    </table>
    """
    parsed, _ = parse_mtc_race_page(html)
    assert parsed["sectional_times"] == {"1000m": 59.21, "800m": 48.69,
                                         "600m": 37.72, "400m": 26.93}


def test_parse_mtc_result_pdf_layout_columns():
    parsed, warnings = parse_mtc_result_pdf(PDF_TEXT)
    assert warnings == []
    assert parsed["meeting_no"] == 16
    assert parsed["race_no"] == 1
    assert parsed["race_time_label"] == "12:30"
    assert parsed["distance_m"] == 1400
    assert parsed["race_class"] == "0-25"
    assert parsed["prize"] == "Rs 188000"
    assert parsed["win_time_s"] == pytest.approx(84.88)
    assert parsed["date"].date().isoformat() == "2026-09-19"

    runners = parsed["runners"]
    assert len(runners) == 3
    assert runners[0]["horse"] == "FLAG CHAMP"
    assert runners[0]["trainer"] == "V RUHEE"
    assert runners[0]["jockey"] == "S RAMA"            # from the continuation line
    assert runners[0]["sp_odds"] == pytest.approx(20.0)
    assert runners[0]["rating"] == 26
    assert runners[1]["horse"] == "KAISARISSA"
    assert runners[1]["jockey"] == "M SONARAM"
    assert runners[1]["body_weight_delta"] == 17.0
    assert runners[2]["jockey"] == "B ECROIGNARD"      # claim stripped from the jockey line
    assert runners[2]["claim_kg"] == 4.0


def test_pdf_text_passthrough_and_bad_pdf():
    assert pdf_text("plain text") == "plain text"
    assert pdf_text(b"%PDF-1.4 not really a pdf") == ""   # never raises


def test_race_name_dash_mojibake_is_repaired():
    """Saved pages can carry a mis-decoded en dash as 'û' (seen on the real page)."""
    html = """
    <title>Horse Racing | Racing News | Betting | Mauritius Turf Club | Meeting 16 |
    Hinterland Cup G3 - 1400M | The Great Gusto û Red Star Trophy |
    Saturday 19 September 2026 | Fixtures</title>
    <table class="race-card-mtc"><tr><th>FP</th><th>Horse</th></tr>
      <tr><td>1</td><td><a href="/horse/x/1">1. X</a></td></tr></table>
    """
    parsed, _ = parse_mtc_race_page(html)
    assert parsed["race_name"] == "The Great Gusto - Red Star Trophy"
    assert "û" not in parsed["race_name"]
