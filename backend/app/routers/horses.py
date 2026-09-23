"""Horse profiles, search, follow/unfollow."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache import get_json_or_compute
from app.db import get_db
from app.models import FollowedHorse, Horse, User
from app.security import get_current_user
from app.services import cache_keys
from app.services.profiles import horse_profile_dict

router = APIRouter(prefix="/api/horses", tags=["horses"])


@router.get("")
def list_horses(
    search: str = Query("", max_length=120),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    key = f"horses:search:{search.lower()}:{limit}"

    def compute():
        query = select(Horse).where(Horse.merged_into_id.is_(None)).order_by(Horse.name)
        if search:
            query = select(Horse).where(
                Horse.merged_into_id.is_(None), Horse.name.ilike(f"%{search}%")
            ).order_by(Horse.name)
        horses = db.scalars(query.limit(limit)).all()
        return {"horses": [{"id": h.id, "name": h.name} for h in horses]}

    return get_json_or_compute(key, compute, ttl=120)


@router.get("/{horse_id}")
def horse_profile(horse_id: int, db: Session = Depends(get_db)):
    key = cache_keys.horse_key(horse_id)

    def compute():
        horse = db.get(Horse, horse_id)
        if horse is None:
            return None
        return horse_profile_dict(db, horse)

    result = get_json_or_compute(key, compute)
    if result is None:
        raise HTTPException(404, "Horse not found")
    return result


@router.post("/{horse_id}/follow")
def follow_horse(
    horse_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    horse = db.get(Horse, horse_id)
    if horse is None:
        raise HTTPException(404, "Horse not found")
    existing = db.scalar(
        select(FollowedHorse).where(
            FollowedHorse.user_id == user.id, FollowedHorse.horse_id == horse_id
        )
    )
    if existing is None:
        db.add(FollowedHorse(user_id=user.id, horse_id=horse_id))
        db.commit()
    return {"horse_id": horse_id, "following": True}


@router.delete("/{horse_id}/follow")
def unfollow_horse(
    horse_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(FollowedHorse).where(
            FollowedHorse.user_id == user.id, FollowedHorse.horse_id == horse_id
        )
    )
    if row is not None:
        db.delete(row)
        db.commit()
    return {"horse_id": horse_id, "following": False}
