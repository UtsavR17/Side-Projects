"""Notification creation — called ONLY from the background pipeline (§10/§F.3),
never synchronously from a user request.

Delivery: rows in `notifications` (in-app + SSE), plus best-effort FCM push
when configured. Web Push would plug in here the same way.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache import cache
from app.config import settings
from app.models import Notification, NotificationPreference, User

logger = logging.getLogger(__name__)


def _pref_enabled(user: User, category: str) -> bool:
    if user.preferences is None:
        return True
    return bool(getattr(user.preferences, category, True))


def notify_users(
    db: Session,
    category: str,
    title: str,
    body: str = "",
    data: dict[str, Any] | None = None,
    user_ids: list[int] | None = None,
) -> int:
    """Create notifications for all opted-in users (or a specific subset)."""
    query = select(User).where(User.is_active.is_(True))
    if user_ids is not None:
        if not user_ids:
            return 0
        query = query.where(User.id.in_(user_ids))
    users = db.scalars(query).all()

    created = 0
    for user in users:
        if not _pref_enabled(user, category):
            continue
        note = Notification(
            user_id=user.id,
            category=category,
            title=title,
            body=body or None,
            data=data or None,
        )
        db.add(note)
        created += 1
    db.commit()

    # Push a live event so open SSE clients update immediately.
    cache.publish(
        "events",
        {"type": "notification", "category": category, "title": title, "count": created},
    )
    if created:
        _send_fcm_push(category, title, body)
    return created


def notify_followers_of_horses(
    db: Session,
    horse_ids: set[int],
    category: str,
    title: str,
    body: str = "",
    data: dict[str, Any] | None = None,
) -> int:
    from app.models import FollowedHorse

    if not horse_ids:
        return 0
    rows = db.scalars(
        select(FollowedHorse).where(FollowedHorse.horse_id.in_(horse_ids))
    ).all()
    return notify_users(
        db, category, title, body, data, user_ids=sorted({r.user_id for r in rows})
    )


def _send_fcm_push(category: str, title: str, body: str) -> None:
    """Best-effort Firebase Cloud Messaging HTTP v1 push.

    Disabled unless FCM_ENABLED=true with project id + service-account JSON —
    the in-app notification rows are the source of truth regardless.
    """
    if not settings.fcm_enabled or not settings.fcm_project_id:
        return
    try:
        # Lazy import so the core pipeline never depends on google libs.
        from app.services.fcm import send_broadcast

        send_broadcast(category, title, body)
    except Exception as exc:  # noqa: BLE001 — notifications must never break the pipeline
        logger.warning("FCM push failed: %s", exc)
