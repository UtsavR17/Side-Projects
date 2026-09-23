"""Jockey & trainer profiles."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache import get_json_or_compute
from app.db import get_db
from app.models import Jockey, Trainer
from app.services import cache_keys
from app.services.profiles import person_profile_dict

router = APIRouter(prefix="/api", tags=["people"])


@router.get("/jockeys")
def list_jockeys(
    search: str = Query("", max_length=120),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    key = f"jockeys:search:{search.lower()}:{limit}"

    def compute():
        query = select(Jockey).order_by(Jockey.name)
        if search:
            query = query.where(Jockey.name.ilike(f"%{search}%"))
        rows = db.scalars(query.limit(limit)).all()
        return {"jockeys": [{"id": j.id, "name": j.name} for j in rows]}

    return get_json_or_compute(key, compute, ttl=120)


@router.get("/jockeys/{jockey_id}")
def jockey_profile(jockey_id: int, db: Session = Depends(get_db)):
    key = cache_keys.jockey_key(jockey_id)

    def compute():
        jockey = db.get(Jockey, jockey_id)
        if jockey is None:
            return None
        return person_profile_dict(db, jockey, "jockey")

    result = get_json_or_compute(key, compute)
    if result is None:
        raise HTTPException(404, "Jockey not found")
    return result


@router.get("/trainers")
def list_trainers(
    search: str = Query("", max_length=120),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    key = f"trainers:search:{search.lower()}:{limit}"

    def compute():
        query = select(Trainer).order_by(Trainer.name)
        if search:
            query = query.where(Trainer.name.ilike(f"%{search}%"))
        rows = db.scalars(query.limit(limit)).all()
        return {"trainers": [{"id": t.id, "name": t.name} for t in rows]}

    return get_json_or_compute(key, compute, ttl=120)


@router.get("/trainers/{trainer_id}")
def trainer_profile(trainer_id: int, db: Session = Depends(get_db)):
    key = cache_keys.trainer_key(trainer_id)

    def compute():
        trainer = db.get(Trainer, trainer_id)
        if trainer is None:
            return None
        return person_profile_dict(db, trainer, "trainer")

    result = get_json_or_compute(key, compute)
    if result is None:
        raise HTTPException(404, "Trainer not found")
    return result
