"""Jockey / trainer profile stats + model leaderboard payloads."""
from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Horse, Jockey, ModelPerformance, Race, RaceEntry, RaceResult, Trainer


def person_profile_dict(db: Session, person: Jockey | Trainer, kind: str) -> dict:
    fk = RaceEntry.jockey_id if kind == "jockey" else RaceEntry.trainer_id
    rides = db.execute(
        select(
            func.count(RaceResult.id),
            func.sum(case((RaceResult.finish_position == 1, 1), else_=0)),
            func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)),
        )
        .select_from(RaceResult)
        .join(RaceEntry, RaceEntry.id == RaceResult.race_entry_id)
        .where(fk == person.id, RaceResult.finish_position.isnot(None))
    ).one()
    runs = int(rides[0] or 0)
    wins = int(rides[1] or 0)
    places = int(rides[2] or 0)

    recent = db.execute(
        select(Race, RaceEntry, RaceResult, Horse)
        .join(RaceEntry, RaceEntry.race_id == Race.id)
        .outerjoin(RaceResult, RaceResult.race_entry_id == RaceEntry.id)
        .join(Horse, Horse.id == RaceEntry.horse_id)
        .where(fk == person.id, RaceResult.id.isnot(None))
        .order_by(Race.date.desc())
        .limit(15)
    ).all()

    return {
        "id": person.id,
        "name": person.name,
        "license_no": person.license_no,
        "stats": {
            "rides": runs,
            "wins": wins,
            "places": places,
            "win_rate": round(wins / runs, 4) if runs else 0.0,
            "place_rate": round(places / runs, 4) if runs else 0.0,
        },
        "recent": [
            {
                "date": race.date.isoformat() if race.date else None,
                "race_no": race.race_no,
                "horse_id": horse.id,
                "horse_name": horse.name,
                "distance_m": race.distance_m,
                "track_condition": race.track_condition,
                "finish_position": result.finish_position if result else None,
                "race_id": race.id,
            }
            for race, entry, result, horse in recent
        ],
    }
