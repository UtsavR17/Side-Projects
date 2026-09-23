"""MTC fixtures/results scraping + ingestion (Prompt B.1).

Parsers are deliberately defensive: the source HTML structure can change, so
anything that can't be understood is flagged (data_quality_flags) instead of
raising — one bad page must never kill the scheduled run.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Horse, Jockey, Race, RaceEntry, RaceResult, RACE_SCHEDULED, Trainer
from pipeline.clean import flag_issue, resolve_or_create
from pipeline.http_client import fetch_html

logger = logging.getLogger(__name__)

_SOURCE = "mtc"
_DISTANCE_RE = re.compile(r"(\d{3,4})\s*m\b", re.IGNORECASE)
_DATE_RE = re.compile(r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2})")


def parse_fixtures(html: str, source_url: str) -> tuple[list[dict], list[str]]:
    """Extract race cards from a fixtures/form-guide page.

    Returns (races, warnings). Heuristic parser: finds race links/headings,
    race numbers, distances and runner tables. Warnings describe anything
    ambiguous that should be reviewed in the admin flag view.
    """
    soup = BeautifulSoup(html, "html.parser")
    warnings: list[str] = []
    races: list[dict] = []

    # Strategy 1: containers that look like individual race cards.
    cards = soup.select("[class*='race-card'], [class*='racecard'], article, .card")
    if not cards:
        # Strategy 2: any element whose text starts with "Race N"
        cards = [
            el
            for el in soup.find_all(["div", "section", "li"])
            if re.match(r"\s*race\s+\d+\b", el.get_text(" ", strip=True), re.IGNORECASE)
        ]

    for card in cards:
        text = card.get_text(" ", strip=True)
        m = re.search(r"\brace\s+(\d+)\b", text, re.IGNORECASE)
        if not m:
            continue
        race_no = int(m.group(1))
        dist = _DISTANCE_RE.search(text)
        runners = []
        for row in card.select("table tr"):
            cells = [c.get_text(" ", strip=True) for c in row.select("td")]
            if len(cells) >= 2:
                runners.append(_row_to_runner(cells))
        runners = [r for r in runners if r and r.get("horse")]
        races.append(
            {
                "race_no": race_no,
                "race_name": None,
                "distance_m": int(dist.group(1)) if dist else None,
                "race_class": None,
                "track_condition": None,
                "date": _extract_date(card.get_text(" ", strip=True)),
                "entries": runners,
            }
        )

    if not races:
        warnings.append("no race cards recognized on page")
    else:
        missing = [r["race_no"] for r in races if not r["entries"]]
        if missing:
            warnings.append(f"race(s) without runners parsed: {missing}")
    _ = source_url  # kept for future per-card deep links
    return races, warnings


def _extract_date(text: str) -> str | None:
    m = _DATE_RE.search(text)
    return m.group(1) if m else None


def _row_to_runner(cells: list[str]) -> dict | None:
    """Best-effort mapping of a table row to a runner.

    Expected shape varies: [horse, jockey, trainer, barrier, weight, odds]
    or [no, horse, jockey, ...]. We anchor on the first purely-text cell.
    """
    try:
        nums = [c for c in cells if re.fullmatch(r"\d+(\.\d+)?", c.strip())]
        texts = [c for c in cells if not re.fullmatch(r"\d+(\.\d+)?", c.strip())]
        if not texts:
            return None
        runner = {
            "horse": texts[0],
            "jockey": texts[1] if len(texts) > 1 else None,
            "trainer": texts[2] if len(texts) > 2 else None,
            "barrier": int(nums[0]) if nums else None,
            "weight_kg": float(nums[1]) if len(nums) > 1 else None,
            "odds": float(nums[2]) if len(nums) > 2 else None,
        }
        return runner
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Results parsing
# ---------------------------------------------------------------------------
def parse_results(html: str) -> tuple[list[dict], list[str]]:
    """Extract finish positions: [{race_no, horse, position, margin, time}] + warnings."""
    soup = BeautifulSoup(html, "html.parser")
    warnings: list[str] = []
    out: list[dict] = []

    blocks = soup.select("[class*='result'], [class*='race-card'], article, .card")
    if not blocks:
        blocks = soup.find_all("table")
    for block in blocks:
        text = block.get_text(" ", strip=True)
        m = re.search(r"\brace\s+(\d+)\b", text, re.IGNORECASE)
        if not m:
            continue
        race_no = int(m.group(1))
        for row in block.select("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.select("td")]
            if len(cells) < 2:
                continue
            pos_match = re.match(r"(\d+)", cells[0])
            if not pos_match:
                continue
            out.append(
                {
                    "race_no": race_no,
                    "position": int(pos_match.group(1)),
                    "horse": cells[1],
                    "margin": cells[2] if len(cells) > 2 else None,
                    "time": _parse_time(cells[3]) if len(cells) > 3 else None,
                }
            )
    if not out:
        warnings.append("no result rows recognized on results page")
    return out, warnings


def _parse_time(raw: str | None) -> float | None:
    if not raw:
        return None
    m = re.match(r"(\d+):(\d+(?:\.\d+)?)", raw)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    try:
        return float(raw)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
def _parse_fixture_date(raw: str | None, fallback: datetime) -> datetime:
    if raw:
        for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%d %B %y", "%d %b %y"):
            try:
                return datetime.strptime(raw.strip(), fmt)
            except ValueError:
                continue
    return fallback


def ingest_fixtures(
    db: Session, cards: list[dict], source_url: str, default_date: datetime | None = None
) -> dict:
    """Upsert parsed race cards. Detects >10% odds moves for updated-prediction alerts."""
    stats = {"races_created": 0, "races_updated": 0, "entries": 0, "odds_moves": []}
    fallback = default_date or datetime.utcnow()

    for card in cards:
        race_dt = _parse_fixture_date(card.get("date"), fallback)
        race = db.scalar(
            select(Race).where(
                Race.date == race_dt,
                Race.race_no == card["race_no"],
                Race.venue == "Champ de Mars",
            )
        )
        if race is None:
            race = Race(
                date=race_dt,
                race_no=card["race_no"],
                venue="Champ de Mars",
                status=RACE_SCHEDULED,
                source_url=source_url,
            )
            db.add(race)
            db.flush()
            stats["races_created"] += 1
        else:
            stats["races_updated"] += 1
        race.race_name = card.get("race_name") or race.race_name
        race.distance_m = card.get("distance_m") or race.distance_m
        race.race_class = card.get("race_class") or race.race_class
        race.track_condition = card.get("track_condition") or race.track_condition

        for runner in card.get("entries", []):
            horse = resolve_or_create(db, Horse, runner["horse"])
            if horse is None:
                flag_issue(
                    db, _SOURCE, "missing_field", "entry without horse name",
                    url=source_url, context={"race_no": card["race_no"]},
                )
                continue
            entry = db.scalar(
                select(RaceEntry).where(
                    RaceEntry.race_id == race.id, RaceEntry.horse_id == horse.id
                )
            )
            if entry is None:
                entry = RaceEntry(race_id=race.id, horse_id=horse.id)
                db.add(entry)
                stats["entries"] += 1
            elif runner.get("odds") and entry.odds and entry.odds > 0:
                ratio = runner["odds"] / entry.odds
                if ratio < 0.9 or ratio > 1.1:
                    stats["odds_moves"].append(
                        {"horse": horse.name, "from": entry.odds,
                         "to": runner["odds"], "race_id": race.id}
                    )
            if runner.get("jockey"):
                jockey = resolve_or_create(db, Jockey, runner["jockey"])
                entry.jockey_id = jockey.id if jockey else entry.jockey_id
            if runner.get("trainer"):
                trainer = resolve_or_create(db, Trainer, runner["trainer"])
                entry.trainer_id = trainer.id if trainer else entry.trainer_id
            entry.barrier = runner.get("barrier") or entry.barrier
            entry.weight_kg = runner.get("weight_kg") or entry.weight_kg
            entry.odds = runner.get("odds") or entry.odds

    db.commit()
    return stats


def ingest_results(db: Session, rows: list[dict]) -> dict:
    """Attach finish positions to existing entries; mark races completed."""
    stats: dict = {"results_written": 0, "races_completed": 0}
    completed_ids: set[int] = set()
    for row in rows:
        race = db.scalar(
            select(Race).where(Race.race_no == row["race_no"]).order_by(Race.date.desc()).limit(1)
        )
        if race is None:
            continue
        horse = db.scalar(select(Horse).where(Horse.name.ilike(f"%{row['horse']}%")))
        if horse is None:
            continue
        entry = db.scalar(
            select(RaceEntry).where(RaceEntry.race_id == race.id, RaceEntry.horse_id == horse.id)
        )
        if entry is None:
            continue
        result = db.scalar(select(RaceResult).where(RaceResult.race_entry_id == entry.id))
        if result is None:
            result = RaceResult(race_entry_id=entry.id)
            db.add(result)
        result.finish_position = row["position"]
        result.margin = row.get("margin")
        result.time_s = row.get("time")
        stats["results_written"] += 1
        completed_ids.add(race.id)
    for race_id in completed_ids:
        race = db.get(Race, race_id)
        if race:
            race.status = "completed"
    db.commit()
    stats["races_completed"] = len(completed_ids)
    return stats


def stage_scrape() -> dict:
    """Pipeline stage: fetch + parse + ingest fixtures (and results if found)."""
    db = SessionLocal()
    try:
        html = fetch_html(settings.mtc_fixtures_url, max_age_seconds=1800)
        if html is None:
            return {"ok": False, "reason": "fetch blocked or failed"}
        cards, warnings = parse_fixtures(html, settings.mtc_fixtures_url)
        for w in warnings:
            flag_issue(db, _SOURCE, "parse_warning", w, url=settings.mtc_fixtures_url)
        stats = ingest_fixtures(db, cards, settings.mtc_fixtures_url)

        results_url = settings.mtc_fixtures_url.replace("fixtures", "results")
        results_html = fetch_html(results_url, max_age_seconds=1800)
        result_stats: dict = {"results_written": 0, "races_completed": 0}
        if results_html:
            rows, res_warnings = parse_results(results_html)
            for w in res_warnings:
                flag_issue(db, _SOURCE, "parse_warning", w, url=results_url)
            if rows:
                result_stats = ingest_results(db, rows)

        odds_moves = stats.pop("odds_moves")
        return {"ok": True, **stats, "odds_moves": odds_moves, **result_stats}
    finally:
        db.close()
