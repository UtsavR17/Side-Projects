"""Human-in-the-loop data import (Prompt B alternative when a source blocks bots).

Why this exists: mtcjockeyclub.com sits behind Cloudflare bot protection
(robots.txt answers 403), so automated scraping of the primary source is off the
table. Supertote allows crawling but renders its race data client-side, so there
is nothing server-side to parse. This module lets a HUMAN supply the data they
legitimately obtained by viewing pages in their own browser (saved HTML) or by
exporting a CSV, and feeds it through the SAME downstream pipeline
(clean -> entity resolution -> features -> train -> predict -> evaluate).

Two input kinds, auto-detected per file:

  fixtures HTML  — a saved MTC/Jockey Club race card / form guide page
  results HTML   — a saved results page
  fixtures CSV   — columns (header row required, case-insensitive):
                   date, race_no, venue, race_name, distance_m, race_class,
                   track_condition, horse, jockey, trainer, barrier,
                   weight_kg, odds
  results CSV    — columns: date, race_no, horse, finish_position,
                   margin, time_s, dn_category

Only `date`, `race_no` and `horse` are required; everything else is optional.
"""
from __future__ import annotations

import argparse
import csv
import io
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import RACE_COMPLETED, Horse, Race, RaceEntry, RaceResult
from pipeline.clean import flag_issue, normalize_name, resolve_or_create
from pipeline.parsing import iso_datetime, parse_date, parse_time, row_get, to_float, to_int
from pipeline.scrape_mtc import ingest_fixtures, parse_fixtures, parse_results

logger = logging.getLogger(__name__)
SOURCE = "manual-import"

# --------------------------------------------------------------------------- CSV
def load_fixtures_csv(text: str) -> tuple[list[dict], list[str]]:
    """Group fixture CSV rows into race cards shaped for `ingest_fixtures`."""
    warnings: list[str] = []
    cards: dict[tuple[str, int], dict] = {}
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ["CSV has no header row"]

    for lineno, row in enumerate(reader, start=2):
        horse = row_get(row, "horse", "horse_name", "runner")
        race_no = to_int(row_get(row, "race_no", "race", "race_number", "race_no."))
        if not horse or race_no is None:
            warnings.append(f"line {lineno}: missing race_no/horse — row skipped")
            continue

        raw_date = row_get(row, "date", "race_date", "meeting_date")
        race_dt = parse_date(raw_date) if raw_date else None
        key = (iso_datetime(race_dt) if race_dt else "", race_no)
        card = cards.get(key)
        if card is None:
            card = {
                "race_no": race_no,
                "date": iso_datetime(race_dt) if race_dt else None,
                "venue": row_get(row, "venue", "course") or "Champ de Mars",
                "race_name": row_get(row, "race_name", "name"),
                "distance_m": to_int(row_get(row, "distance_m", "distance", "dist")),
                "race_class": row_get(row, "race_class", "class"),
                "track_condition": row_get(row, "track_condition", "going", "condition"),
                "entries": [],
            }
            cards[key] = card
        else:  # fill race-level blanks from later rows
            for field, value in (
                ("race_name", row_get(row, "race_name", "name")),
                ("race_class", row_get(row, "race_class", "class")),
                ("track_condition", row_get(row, "track_condition", "going", "condition")),
                ("distance_m", to_int(row_get(row, "distance_m", "distance", "dist"))),
            ):
                if not card.get(field) and value:
                    card[field] = value

        card["entries"].append({
            "horse": horse,
            "jockey": row_get(row, "jockey", "jockey_name"),
            "trainer": row_get(row, "trainer", "trainer_name"),
            "barrier": to_int(row_get(row, "barrier", "draw", "stall", "gate")),
            "weight_kg": to_float(row_get(row, "weight_kg", "weight", "wt", "kg")),
            "odds": to_float(row_get(row, "odds", "sp", "price", "betting")),
        })

    if not cards:
        warnings.append("no usable rows found in CSV")
    return list(cards.values()), warnings


def load_results_csv(text: str) -> tuple[list[dict], list[str]]:
    """Parse a results CSV into the row shape `ingest_results_rows` expects."""
    warnings: list[str] = []
    rows: list[dict] = []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], ["CSV has no header row"]

    for lineno, raw in enumerate(reader, start=2):
        horse = row_get(raw, "horse", "horse_name", "runner")
        race_no = to_int(row_get(raw, "race_no", "race", "race_number"))
        if not horse or race_no is None:
            warnings.append(f"line {lineno}: missing race_no/horse — row skipped")
            continue
        raw_date = row_get(raw, "date", "race_date", "meeting_date")
        position = to_int(row_get(raw, "finish_position", "position", "pos",
                                  "place", "finish", "fp"))
        dn_category = row_get(raw, "dn_category", "dn", "status")
        if position is None and not dn_category:
            warnings.append(f"line {lineno}: no finish position or DN category — row skipped")
            continue
        rows.append({
            "date": parse_date(raw_date) if raw_date else None,
            "race_no": race_no,
            "horse": horse,
            "position": position,
            "margin": row_get(raw, "margin", "btn", "distance_beaten"),
            "time": parse_time(row_get(raw, "time_s", "time", "race_time")),
            "dn_category": dn_category,
        })

    if not rows:
        warnings.append("no usable result rows found in CSV")
    return rows, warnings


def _looks_like_csv(text: str) -> bool:
    head = text.lstrip()[:200]
    return not head.startswith("<")


def detect_kind(text: str, filename: str = "") -> str:
    """Return 'fixtures-csv' | 'results-csv' | 'fixtures-html' | 'results-html'."""
    lowered = filename.lower()
    is_csv = _looks_like_csv(text)
    if is_csv:
        header = (text.splitlines() or [""])[0].lower()
        if any(token in header for token in ("finish", "position", "place", "pos")):
            return "results-csv"
        return "fixtures-csv"
    if "result" in lowered:
        return "results-html"
    return "fixtures-html"


# ------------------------------------------------------------------- ingestion
def _find_race(db: Session, race_no: int, when: datetime | None) -> Race | None:
    """Match a race by number, preferring the correct day when a date is supplied."""
    query = select(Race).where(Race.race_no == race_no)
    if when is not None:
        day_start = when.replace(hour=0, minute=0, second=0, microsecond=0)
        race = db.scalar(
            query.where(Race.date >= day_start, Race.date < day_start + timedelta(days=1))
        )
        if race is not None:
            return race
    return db.scalar(query.order_by(Race.date.desc()).limit(1))


def _find_horse(db: Session, name: str) -> Horse | None:
    """Entity-resolution lookup: exact normalised name first, then a fuzzy contains."""
    norm = normalize_name(name)
    if not norm:
        return None
    horse = db.scalar(select(Horse).where(Horse.name_norm == norm))
    if horse is not None:
        return horse
    return db.scalar(select(Horse).where(Horse.name.ilike(f"%{name.strip()}%")).limit(1))


def ingest_results_rows(db: Session, rows: list[dict]) -> dict:
    """Write finish positions, matching on (date, race_no, horse) — flags misses."""
    stats = {"results_written": 0, "races_completed": 0,
             "unknown_horses": 0, "unmatched_entries": 0, "missing_races": 0}
    completed: set[int] = set()

    for row in rows:
        race = _find_race(db, row["race_no"], row.get("date"))
        if race is None:
            stats["missing_races"] += 1
            flag_issue(db, SOURCE, "missing_race",
                       f"result for race {row['race_no']} but no matching race exists",
                       context={k: str(v) for k, v in row.items()})
            continue

        horse = _find_horse(db, row["horse"])
        if horse is None:
            stats["unknown_horses"] += 1
            flag_issue(db, SOURCE, "unknown_horse",
                       f"result references unknown horse '{row['horse']}' (race {race.id})",
                       context={k: str(v) for k, v in row.items()})
            continue

        entry = db.scalar(
            select(RaceEntry).where(
                RaceEntry.race_id == race.id, RaceEntry.horse_id == horse.id
            )
        )
        if entry is None:
            stats["unmatched_entries"] += 1
            flag_issue(db, SOURCE, "unmatched_entry",
                       f"'{horse.name}' has a result in race {race.id} but is not on the card",
                       context={k: str(v) for k, v in row.items()})
            continue

        result = db.scalar(select(RaceResult).where(RaceResult.race_entry_id == entry.id))
        if result is None:
            result = RaceResult(race_entry_id=entry.id)
            db.add(result)
        result.finish_position = row.get("position")
        result.margin = row.get("margin")
        result.time_s = row.get("time")
        result.dn_category = row.get("dn_category")
        stats["results_written"] += 1
        completed.add(race.id)

    for race_id in completed:
        race = db.get(Race, race_id)
        if race is not None:
            race.status = RACE_COMPLETED
    db.commit()
    stats["races_completed"] = len(completed)
    return stats


# ------------------------------------------------------------------ dispatcher
def import_text(db: Session, text: str, kind: str = "auto",
                default_date: datetime | None = None, label: str = "") -> dict:
    """Import one document (CSV or saved HTML). Returns stats + warnings."""
    resolved = detect_kind(text, label) if kind in ("auto", "", None) else kind
    warnings: list[str] = []
    stats: dict = {}
    source_ref = f"{SOURCE}:{label or 'inline'}"

    if resolved == "fixtures-csv":
        cards, warnings = load_fixtures_csv(text)
        if cards:
            stats = ingest_fixtures(db, cards, source_url=source_ref,
                                    default_date=default_date)
    elif resolved == "results-csv":
        rows, warnings = load_results_csv(text)
        if rows:
            stats = ingest_results_rows(db, rows)
    elif resolved == "results-html":
        parsed, warnings = parse_results(text)
        rows = [{"race_no": r["race_no"], "horse": r["horse"], "position": r["position"],
                 "margin": r.get("margin"), "time": r.get("time"), "date": None}
                for r in parsed]
        if rows:
            stats = ingest_results_rows(db, rows)
    else:  # fixtures-html
        cards, warnings = parse_fixtures(text, source_ref)
        if cards:
            stats = ingest_fixtures(db, cards, source_url=source_ref,
                                    default_date=default_date)

    for warning in warnings:
        flag_issue(db, SOURCE, "parse_warning", warning, context={"file": label})
    return {"kind": resolved, "warnings": warnings, **stats}


def stage_import(paths: list[str], kind: str = "auto",
                 default_date: datetime | None = None) -> dict:
    """Import a set of saved pages / CSVs through the shared ingest path."""
    db = SessionLocal()
    results = []
    try:
        for raw_path in paths:
            path = Path(raw_path)
            if not path.exists():
                results.append({"file": str(path), "error": "file not found"})
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            outcome = import_text(db, text, kind=kind, default_date=default_date,
                                  label=path.name)
            outcome["file"] = path.name
            results.append(outcome)
            logger.info("imported %s -> %s", path.name, outcome)
        return {"files": results, "count": len(results)}
    finally:
        db.close()


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Import human-supplied race cards / results (CSV or saved HTML)."
    )
    parser.add_argument("files", nargs="+", help="CSV or saved .html files to import")
    parser.add_argument("--kind", default="auto",
                        choices=["auto", "fixtures-csv", "results-csv",
                                 "fixtures-html", "results-html"])
    parser.add_argument("--date", default=None,
                        help="fallback date (YYYY-MM-DD) for files that omit one")
    args = parser.parse_args(argv)

    fallback = parse_date(args.date) if args.date else None
    for item in stage_import(args.files, kind=args.kind, default_date=fallback)["files"]:
        print(item)


if __name__ == "__main__":
    main()


