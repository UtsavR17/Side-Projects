"""Notification reads + preference management (auth required)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import NOTIFICATION_CATEGORIES, Notification, NotificationPreference, User
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
