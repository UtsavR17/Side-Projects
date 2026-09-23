"""Open-Meteo weather enrichment for upcoming races (§2 weather row).

Race-day conditions feed `races.weather`; track condition itself stays as
declared by the clerk of the course.
"""
from __future__ import annotations

import logging
from datetime import datetime

import httpx
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import RACE_SCHEDULED, Race

logger = logging.getLogger(__name__)

API = "https://api.open-meteo.com/v1/forecast"


def fetch_forecast_for_date(day: datetime) -> dict | None:
    params = {
        "latitude": settings.race_venue_lat,
        "longitude": settings.race_venue_lon,
        "daily": "weathercode,precipitation_sum,temperature_2m_max,temperature_2m_min",
        "timezone": "Indian/Mauritius",
        "start_date": day.strftime("%Y-%m-%d"),
        "end_date": day.strftime("%Y-%m-%d"),
    }
    try:
        resp = httpx.get(API, params=params, timeout=15)
        resp.raise_for_status()
        daily = resp.json().get("daily", {})
        if not daily or not daily.get("weathercode"):
            return None
        return {
            "weathercode": daily["weathercode"][0],
            "precipitation_mm": daily.get("precipitation_sum", [None])[0],
            "tmax": daily.get("temperature_2m_max", [None])[0],
            "tmin": daily.get("temperature_2m_min", [None])[0],
        }
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        logger.warning("weather fetch failed for %s: %s", day, exc)
        return None


def describe(code: int, precip_mm: float | None) -> str:
    if precip_mm and precip_mm > 5:
        return "rain"
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return "showers"
    if code in (95, 96, 99):
        return "thunderstorm"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (0, 1):
        return "clear"
    if code in (2, 3):
        return "cloudy"
    return "unknown"


def enrich_upcoming_races() -> dict:
    """Attach forecast weather to scheduled races within the forecast horizon."""
    if not settings.weather_enabled:
        return {"updated": 0, "skipped": "disabled"}
    updated = 0
    db = SessionLocal()
    try:
        races = db.scalars(
            select(Race).where(Race.status == RACE_SCHEDULED).order_by(Race.date)
        ).all()
        by_day: dict[str, dict | None] = {}
        for race in races:
            if race.weather:  # already known
                continue
            day_key = race.date.strftime("%Y-%m-%d")
            if day_key not in by_day:
                by_day[day_key] = fetch_forecast_for_date(race.date)
            forecast = by_day[day_key]
            if forecast is None:
                continue
            race.weather = describe(forecast["weathercode"], forecast["precipitation_mm"])
            updated += 1
        db.commit()
        return {"updated": updated}
    finally:
        db.close()
