"""Notification triggers + preferences (Prompt F)."""
from sqlalchemy import select  # noqa: F401

from app.models import Horse, User  # noqa: F401
from app.services.notifications import notify_users


def _register(client, email):
    resp = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_notify_respects_preferences(client, db):
    headers = _register(client, "notif@example.com")
    me_id = client.get("/api/auth/me", headers=headers).json()["id"]

    prefs = client.get("/api/me/preferences", headers=headers).json()
    assert prefs["fixtures"] is True and prefs["weekly_summary"] is True

    # scoped to this user (a bootstrap admin also exists in the DB)
    assert notify_users(db, "fixtures", "New fixtures", "3 races added",
                        user_ids=[me_id]) == 1

    prefs["fixtures"] = False
    assert client.put("/api/me/preferences", headers=headers, json=prefs).status_code == 200
    assert notify_users(db, "fixtures", "New fixtures again", user_ids=[me_id]) == 0
    assert notify_users(db, "predictions_ready", "Ready for Race 3",
                        user_ids=[me_id]) == 1

    listing = client.get("/api/notifications", headers=headers).json()
    assert listing["unread_count"] == 2
    titles = {n["title"] for n in listing["notifications"]}
    assert "New fixtures" in titles and "New fixtures again" not in titles

    client.post("/api/notifications/read-all", headers=headers)
    assert client.get("/api/notifications", headers=headers).json()["unread_count"] == 0

    # default broadcast reaches every active user (admin included)
    assert notify_users(db, "weekly_summary", "Weekly report") >= 2


def test_notifications_require_auth(client):
    assert client.get("/api/notifications").status_code == 401


def test_followed_horse_flow(client, db):
    from pipeline.clean import resolve_or_create

    horse = resolve_or_create(db, Horse, "Follow Star")
    db.commit()

    headers = _register(client, "follower@example.com")
    horse_id = horse.id
    resp = client.post(f"/api/horses/{horse_id}/follow", headers=headers)
    assert resp.json()["following"] is True
    # idempotent
    client.post(f"/api/horses/{horse_id}/follow", headers=headers)
    resp = client.delete(f"/api/horses/{horse_id}/follow", headers=headers)
    assert resp.json()["following"] is False
