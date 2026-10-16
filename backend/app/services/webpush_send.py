"""Web Push delivery (RFC 8291/8292) — the browser-side twin of FCM.

Best-effort by design: the in-app `notifications` rows remain the source of
truth and a push failure must NEVER break the pipeline that called
notify_users(). Dead endpoints (404/410 from the push service) are pruned;
endpoints that keep failing are dropped after MAX_FAILURES attempts.

One-time setup:  python gen_vapid.py  (writes vapid_private.pem + prints env).
"""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import WebPushSubscription

logger = logging.getLogger(__name__)

MAX_FAILURES = 5  # drop a subscription after this many consecutive failures
GONE_STATUSES = (404, 410)  # push service: endpoint no longer exists


def vapid_key_arg() -> str | None:
    """Resolve VAPID_PRIVATE_KEY into what pywebpush accepts: an existing file
    path (it reads the file itself) or normalized PEM text. None if unset or
    pointing at a missing file."""
    value = (settings.vapid_private_key or "").strip()
    if not value:
        return None
    if "-----BEGIN" in value:
        return value.replace("\\n", "\n")
    if Path(value).is_file():
        return value
    logger.warning("VAPID_PRIVATE_KEY file not found: %s", value)
    return None


def vapid_public_key_b64() -> str | None:
    """Base64url(raw P-256 point) — the browser's `applicationServerKey`."""
    key = vapid_key_arg()
    if key is None:
        return None
    try:
        from cryptography.hazmat.primitives import serialization

        pem = key.encode() if key.startswith("-----BEGIN") else Path(key).read_bytes()
        private = serialization.load_pem_private_key(pem, password=None)
        raw = private.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    except Exception as exc:  # noqa: BLE001 — endpoint answers 503 instead
        logger.warning("VAPID public key derivation failed: %s", exc)
        return None


def send_web_push(db: Session, user_ids: list[int], title: str, body: str = "") -> int:
    """Push one notification to every stored subscription of these users.

    Returns how many pushes the service accepted. Individual failures never
    affect other subscriptions or the caller.
    """
    if not settings.web_push_enabled or not user_ids:
        return 0
    key = vapid_key_arg()
    if key is None:
        logger.warning("WEB_PUSH_ENABLED but no usable VAPID key — skipping")
        return 0
    try:
        import pywebpush
    except ImportError:  # pragma: no cover
        logger.warning("pywebpush not installed — pip install -r requirements.txt")
        return 0

    subs = db.scalars(
        select(WebPushSubscription).where(WebPushSubscription.user_id.in_(user_ids))
    ).all()
    if not subs:
        return 0

    payload = json.dumps({"title": title, "body": body})
    sent = 0
    for sub in subs:
        info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        try:
            pywebpush.webpush(
                subscription_info=info,
                data=payload,
                vapid_private_key=key,
                vapid_claims={"sub": settings.vapid_claims_email},
                ttl=3600,
            )
            sent += 1
            if sub.failure_count:
                sub.failure_count = 0
                sub.last_error = None
        except Exception as exc:  # noqa: BLE001 — never break the caller
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in GONE_STATUSES:
                db.delete(sub)
                logger.info("web push endpoint gone (%s) — subscription pruned", status)
                continue
            sub.failure_count = (sub.failure_count or 0) + 1
            sub.last_error = str(exc)[:480]
            if sub.failure_count >= MAX_FAILURES:
                db.delete(sub)
                logger.info("web push failed %dx — subscription pruned", MAX_FAILURES)
            else:
                logger.warning("web push failed (status=%s): %s", status, exc)
    db.commit()
    return sent