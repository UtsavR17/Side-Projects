"""Scraper parser + ingestion tests (Prompt B.1/B.2)."""
from datetime import datetime

from sqlalchemy import select

from pipeline.scrape_mtc import ingest_fixtures, parse_fixtures, parse_results

from app.models import Horse, Race

FIXTURE_HTML = """
<html><body>
<h2>12 May 2026</h2>
<div class="race-card">Race 3 - 1400m - 12 May 2026
  <table>
    <tr><td>Belle Isle</td><td>J. Smith</td><td>T. Brown</td><td>1</td><td>55</td><td>3.5</td></tr>
    <tr><td>Café Noir</td><td>A. Test</td><td>T. Practice</td><td>2</td><td>54.5</td><td>5.0</td></tr>
  </table>
</div>
<div class="race-card">Race 4 - 1800m - 12 May 2026
  <table>
    <tr><td>Demo Charger</td><td>B. Sample</td><td>T. Fiction</td><td>3</td><td>56</td><td>2.8</td></tr>
  </table>
</div>
</body></html>
"""

RESULTS_HTML = """
<html><body>
<div class="result">Race 3 results
 <table>
  <tr><td>1</td><td>Belle Isle</td><td>1.2L</td><td>1:23.4</td></tr>
  <tr><td>2</td><td>Café Noir</td><td>0.5L</td><td>1:24.1</td></tr>
 </table>
</div>
</body></html>
"""


def test_parse_fixtures_extracts_cards():
    races, warnings = parse_fixtures(FIXTURE_HTML, "http://example/fixtures")
    assert len(races) == 2
    r3 = next(r for r in races if r["race_no"] == 3)
    assert r3["distance_m"] == 1400
    assert len(r3["entries"]) == 2
    assert r3["entries"][0]["horse"] == "Belle Isle"
    assert r3["entries"][0]["odds"] == 3.5
    assert r3["date"] == "12 May 2026"
    assert warnings == []


def test_parse_fixtures_empty_page_warns():
    races, warnings = parse_fixtures("<html><body>nothing here</body></html>", "http://x")
    assert races == []
    assert warnings  # flagged, not raised


def test_ingest_upsert_and_odds_move(db):
    cards, _ = parse_fixtures(FIXTURE_HTML, "http://example/fixtures")
    first = ingest_fixtures(db, cards, "http://example/fixtures",
                            default_date=datetime(2026, 5, 12))
    assert first["races_created"] == 2
    assert first["entries"] == 3

    # same page again: no new races; odds on Belle Isle crashed -> move flagged
    cards[0]["entries"][0]["odds"] = 6.5
    second = ingest_fixtures(db, cards, "http://example/fixtures",
                             default_date=datetime(2026, 5, 12))
    assert second["races_created"] == 0
    assert second["races_updated"] == 2
    assert len(second["odds_moves"]) == 1
    assert second["odds_moves"][0]["horse"] == "Belle Isle"

    assert len(db.scalars(select(Horse)).all()) == 3


def test_parse_results(db):
    cards, _ = parse_fixtures(FIXTURE_HTML, "http://example/fixtures")
    ingest_fixtures(db, cards, "http://example/fixtures", default_date=datetime(2026, 5, 12))

    rows, warnings = parse_results(RESULTS_HTML)
    assert warnings == []
    assert rows[0] == {"race_no": 3, "position": 1, "horse": "Belle Isle",
                       "margin": "1.2L", "time": 83.4}

    from pipeline.scrape_mtc import ingest_results

    stats = ingest_results(db, rows)
    assert stats["results_written"] == 2
    assert stats["races_completed"] == 1
    race = db.scalars(select(Race).order_by(Race.race_no)).first()
    assert race.status == "completed"
