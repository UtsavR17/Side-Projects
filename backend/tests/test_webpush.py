"""Web Push: VAPID key endpoint, subscriptions, best-effort delivery (RFC 8291/8292)."""
import json
import types

import pywebpush
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import func, select

from app.config import settings
from app.models import WebPushSubscription
from app.services.notifications import notify_users

ENDPOINT = "https://push.example.com/subscriptions/abc-123"
SUB_BODY = {
    "endpoint": ENDPOINT,
    "keys": {"p256dh": "B" * 87, "auth": "c" * 32},
}


def _register(client, email):
    resp = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _test_pem() -> str:
    """A throwaway VAPID key — generation is milliseconds on a laptop."""
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


@pytest.fixture()
def push_enabled(monkeypatch):
    monkeypatch.setattr(settings, "web_push_enabled", True)
    monkeypatch.setattr(settings, "vapid_private_key", _test_pem())
    return settings


def test_vapid_key_disabled_by_default(client):
    resp = client.get("/api/push/vapid-public-key")
    assert resp.status_code == 503
    assert "disabled" in resp.json()["detail"]


def test_vapid_key_derives_raw_p256_point(client, push_enabled):
    import base64

    resp = client.get("/api/push/vapid-public-key")
    assert resp.status_code == 200, resp.text
    key = resp.json()["key"]
    raw = base64.urlsafe_b64decode(key + "=" * (-len(key) % 4))
    assert len(raw) == 65 and raw[0] == 4  # uncompressed P-256 point


def test_subscribe_requires_auth(client, push_enabled):
    assert client.post("/api/push/subscribe", json=SUB_BODY).status_code == 401
    assert client.post("/api/push/unsubscribe", json={"endpoint": ENDPOINT}).status_code == 401


def test_subscribe_upsert_and_unsubscribe(client, db, push_enabled):
    headers = _register(client, "push@example.com")

    resp = client.post("/api/push/subscribe", json=SUB_BODY, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["subscribed"] is True
    first_id = resp.json()["id"]

    # same endpoint again -> upsert (keys refreshed, still one row)
    refreshed = {**SUB_BODY, "keys": {"p256dh": "D" * 87, "auth": "e" * 32}}
    resp = client.post("/api/push/subscribe", json=refreshed, headers=headers)
    assert resp.json()["id"] == first_id
    count = db.scalar(select(func.count(WebPushSubscription.id)))
    assert count == 1
    row = db.get(WebPushSubscription, first_id)
    assert row.p256dh == "D" * 87

    # non-http endpoint rejected
    bad = {**SUB_BODY, "endpoint": "ftp://push.example.com/x"}
    assert client.post("/api/push/subscribe", json=bad, headers=headers).status_code == 422

    # unsubscribe (own subscription) -> pruned, idempotent
    resp = client.post("/api/push/unsubscribe", json={"endpoint": ENDPOINT}, headers=headers)
    assert resp.json() == {"removed": True}
    assert db.scalar(select(func.count(WebPushSubscription.id))) == 0
    resp = client.post("/api/push/unsubscribe", json={"endpoint": ENDPOINT}, headers=headers)
    assert resp.json() == {"removed": False}


def test_delivery_on_notify(client, db, push_enabled, monkeypatch):
    headers = _register(client, "deliver@example.com")
    me_id = client.get("/api/auth/me", headers=headers).json()["id"]
    client.post("/api/push/subscribe", json=SUB_BODY, headers=headers)

    calls: list[dict] = []
    monkeypatch.setattr(pywebpush, "webpush", lambda **kw: calls.append(kw))

    created = notify_users(
        db, "predictions_ready", "Predictions ready", "3 races", user_ids=[me_id]
    )
    assert created == 1
    assert len(calls) == 1
    sent = calls[0]
    payload = json.loads(sent["data"])
    assert payload == {"title": "Predictions ready", "body": "3 races"}
    assert sent["subscription_info"]["endpoint"] == ENDPOINT
    assert sent["subscription_info"]["keys"]["p256dh"] == "B" * 87
    assert sent["vapid_claims"]["sub"] == settings.vapid_claims_email
    assert sent["vapid_private_key"]  # resolved key handed to pywebpush

    # preference-off user gets no push
    calls.clear()
    prefs = client.get("/api/me/preferences", headers=headers).json()
    prefs["predictions_ready"] = False
    client.put("/api/me/preferences", headers=headers, json=prefs)
    assert notify_users(db, "predictions_ready", "Again", user_ids=[me_id]) == 0
    assert calls == []


def test_dead_endpoint_is_pruned(client, db, push_enabled, monkeypatch):
    headers = _register(client, "gone@example.com")
    me_id = client.get("/api/auth/me", headers=headers).json()["id"]
    client.post("/api/push/subscribe", json=SUB_BODY, headers=headers)

    def gone(**_kw):
        raise pywebpush.WebPushException(
            "Gone",
            response=types.SimpleNamespace(status_code=410, json=lambda: {}, text=""),
        )

    monkeypatch.setattr(pywebpush, "webpush", gone)
    notify_users(db, "fixtures", "Hello", user_ids=[me_id])
    assert db.scalar(select(func.count(WebPushSubscription.id))) == 0


def test_flaky_endpoint_dropped_after_max_failures(db, push_enabled, monkeypatch):
    from app.models import User
    from app.services.webpush_send import MAX_FAILURES, send_web_push

    user = User(email="flaky@example.com", password_hash="x")
    db.add(user)
    db.flush()
    db.add(
        WebPushSubscription(
            user_id=user.id, endpoint=ENDPOINT, p256dh="B" * 87, auth="c" * 32
        )
    )
    db.commit()

    calls = {"n": 0}

    def boom(**_kw):
        calls["n"] += 1
        raise RuntimeError("transient network error")

    monkeypatch.setattr(pywebpush, "webpush", boom)
    for i in range(1, MAX_FAILURES + 1):
        assert send_web_push(db, [user.id], "Hi") == 0
        sub = db.scalar(select(WebPushSubscription))
        if i < MAX_FAILURES:
            assert sub.failure_count == i
            assert "transient" in sub.last_error
        else:
            assert sub is None  # dropped
    assert calls["n"] == MAX_FAILURES
