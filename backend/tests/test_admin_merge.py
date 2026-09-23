"""Admin merge flow (§11 data-quality view)."""
from app.models import Horse, RaceEntry


def _admin_headers(client):
    resp = client.post("/api/auth/login",
                       json={"email": "admin@example.com", "password": "adminpass123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_merge_duplicate_horses(client, db):
    from pipeline.clean import resolve_or_create

    canonical = resolve_or_create(db, Horse, "Belle Isle")
    dup = resolve_or_create(db, Horse, "Belleisle Old")
    other = resolve_or_create(db, Horse, "Third Horse")
    db.commit()

    from app.models import Race, RACE_SCHEDULED
    from datetime import datetime

    race = Race(date=datetime(2030, 1, 5, 14, 0), race_no=1, status=RACE_SCHEDULED)
    db.add(race)
    db.flush()
    db.add(RaceEntry(race_id=race.id, horse_id=dup.id))
    db.add(RaceEntry(race_id=race.id, horse_id=other.id))
    db.commit()

    headers = _admin_headers(client)
    resp = client.post("/api/admin/horses/merge",
                       headers=headers,
                       json={"source_id": dup.id, "target_id": canonical.id})
    assert resp.status_code == 200, resp.text
    assert resp.json()["entries_moved"] == 1

    db.expire_all()
    dup_after = db.get(Horse, dup.id)
    assert dup_after.merged_into_id == canonical.id
    moved = db.query(RaceEntry).filter(RaceEntry.horse_id == canonical.id).all()
    assert len(moved) == 1


def test_merge_requires_admin(client, db):
    resp = client.post("/api/admin/horses/merge",
                       json={"source_id": 1, "target_id": 2})
    assert resp.status_code == 401
