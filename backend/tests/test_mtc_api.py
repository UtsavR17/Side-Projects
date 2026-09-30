"""The API must expose the official MTC fields captured by the importers."""
from pathlib import Path

from pipeline.import_files import import_text

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_HTML = (FIXTURES / "mtc_race_page.html").read_text(encoding="utf-8")
PDF_TEXT = (FIXTURES / "mtc_result_pdf_text.txt").read_text(encoding="utf-8")


def test_race_detail_exposes_official_fields(client, db):
    import_text(db, PAGE_HTML, kind="auto", label="page.html")

    races = client.get("/api/races?upcoming=false&limit=50").json()["races"]
    assert races, "imported race should be listed"
    race = races[0]

    detail = client.get(f"/api/races/{race['id']}").json()

    # race-level official extras
    assert detail["meeting_no"] == 16
    assert detail["race_time_label"] == "12:30"
    assert detail["prize"] == "Rs 188000"
    assert detail["win_time_s"] == 84.88
    assert detail["tote_dividends"]["Exacta"]["1-3"] == 122.0
    assert detail["sectional_times"]["400m"] == 26.93

    entries = detail["entries"]
    assert len(entries) == 3
    # the API returns runners in race-card (barrier) order
    by_name = {e["horse_name"]: e for e in entries}
    runner = by_name["FLAG CHAMP"]
    assert runner["saddle_no"] == 1
    assert runner["horse_external_id"] == "2298678"
    assert runner["rating"] == 26
    assert runner["gear"] == "XNA"
    assert runner["sp_odds"] == 20.0
    assert runner["body_weight_kg"] == 465.0
    assert runner["jockey_name"] == "S RAMA"
    assert runner["trainer_name"] == "V RUHEE"
    assert runner["result"]["finish_position"] == 1
    assert runner["result"]["win_dividend"] == 20.0
    assert runner["result"]["place_dividend"] == 11.0

    third = by_name["BALOUCHI"]
    assert third["result"]["finish_position"] == 3
    assert third["body_weight_delta"] == 2.0
    assert third["notes"] == "jockey claim -4.0kg"


def test_horse_profile_exposes_rating_and_body_weight(client, db):
    import_text(db, PDF_TEXT, kind="auto", label="race.pdf")

    horses = client.get("/api/horses?limit=10").json()["horses"]
    horse_id = next(h["id"] for h in horses if h["name"] == "FLAG CHAMP")

    profile = client.get(f"/api/horses/{horse_id}").json()
    assert profile["external_id"] is None          # PDF carries no MTC id
    latest = profile["recent_form"][0]
    assert latest["rating"] == 26
    assert latest["sp_odds"] == 20.0
    assert latest["gear"] == "XNA"
    assert latest["body_weight_kg"] == 465.0
    assert latest["barrier"] == 3
    assert latest["finish_position"] == 1