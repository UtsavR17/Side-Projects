"""Tests for the /api/me endpoints the mobile client depends on."""
from sqlalchemy import select

from app.models import DeviceToken, Horse


def _register(client, email="mobile@example.com"):
    resp = client.post("/api/auth/register",
                       json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_followed_horses_round_trip(client, db):
    from pipeline.clean import resolve_or_create

    star = resolve_or_create(db, Horse, "Follow Star")
    other = resolve_or_create(db, Horse, "Other Runner")
    db.commit()

    headers = _register(client)
    assert client.get("/api/me/followed-horses", headers=headers).json()["horses"] == []

    client.post(f"/api/horses/{star.id}/follow", headers=headers)
    client.post(f"/api/horses/{other.id}/follow", headers=headers)
    horses = client.get("/api/me/followed-horses", headers=headers).json()["horses"]
    assert [h["name"] for h in horses] == ["Follow Star", "Other Runner"]

    client.delete(f"/api/horses/{star.id}/follow", headers=headers)
    horses = client.get("/api/me/followed-horses", headers=headers).json()["horses"]
    assert [h["name"] for h in horses] == ["Other Runner"]


def test_followed_horses_requires_auth(client):
    assert client.get("/api/me/followed-horses").status_code == 401


def test_device_token_registration_is_idempotent(client, db):
    headers = _register(client, email="device@example.com")

    first = client.post("/api/me/device-tokens", headers=headers,
                        json={"token": "fcm-token-abc123", "platform": "android"})
    assert first.status_code == 200, first.text
    assert first.json()["registered"] is True

    again = client.post("/api/me/device-tokens", headers=headers,
                        json={"token": "fcm-token-abc123", "platform": "android"})
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert len(db.scalars(select(DeviceToken)).all()) == 1

    # a platform change updates in place
    client.post("/api/me/device-tokens", headers=headers,
                json={"token": "fcm-token-abc123", "platform": "ios"})
    rows = db.scalars(select(DeviceToken)).all()
    assert len(rows) == 1 and rows[0].platform == "ios"

    removed = client.request("DELETE", "/api/me/device-tokens?token=fcm-token-abc123",
                             headers=headers)
    assert removed.json()["removed"] is True
    assert db.scalars(select(DeviceToken)).all() == []


def test_device_token_validation(client):
    headers = _register(client, email="device2@example.com")
    assert client.post("/api/me/device-tokens", headers=headers,
                       json={"token": "short"}).status_code == 422
    assert client.post("/api/me/device-tokens",
                       json={"token": "long-enough-token"}).status_code == 401