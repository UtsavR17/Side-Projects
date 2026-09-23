"""End-to-end API tests on a seeded demo dataset."""
import pytest

from seed_demo import build_demo_data


@pytest.fixture(scope="module", autouse=True)
def _noop():
    yield


@pytest.fixture()
def seeded_db(db):
    build_demo_data(db, past_meetings=8, upcoming_meetings=1)
    return db


def test_upcoming_and_race_detail(client, seeded_db):
    resp = client.get("/api/races")
    assert resp.status_code == 200
    races = resp.json()["races"]
    assert len(races) == 7  # one upcoming meeting, seven races

    race = races[0]
    detail = client.get(f"/api/races/{race['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == race["id"]
    assert len(body["entries"]) >= 8
    entry = body["entries"][0]
    assert entry["horse_name"]
    assert "predictions" in entry


def test_completed_races_listed(client, seeded_db):
    resp = client.get("/api/races?upcoming=false&limit=200")
    assert resp.status_code == 200
    assert len(resp.json()["races"]) >= 50  # 8 meetings * 7 races


def test_horse_profile(client, seeded_db):
    listing = client.get("/api/horses?search=Demo").json()
    assert listing["horses"]
    horse_id = listing["horses"][0]["id"]
    profile = client.get(f"/api/horses/{horse_id}")
    assert profile.status_code == 200
    body = profile.json()
    assert body["career"]["runs"] >= 0
    assert body["recent_form"]  # demo horses have history


def test_jockey_trainer_profile(client, seeded_db):
    j = client.get("/api/jockeys").json()["jockeys"]
    t = client.get("/api/trainers").json()["trainers"]
    assert j and t
    assert client.get(f"/api/jockeys/{j[0]['id']}").status_code == 200
    assert client.get(f"/api/trainers/{t[0]['id']}").status_code == 200


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] is True
