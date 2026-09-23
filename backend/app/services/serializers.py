"""DB -> JSON payload serializers shared by routers and the cache warmer.

Everything here returns plain dicts so payloads can be cached verbatim.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Horse,
    HorseFormSnapshot,
    Jockey,
    ModelPerformance,
    Prediction,
    Race,
    RaceEntry,
    Trainer,
)


def race_summary_dict(race: Race) -> dict:
    return {
        "id": race.id,
        "date": race.date.isoformat() if race.date else None,
        "venue": race.venue,
        "race_no": race.race_no,
        "race_name": race.race_name,
        "distance_m": race.distance_m,
        "race_class": race.race_class,
        "track_condition": race.track_condition,
        "weather": race.weather,
        "status": race.status,
    }


def race_detail_dict(db: Session, race: Race) -> dict:
    entries = db.scalars(
        select(RaceEntry)
        .where(RaceEntry.race_id == race.id)
        .options(
            joinedload(RaceEntry.horse),
            joinedload(RaceEntry.jockey),
            joinedload(RaceEntry.trainer),
            joinedload(RaceEntry.result),
        )
    ).unique().all()

    preds = db.scalars(
        select(Prediction)
        .where(Prediction.race_id == race.id)
        .options(joinedload(Prediction.explanations))
    ).unique().all()
    preds_by_horse: dict[int, list[Prediction]] = {}
    for p in preds:
        preds_by_horse.setdefault(p.horse_id, []).append(p)

    out = race_summary_dict(race)
    out["entries"] = []
    for e in sorted(entries, key=lambda x: (x.barrier or 99, x.id)):
        out["entries"].append(
            {
                "id": e.id,
                "barrier": e.barrier,
                "weight_kg": e.weight_kg,
                "odds": e.odds,
                "scratched": e.scratched,
                "horse_id": e.horse_id,
                "horse_name": e.horse.name if e.horse else "?",
                "jockey_id": e.jockey_id,
                "jockey_name": e.jockey.name if e.jockey else None,
                "trainer_id": e.trainer_id,
                "trainer_name": e.trainer.name if e.trainer else None,
                "result": (
                    {
                        "finish_position": e.result.finish_position,
                        "margin": e.result.margin,
                        "time_s": e.result.time_s,
                        "dn_category": e.result.dn_category,
                    }
                    if e.result
                    else None
                ),
                "predictions": [
                    {
                        "id": p.id,
                        "model_name": p.model_name,
                        "win_prob": p.win_prob,
                        "place_prob": p.place_prob,
                        "predicted_rank": p.predicted_rank,
                        "confidence": p.confidence,
                        "generated_at": p.generated_at.isoformat() if p.generated_at else None,
                        "explanations": [
                            {
                                "factor": x.factor,
                                "direction": x.direction,
                                "weight": x.weight,
                                "detail": x.detail,
                            }
                            for x in sorted(
                                p.explanations,
                                key=lambda x: -abs(x.weight),
                            )
                        ],
                    }
                    for p in sorted(
                        preds_by_horse.get(e.horse_id, []),
                        key=lambda p: p.model_name,
                    )
                ],
            }
        )
    return out
