"""Horse profile payloads (career, latest precomputed snapshot, recent form)."""
from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Horse, HorseFormSnapshot, Jockey, Race, RaceEntry, RaceResult

# Re-exported so routers can import everything profile-related from one place.
from app.services.people_stats import person_profile_dict  # noqa: F401


def horse_profile_dict(db: Session, horse: Horse) -> dict:
    snapshot = db.scalars(
        select(HorseFormSnapshot)
        .where(HorseFormSnapshot.horse_id == horse.id)
        .order_by(HorseFormSnapshot.as_of_date.desc())
        .limit(1)
    ).first()

    runs, wins, places, avg_finish = _career_stats(db, horse.id)

    recent = db.execute(
        select(Race, RaceEntry, RaceResult, Jockey)
        .join(RaceEntry, RaceEntry.race_id == Race.id)
        .outerjoin(RaceResult, RaceResult.race_entry_id == RaceEntry.id)
        .outerjoin(Jockey, Jockey.id == RaceEntry.jockey_id)
        .where(RaceEntry.horse_id == horse.id, RaceResult.id.isnot(None))
        .order_by(Race.date.desc())
        .limit(15)
    ).all()

    return {
        "id": horse.id,
        "name": horse.name,
        "sex": horse.sex,
        "sire": horse.sire,
        "dam": horse.dam,
        "foaling_year": horse.foaling_year,
        "notes": horse.notes,
        "career": {
            "runs": runs,
            "wins": wins,
            "places": places,
            "win_rate": round(wins / runs, 4) if runs else 0.0,
            "place_rate": round(places / runs, 4) if runs else 0.0,
            "avg_finish": round(avg_finish, 2) if avg_finish is not None else None,
        },
        "snapshot": (
            {
                "as_of_date": snapshot.as_of_date.isoformat(),
                "form_score": snapshot.form_score,
                "days_since_last_race": snapshot.days_since_last_race,
                "by_distance": snapshot.by_distance,
                "by_track_condition": snapshot.by_track_condition,
            }
            if snapshot
            else None
        ),
        "recent_form": [
            {
                "date": race.date.isoformat() if race.date else None,
                "race_no": race.race_no,
                "venue": race.venue,
                "distance_m": race.distance_m,
                "track_condition": race.track_condition,
                "finish_position": result.finish_position if result else None,
                "dn_category": result.dn_category if result else None,
                "odds": entry.odds,
                "weight_kg": entry.weight_kg,
                "jockey_name": jockey.name if jockey else None,
                "race_id": race.id,
            }
            for race, entry, result, jockey in recent
        ],
    }


def _career_stats(db: Session, horse_id: int) -> tuple[int, int, int, float | None]:
    row = db.execute(
        select(
            func.count(RaceResult.id),
            func.sum(case((RaceResult.finish_position == 1, 1), else_=0)),
            func.sum(case((RaceResult.finish_position <= 3, 1), else_=0)),
            func.avg(RaceResult.finish_position),
        )
        .select_from(RaceResult)
        .join(RaceEntry, RaceEntry.id == RaceResult.race_entry_id)
        .where(RaceEntry.horse_id == horse_id, RaceResult.finish_position.isnot(None))
    ).one()
    runs = int(row[0] or 0)
    avg = float(row[3]) if row[3] is not None else None
    return runs, int(row[1] or 0), int(row[2] or 0), avg
