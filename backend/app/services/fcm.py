"""Firebase Cloud Messaging (HTTP v1) — optional delivery channel.

Requires a Google service-account JSON for a Firebase project. Token
registration (device tokens per user) is intentionally deferred to the Flutter
stage; this module is wired in so the pipeline can push the moment tokens exist.
"""
from __future__ import annotations

import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

FCM_ENDPOINT = (
    "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
)


def _access_token() -> str | None:
    """Mint an OAuth2 access token from the service account (stdlib only)."""
    try:
        import jwt as pyjwt  # PyJWT can sign RS256 for the JWT exchange
    except ImportError:  # pragma: no cover
        return None
    creds = json.loads(settings.fcm_credentials_json)
    now = int(__import__("time").time())
    assertion = pyjwt.encode(
        {
            "iss": creds["client_email"],
            "scope": "https://www.googleapis.com/auth/firebase.messaging",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
        },
        creds["private_key"],
        algorithm="RS256",
    )
    resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("access_token")


def send_broadcast(category: str, title: str, body: str) -> int:
    """Send a push to all registered device tokens. Returns sends attempted."""
    from app.models import DeviceToken

    from app.db import SessionLocal

    db = SessionLocal()
    try:
        tokens = [t.token for t in db.query(DeviceToken).all()]
        if not tokens:
            return 0
        token = _access_token()
        if not token:
            return 0
        url = FCM_ENDPOINT.format(project_id=settings.fcm_project_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        sent = 0
        for device_token in tokens:
            payload = {
                "message": {
                    "token": device_token,
                    "notification": {"title": title, "body": body},
                    "data": {"category": category},
                }
            }
            try:
                r = httpx.post(url, json=payload, headers=headers, timeout=10)
                if r.status_code == 200:
                    sent += 1
                else:
                    logger.warning("FCM send failed: %s %s", r.status_code, r.text[:200])
            except httpx.HTTPError as exc:
                logger.warning("FCM send error: %s", exc)
        return sent
    finally:
        db.close()
