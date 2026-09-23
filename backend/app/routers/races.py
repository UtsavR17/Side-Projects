"""Race list / detail endpoints — cache-first reads (Prompt A.3)."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.cache import get_json_or_compute
from app.db import get_db
from app.models import RACE_SCHEDULED, Race
from app.services import cache_keys
from app.services.serializers import race_detail_dict, race_summary_dict

router = APIRouter(prefix="/api/races", tags=["races"])


@router.get("")
def list_races(
    upcoming: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    key = cache_keys.upcoming_key() if upcoming else f"races:all:{limit}"

    def compute():
        query = select(Race).order_by(Race.date.asc()).limit(limit)
        if upcoming:
            cutoff = datetime.utcnow() - timedelta(hours=12)
            query = select(Race).where(
                Race.date >= cutoff, Race.status == RACE_SCHEDULED
            ).order_by(Race.date.asc()).limit(limit)
        races = db.scalars(query).all()
        return {"races": [race_summary_dict(r) for r in races]}

    return get_json_or_compute(key, compute)


@router.get("/{race_id}")
def race_detail(race_id: int, db: Session = Depends(get_db)):
    key = cache_keys.race_key(race_id)

    def compute():
        race = db.get(Race, race_id)
        if race is None:
            return None
        return race_detail_dict(db, race)

    result = get_json_or_compute(key, compute)
    if result is None:
        raise HTTPException(404, "Race not found")
    return result
