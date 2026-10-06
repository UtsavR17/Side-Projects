"""Authenticated *me* endpoints: followed horses + push device registration.

Used by the mobile client (Prompt E): the followed-horses screen and the FCM
token registration step.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DeviceToken, FollowedHorse, Horse, User
from app.security import get_current_user

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/followed-horses")
def followed_horses(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Horses this user follows (newest additions sorted by name)."""
    horses = db.scalars(
        select(Horse)
        .join(FollowedHorse, FollowedHorse.horse_id == Horse.id)
        .where(FollowedHorse.user_id == user.id)
        .order_by(Horse.name)
    ).all()
    return {"horses": [{"id": h.id, "name": h.name} for h in horses]}


class DeviceTokenIn(BaseModel):
    token: str = Field(min_length=8, max_length=500)
    platform: str | None = Field(default=None, max_length=20)


@router.post("/device-tokens")
def register_device_token(
    body: DeviceTokenIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register (or refresh) a mobile push token for FCM delivery."""
    row = db.scalar(
        select(DeviceToken).where(
            DeviceToken.user_id == user.id, DeviceToken.token == body.token
        )
    )
    if row is None:
        row = DeviceToken(user_id=user.id, token=body.token, platform=body.platform)
        db.add(row)
        db.commit()
        db.refresh(row)
    elif body.platform and row.platform != body.platform:
        row.platform = body.platform
        db.commit()
    return {"registered": True, "id": row.id}


@router.delete("/device-tokens")
def unregister_device_token(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stop pushing to a device (e.g. on sign-out)."""
    row = db.scalar(
        select(DeviceToken).where(
            DeviceToken.user_id == user.id, DeviceToken.token == token
        )
    )
    if row is not None:
        db.delete(row)
        db.commit()
    return {"removed": row is not None}