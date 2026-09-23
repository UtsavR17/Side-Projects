"""Feature-engineering stage (Prompt B.3): precomputed horse_form_snapshots.

Snapshots are computed strictly from races BEFORE `as_of_date` (no leakage)
and are the single source of distance/track-condition features for both the
ML dataset builder and the profile pages.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Horse, HorseFormSnapshot, RACE_SCHEDULED, Race, RaceEntry, RaceResult
from app.services.form_stats import (
    aggregate_stats,
    condition_index,
    distance_bucket,
    form_score,
)

logger = logging.getLogger(__name__)


def history_before(db: Session, horse_id: int, as_of: date) -> list[tuple[datetime, Race, int | None]]:
    """Chronological (race_date, race, finish) strictly before as_of."""
    rows = db.execute(
        select(Race, RaceResult.finish_position)
        .join(RaceEntry, RaceEntry.race_id == Race.id)
        .join(RaceResult, RaceResult.race_entry_id == RaceEntry.id)
        .where(RaceEntry.horse_id == horse_id, Race.date < datetime.combine(as_of, datetime.min.time()))
        .order_by(Race.date.asc())
    ).all()
    return [(race.date, race, pos) for race, pos in rows]


def build_snapshot(db: Session, horse_id: int, as_of: date) -> HorseFormSnapshot:
    hist = history_before(db, horse_id, as_of)
    positions = [pos for _, _, pos in hist]
    stats = aggregate_stats(positions)

    days_since = None
    if hist:
        last_dt = hist[-1][0]
        days_since = (datetime.combine(as_of, datetime.min.time()) - last_dt).days

    # Distance / condition breakdowns
    by_distance: dict[str, dict] = {}
    by_condition: dict[str, dict] = {}
    cond_positions: dict[str, list[int | None]] = {}
    dist_positions: dict[str, list[int | None]] = {}
    for _, race, pos in hist:
        dbucket = distance_bucket(race.distance_m)
        if dbucket:
            dist_positions.setdefault(dbucket, []).append(pos)
        ckey = (race.track_condition or "unknown").lower()
        cond_positions.setdefault(ckey, []).append(pos)
    for bucket, positions in dist_positions.items():
        by_distance[bucket] = aggregate_stats(positions)
    for cond, positions in cond_positions.items():
        stats_c = aggregate_stats(positions)
        stats_c["condition_index"] = condition_index(cond)
        by_condition[cond] = stats_c

    score = form_score(
        runs=stats["runs"],
        wins=stats["wins"],
        places=stats["places"],
        avg_finish=stats["avg_finish"],
        days_since_last=days_since,
        recent_finishes=[p for p in positions[-5:] if p is not None],
    )

    existing = db.scalar(
        select(HorseFormSnapshot).where(
            HorseFormSnapshot.horse_id == horse_id, HorseFormSnapshot.as_of_date == as_of
        )
    )
    snap = existing or HorseFormSnapshot(horse_id=horse_id, as_of_date=as_of)
    snap.runs = stats["runs"]
    snap.wins = stats["wins"]
    snap.places = stats["places"]
    snap.win_rate = stats["win_rate"]
    snap.place_rate = stats["place_rate"]
    snap.avg_finish = stats["avg_finish"]
    snap.days_since_last_race = days_since
    snap.form_score = score
    snap.by_distance = by_distance
    snap.by_track_condition = by_condition
    if existing is None:
        db.add(snap)
    return snap


def stage_features(db: Session | None = None, horizon_days: int = 14) -> dict:
    """Recompute snapshots for every horse entered in an upcoming race."""
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        window_end = datetime.utcnow().date() + timedelta(days=horizon_days)
        races = db.scalars(
            select(Race).where(
                Race.status == RACE_SCHEDULED,
                Race.date >= datetime.utcnow(),
                Race.date <= datetime.combine(window_end, datetime.min.time()),
            )
        ).all()
        horse_days: dict[int, date] = {}
        for race in races:
            entries = db.scalars(select(RaceEntry).where(RaceEntry.race_id == race.id)).all()
            for entry in entries:
                current = horse_days.get(entry.horse_id)
                race_day = race.date.date()
                if current is None or race_day < current:
                    horse_days[entry.horse_id] = race_day

        written = 0
        for horse_id, as_of in horse_days.items():
            build_snapshot(db, horse_id, as_of)
            written += 1
        db.commit()
        logger.info("features: %d snapshots recomputed", written)
        return {"snapshots": written, "horses": len(horse_days)}
    finally:
        if own_session:
            db.close()
