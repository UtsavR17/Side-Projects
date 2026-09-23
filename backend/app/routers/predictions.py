"""Predictions: raw prediction reads, history vs results, model leaderboard."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.cache import get_json_or_compute
from app.db import get_db
from app.models import RACE_COMPLETED, Prediction, Race, RaceEntry, RaceResult
from app.services import cache_keys
from app.services.leaderboard import leaderboard_dict

router = APIRouter(prefix="/api", tags=["predictions"])


@router.get("/predictions")
def list_predictions(
    race_id: int | None = None,
    model_name: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    key = f"predictions:{race_id}:{model_name}:{limit}"

    def compute():
        query = select(Prediction).options(joinedload(Prediction.explanations))
        if race_id is not None:
            query = query.where(Prediction.race_id == race_id)
        if model_name:
            query = query.where(Prediction.model_name == model_name)
        rows = db.scalars(query.order_by(Prediction.generated_at.desc()).limit(limit)).unique().all()
        return {
            "predictions": [
                {
                    "id": p.id,
                    "race_id": p.race_id,
                    "horse_id": p.horse_id,
                    "model_name": p.model_name,
                    "win_prob": p.win_prob,
                    "place_prob": p.place_prob,
                    "predicted_rank": p.predicted_rank,
                    "confidence": p.confidence,
                    "generated_at": p.generated_at.isoformat() if p.generated_at else None,
                }
                for p in rows
            ]
        }

    return get_json_or_compute(key, compute, ttl=120)


@router.get("/predictions/history")
def prediction_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    key = cache_keys.predictions_history_key(limit, offset)

    def compute():
        races = db.scalars(
            select(Race)
            .where(Race.status == RACE_COMPLETED)
            .order_by(Race.date.desc())
            .offset(offset)
            .limit(limit)
        ).all()

        out = []
        for race in races:
            preds = db.scalars(
                select(Prediction)
                .where(Prediction.race_id == race.id, Prediction.model_name == "ensemble")
            ).all()
            if not preds:
                continue
            entries = {
                e.id: e
                for e in db.scalars(select(RaceEntry).where(RaceEntry.race_id == race.id)).all()
            }
            results = db.scalars(
                select(RaceResult).where(RaceResult.race_entry_id.in_(list(entries)))
            ).all()
            winner_entry_id = next(
                (r.race_entry_id for r in results if r.finish_position == 1), None
            )
            winner_horse_id = entries[winner_entry_id].horse_id if winner_entry_id else None
            top = min(preds, key=lambda p: p.predicted_rank)
            out.append(
                {
                    "race": {
                        "id": race.id,
                        "date": race.date.isoformat() if race.date else None,
                        "venue": race.venue,
                        "race_no": race.race_no,
                        "distance_m": race.distance_m,
                        "track_condition": race.track_condition,
                    },
                    "top_pick_horse_id": top.horse_id,
                    "top_pick_prob": top.win_prob,
                    "actual_winner_horse_id": winner_horse_id,
                    "hit": top.horse_id == winner_horse_id,
                }
            )
        return {"history": out, "limit": limit, "offset": offset}

    return get_json_or_compute(key, compute, ttl=180)


@router.get("/leaderboard")
def leaderboard(db: Session = Depends(get_db)):
    return get_json_or_compute(cache_keys.leaderboard_key(), lambda: leaderboard_dict(db))
