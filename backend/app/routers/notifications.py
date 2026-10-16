"""Notification reads + preference management + Web Push subscriptions (auth required)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import (
    NOTIFICATION_CATEGORIES,
    Notification,
    NotificationPreference,
    User,
    WebPushSubscription,
)
from app.schemas import NotificationPrefsIn, NotificationPrefsOut
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["notifications"])


@router.get("/notifications")
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    rows = db.scalars(query.order_by(Notification.created_at.desc()).limit(limit)).all()
    unread = db.scalars(
        select(Notification).where(
            Notification.user_id == user.id, Notification.is_read.is_(False)
        )
    ).all()
    return {
        "notifications": [
            {
                "id": n.id,
                "category": n.category,
                "title": n.title,
                "body": n.body,
                "data": n.data,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in rows
        ],
        "unread_count": len(unread),
    }


@router.post("/notifications/{notification_id}/read")
def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = db.get(Notification, notification_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    note.is_read = True
    db.commit()
    return {"id": note.id, "is_read": True}


@router.post("/notifications/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Notification).where(
            Notification.user_id == user.id, Notification.is_read.is_(False)
        )
    ).all()
    for note in rows:
        note.is_read = True
    db.commit()
    return {"marked": len(rows)}


def _prefs_or_create(db: Session, user: User) -> NotificationPreference:
    prefs = db.get(NotificationPreference, user.id)
    if prefs is None:
        prefs = NotificationPreference(user_id=user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


@router.get("/me/preferences", response_model=NotificationPrefsOut)
def get_prefs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _prefs_or_create(db, user)


@router.put("/me/preferences", response_model=NotificationPrefsOut)
def set_prefs(
    body: NotificationPrefsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = _prefs_or_create(db, user)
    for cat in NOTIFICATION_CATEGORIES:
        setattr(prefs, cat, getattr(body, cat))
    db.commit()
    db.refresh(prefs)
    return prefs


# --------------------------------------------------------------------- Web Push
class PushKeysIn(BaseModel):
    p256dh: str = Field(min_length=20, max_length=400)
    auth: str = Field(min_length=8, max_length=200)


class PushSubscribeIn(BaseModel):
    endpoint: str = Field(min_length=8, max_length=2000)
    keys: PushKeysIn

    @field_validator("endpoint")
    @classmethod
    def _http_endpoint(cls, v: str) -> str:
        if not v.startswith(("https://", "http://")):
            raise ValueError("endpoint must be an http(s) URL")
        return v


class PushUnsubscribeIn(BaseModel):
    endpoint: str = Field(min_length=8, max_length=2000)


@router.get("/push/vapid-public-key")
def vapid_public_key():
    """Browser `applicationServerKey` — public info, so no auth. 503 while
    web push is disabled or the VAPID key has not been generated yet."""
    from app.services.webpush_send import vapid_public_key_b64

    if not settings.web_push_enabled:
        raise HTTPException(503, "Web push is disabled on this server")
    key = vapid_public_key_b64()
    if key is None:
        raise HTTPException(503, "VAPID key not configured (run: python gen_vapid.py)")
    return {"key": key}


@router.post("/push/subscribe")
def push_subscribe(
    body: PushSubscribeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store (or refresh) this user's browser push subscription (RFC 8292)."""
    row = db.scalar(
        select(WebPushSubscription).where(WebPushSubscription.endpoint == body.endpoint)
    )
    if row is None:
        row = WebPushSubscription(
            user_id=user.id,
            endpoint=body.endpoint,
            p256dh=body.keys.p256dh,
            auth=body.keys.auth,
        )
        db.add(row)
    else:
        # same endpoint re-registered (new sign-in / browser reset)
        row.user_id = user.id
        row.p256dh = body.keys.p256dh
        row.auth = body.keys.auth
        row.failure_count = 0
        row.last_error = None
    db.commit()
    db.refresh(row)
    return {"subscribed": True, "id": row.id}


@router.post("/push/unsubscribe")
def push_unsubscribe(
    body: PushUnsubscribeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stop pushing to a browser subscription (idempotent)."""
    row = db.scalar(
        select(WebPushSubscription).where(
            WebPushSubscription.endpoint == body.endpoint,
            WebPushSubscription.user_id == user.id,
        )
    )
    if row is not None:
        db.delete(row)
        db.commit()
    return {"removed": row is not None}
