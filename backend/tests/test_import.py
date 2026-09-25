"""Human-in-the-loop import tests: parsing, CSV loaders, ingestion."""
import pytest
from sqlalchemy import select

from app.models import DataQualityFlag, Horse, Race, RaceEntry, RaceResult
from pipeline.import_files import (
    detect_kind,
    import_text,
    ingest_results_rows,
    load_fixtures_csv,
)
from pipeline.parsing import parse_date, parse_time

FIXTURES_CSV = """date,race_no,venue,race_name,distance_m,race_class,track_condition,horse,jockey,trainer,barrier,weight_kg,odds
2026-05-12,3,Champ de Mars,Winter Plate,1400,Handicap,good,Belle Isle,J. Smith,T. Brown,1,55,3.5
2026-05-12,3,Champ de Mars,Winter Plate,1400,Handicap,good,Cafe Noir,A. Test,T. Practice,2,54.5,5
2026-05-12,4,Champ de Mars,Sprint Cup,1200,Maiden,soft,Quick Step,B. Sample,T. Fiction,3,56,2.8
"""

RESULTS_CSV = """date,race_no,horse,finish_position,margin,time_s,dn_category
12/05/2026,3,Belle Isle,1,1.2L,1:23.4,
12/05/2026,3,cafe-noir,2,0.5L,1:24.1,
12/05/2026,3,Ghost Runner,3,2L,1:25.0,
"""

FIXTURES_HTML = """
<html><body><div class="race-card">Race 5 - 1800m - 12 May 2026
<table>
<tr><td>Saved Star</td><td>J. Smith</td><td>T. Brown</td><td>4</td><td>55</td><td>4.0</td></tr>
</table></div></body></html>
"""


def test_parse_helpers():
    assert parse_date("2026-05-12").year == 2026
    assert parse_date("12/05/2026").month == 5
    assert parse_date("12 May 2026").day == 12
    assert parse_time("1:23.4") == pytest.approx(83.4)
    assert parse_time("83.4") == pytest.approx(83.4)
    assert parse_time("") is None


def test_detect_kind():
    assert detect_kind(FIXTURES_CSV) == "fixtures-csv"
    assert detect_kind(RESULTS_CSV) == "results-csv"
    assert detect_kind(FIXTURES_HTML) == "fixtures-html"
    assert detect_kind("<html>results</html>", "race_results.html") == "results-html"


def test_load_fixtures_csv_groups_races():
    cards, warnings = load_fixtures_csv(FIXTURES_CSV)
    assert warnings == []
    assert len(cards) == 2  # race 3 (two runners) + race 4
    race3 = next(c for c in cards if c["race_no"] == 3)
    assert race3["distance_m"] == 1400
    assert race3["track_condition"] == "good"
    assert [e["horse"] for e in race3["entries"]] == ["Belle Isle", "Cafe Noir"]
    assert race3["entries"][0]["odds"] == 3.5
    assert race3["entries"][0]["barrier"] == 1


def test_load_fixtures_csv_reports_bad_rows():
    cards, warnings = load_fixtures_csv("date,race_no,horse\n2026-05-12,,Ghost\n")
    assert cards == []
    assert any("missing race_no/horse" in w for w in warnings)


def test_fixtures_csv_import_creates_races_and_resolves_names(db):
    stats = import_text(db, FIXTURES_CSV, kind="auto", label="card.csv")
    assert stats["kind"] == "fixtures-csv"
    assert stats["races_created"] == 2
    assert stats["entries"] == 3

    horses = db.scalars(select(Horse)).all()
    assert {h.name_norm for h in horses} == {"belle isle", "cafe noir", "quick step"}

    # re-import is idempotent: no duplicate races, entries or horses
    again = import_text(db, FIXTURES_CSV, kind="auto", label="card.csv")
    assert again["races_created"] == 0
    assert again["races_updated"] == 2
    assert len(db.scalars(select(Race)).all()) == 2
    assert len(db.scalars(select(RaceEntry)).all()) == 3
    assert len(db.scalars(select(Horse)).all()) == 3


def test_fixtures_html_import_creates_race(db):
    stats = import_text(db, FIXTURES_HTML, kind="auto", label="saved.html")
    assert stats["races_created"] == 1
    race = db.scalars(select(Race)).first()
    assert race.race_no == 5 and race.distance_m == 1800
    assert db.scalars(select(RaceEntry)).first() is not None


def test_results_csv_import_matches_date_and_normalised_names(db):
    import_text(db, FIXTURES_CSV, kind="auto", label="card.csv")
    stats = import_text(db, RESULTS_CSV, kind="auto", label="results.csv")

    assert stats["results_written"] == 2   # Belle Isle + "cafe-noir" (fuzzy/normalised)
    assert stats["races_completed"] == 1
    assert stats["unknown_horses"] == 1    # Ghost Runner is flagged, never created

    race = db.scalars(select(Race).where(Race.race_no == 3)).first()
    assert race.status == "completed"
    results = db.scalars(
        select(RaceResult)
        .join(RaceEntry, RaceEntry.id == RaceResult.race_entry_id)
        .where(RaceEntry.race_id == race.id)
    ).all()
    assert sorted(r.finish_position for r in results) == [1, 2]
    assert any(f.kind == "unknown_horse" for f in db.scalars(select(DataQualityFlag)).all())


def test_results_for_unknown_race_is_flagged(db):
    stats = ingest_results_rows(db, [{"race_no": 99, "horse": "Nobody", "position": 1,
                                      "margin": None, "time": None, "date": None}])
    assert stats["results_written"] == 0
    assert stats["missing_races"] == 1
