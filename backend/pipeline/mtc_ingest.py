"""Write parsed MTC race data (HTML page or official PDF export) into the schema.

Shares entity resolution with the rest of the pipeline, so horses/jockeys/
trainers created here behave exactly like scraped or CSV-imported ones — and any
miss is flagged rather than invented.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Horse,
    Jockey,
    Race,
    RaceEntry,
    RaceResult,
    Trainer,
    RACE_COMPLETED,
    RACE_SCHEDULED,
)
from pipeline.clean import flag_issue, normalize_name, resolve_or_create

logger = logging.getLogger(__name__)
SOURCE = "mtc-import"
VENUE = "Champ de Mars"


def _resolve_horse(db: Session, name: str, external_id: str | None) -> Horse | None:
    """Match on the MTC horse id first (stable), then on the normalised name."""
    norm = normalize_name(name)
    if not norm:
        return None
    horse = None
    if external_id:
        horse = db.scalar(select(Horse).where(Horse.external_id == str(external_id)))
    if horse is None:
        horse = db.scalar(select(Horse).where(Horse.name_norm == norm))
    if horse is None:
        horse = Horse(name=name.strip(), name_norm=norm,
                      external_id=str(external_id) if external_id else None)
        db.add(horse)
        db.flush()
        return horse
    if external_id and not horse.external_id:
        horse.external_id = str(external_id)
    return horse


def _race_datetime(parsed: dict, default_date: datetime | None) -> tuple[datetime, list[str]]:
    warnings: list[str] = []
    when = parsed.get("date") or default_date
    if when is None:
        warnings.append("no date on the document; used today's date")
        when = datetime.utcnow()
    label = parsed.get("race_time_label")
    if label and ":" in str(label):
        try:
            hour, minute = (int(part) for part in str(label).split(":")[:2])
            when = when.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return when, warnings
        except ValueError:
            pass
    return when.replace(hour=14, minute=0, second=0, microsecond=0), warnings


def ingest_mtc_race(db: Session, parsed: dict, source_label: str = "",
                    default_date: datetime | None = None) -> dict:
    """Upsert one parsed race (with its runners and results). Idempotent."""
    stats = {"races_created": 0, "races_updated": 0, "entries": 0,
             "results_written": 0, "horses_created": 0, "warnings": []}
    race_no = parsed.get("race_no")
    if not race_no:
        flag_issue(db, SOURCE, "missing_field", "parsed document has no race number",
                   context={"file": source_label})
        stats["warnings"].append("no race number")
        return stats

    when, date_warnings = _race_datetime(parsed, default_date)
    stats["warnings"].extend(date_warnings)

    day_start = when.replace(hour=0, minute=0, second=0, microsecond=0)
    race = db.scalar(
        select(Race).where(
            Race.race_no == race_no,
            Race.venue == VENUE,
            Race.date >= day_start,
            Race.date < day_start + timedelta(days=1),
        )
    )
    if race is None:
        race = Race(date=when, race_no=race_no, venue=VENUE, status=RACE_SCHEDULED)
        db.add(race)
        db.flush()
        stats["races_created"] = 1
    else:
        race.date = when
        stats["races_updated"] = 1

    race.meeting_no = parsed.get("meeting_no") or race.meeting_no
    race.race_name = parsed.get("race_name") or race.race_name
    race.distance_m = parsed.get("distance_m") or race.distance_m
    race.race_class = parsed.get("race_class") or race.race_class
    race.prize = parsed.get("prize") or race.prize
    race.race_time_label = parsed.get("race_time_label") or race.race_time_label
    race.win_time_s = parsed.get("win_time_s") or race.win_time_s
    if parsed.get("tote_dividends"):
        race.tote_dividends = parsed["tote_dividends"]
    if parsed.get("sectional_times"):
        race.sectional_times = parsed["sectional_times"]
    if source_label:
        race.source_url = f"{SOURCE}:{source_label}"

    for runner in parsed.get("runners", []):
        horse = _resolve_horse(db, runner.get("horse") or "", runner.get("external_id"))
        if horse is None:
            flag_issue(db, SOURCE, "missing_field", "runner without a horse name",
                       context={"file": source_label, "race_no": race_no})
            continue

        jockey = resolve_or_create(db, Jockey, runner["jockey"]) if runner.get("jockey") else None
        trainer = resolve_or_create(db, Trainer, runner["trainer"]) if runner.get("trainer") else None

        entry = db.scalar(
            select(RaceEntry).where(
                RaceEntry.race_id == race.id, RaceEntry.horse_id == horse.id
            )
        )
        if entry is None:
            entry = RaceEntry(race_id=race.id, horse_id=horse.id)
            db.add(entry)
            db.flush()          # need entry.id before writing its result
            stats["entries"] += 1

        entry.saddle_no = runner.get("saddle_no") or entry.saddle_no
        entry.barrier = runner.get("barrier") or entry.barrier
        entry.weight_kg = runner.get("weight_kg") or entry.weight_kg
        entry.sp_odds = runner.get("sp_odds") or entry.sp_odds
        entry.odds = runner.get("sp_odds") or entry.odds      # SP powers the market feature
        entry.rating = runner.get("rating") or entry.rating
        entry.gear = runner.get("gear") or entry.gear
        entry.body_weight_kg = runner.get("body_weight_kg") or entry.body_weight_kg
        entry.body_weight_delta = runner.get("body_weight_delta") or entry.body_weight_delta
        entry.jockey_id = jockey.id if jockey else entry.jockey_id
        entry.trainer_id = trainer.id if trainer else entry.trainer_id
        if runner.get("claim_kg"):
            entry.notes = f"jockey claim -{runner['claim_kg']}kg"

        if runner.get("finish_position") is not None or runner.get("time_s") is not None:
            result = db.scalar(select(RaceResult).where(RaceResult.race_entry_id == entry.id))
            if result is None:
                result = RaceResult(race_entry_id=entry.id)
                db.add(result)
            result.finish_position = runner.get("finish_position")
            result.margin = str(runner.get("margin") or "")[:50] or None
            result.time_s = runner.get("time_s")
            result.sp_odds = runner.get("sp_odds")
            result.win_dividend = runner.get("win_dividend")
            result.place_dividend = runner.get("place_dividend")
            stats["results_written"] += 1

    if stats["results_written"]:
        race.status = RACE_COMPLETED
    elif when < datetime.utcnow():
        # The meeting has already run but this document (a nomination/preview
        # card) carries no finish positions — mark it done so it leaves the
        # upcoming queues; results can still be attached by a later import.
        race.status = RACE_COMPLETED

    db.commit()
    logger.info("mtc import %s -> %s", source_label or "inline", stats)
    return stats
