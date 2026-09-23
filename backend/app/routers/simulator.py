"""Race simulator — dedicated what-if endpoint (§11 / Prompt D).

Re-weights STORED ensemble probabilities using precomputed distance /
track-condition profiles under a changed race context. Never triggers a
scrape or a model fit — it keeps the app's "reads only" contract intact.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import HorseFormSnapshot, Prediction, Race, RaceEntry
from app.services.whatif import adjusted_prob

router = APIRouter(prefix="/api/simulator", tags=["simulator"])


class WhatIfIn(BaseModel):
    race_id: int
    distance_m: int | None = Field(default=None, ge=200, le=6000)
    track_condition: str | None = None


@router.post("/what-if")
def what_if(body: WhatIfIn, db: Session = Depends(get_db)):
    race = db.get(Race, body.race_id)
    if race is None:
        raise HTTPException(404, "Race not found")

    entries = db.scalars(
        select(RaceEntry).where(RaceEntry.race_id == race.id, RaceEntry.scratched.is_(False))
    ).all()
    preds = {
        p.horse_id: p
        for p in db.scalars(
            select(Prediction).where(
                Prediction.race_id == race.id, Prediction.model_name == "ensemble"
            )
        ).all()
    }
    if not preds or not entries:
        raise HTTPException(400, "No stored ensemble predictions for this race yet")

    new_distance = body.distance_m if body.distance_m is not None else race.distance_m
    new_condition = (
        body.track_condition if body.track_condition is not None else race.track_condition
    )

    picks = []
    for entry in entries:
        base = preds.get(entry.horse_id)
        if base is None:
            continue
        snap = db.scalars(
            select(HorseFormSnapshot)
            .where(HorseFormSnapshot.horse_id == entry.horse_id)
            .order_by(HorseFormSnapshot.as_of_date.desc())
            .limit(1)
        ).first()
        adjusted = adjusted_prob(
            base.win_prob, snap, race.distance_m, race.track_condition,
            new_distance, new_condition,
        )
        picks.append(
            {
                "horse_id": entry.horse_id,
                "horse_name": entry.horse.name if entry.horse else "?",
                "base_win_prob": round(base.win_prob, 4),
                "_adj": adjusted,
            }
        )

    # Re-normalize so the field remains a probability distribution.
    total = sum(p["_adj"] for p in picks) or 1.0
    for p in picks:
        p["adjusted_win_prob"] = round(p["_adj"] / total, 4)
        p["delta"] = round(p["adjusted_win_prob"] - p["base_win_prob"], 4)
        del p["_adj"]
    picks.sort(key=lambda p: -p["adjusted_win_prob"])
    for i, p in enumerate(picks, start=1):
        p["rank"] = i

    return {
        "race_id": race.id,
        "context": {
            "distance_m": {"from": race.distance_m, "to": new_distance},
            "track_condition": {"from": race.track_condition, "to": new_condition},
        },
        "picks": picks,
        "method": "heuristic-reweight (stored ensemble x distance/condition fit)",
    }
