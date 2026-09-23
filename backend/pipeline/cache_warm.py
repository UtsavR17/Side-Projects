"""Cache-warming stage (Prompt B.4): after a pipeline run, push fresh payloads
into Redis so the API's very first read is already fast."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache import cache
from app.db import SessionLocal
from app.models import Horse, RACE_SCHEDULED, Race
from app.services import cache_keys
from app.services.leaderboard import leaderboard_dict
from app.services.profiles import horse_profile_dict
from app.services.serializers import race_detail_dict, race_summary_dict

logger = logging.getLogger(__name__)


def stage_cache_warm() -> dict:
    db = SessionLocal()
    warmed = {"races": 0, "horses": 0, "leaderboard": 0}
    try:
        # Start from a clean slate so stale entries disappear immediately.
        cache_keys.invalidate_all_profiles()

        upcoming = db.scalars(
            select(Race)
            .where(Race.status == RACE_SCHEDULED, Race.date >= datetime.utcnow() - timedelta(hours=12))
            .order_by(Race.date.asc())
            .limit(50)
        ).all()
        cache.set_json(
            cache_keys.upcoming_key(),
            {"races": [race_summary_dict(r) for r in upcoming]},
        )
        for race in upcoming:
            cache.set_json(cache_keys.race_key(race.id), race_detail_dict(db, race))
            warmed["races"] += 1
            for entry in race.entries:
                if entry.horse_id:
                    horse = db.get(Horse, entry.horse_id)
                    if horse:
                        cache.set_json(
                            cache_keys.horse_key(horse.id), horse_profile_dict(db, horse)
                        )
                        warmed["horses"] += 1

        cache.set_json(cache_keys.leaderboard_key(), leaderboard_dict(db))
        warmed["leaderboard"] = 1
        logger.info("cache warm complete: %s", warmed)
        return warmed
    finally:
        db.close()
