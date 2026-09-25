"""Shared parsing helpers for messy racing data (dates, times, numbers, columns).

Used by both the scraper and the human-in-the-loop importer so they can never
drift apart.
"""
from __future__ import annotations

from datetime import datetime

DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %B %Y",
    "%d %b %Y",
    "%d %B %y",
    "%d %b %y",
)


def parse_date(raw: str | None, fallback: datetime | None = None) -> datetime:
    """Parse the many date shapes real sources use; fall back to `fallback`/now."""
    if raw:
        text = str(raw).strip()
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        try:  # last resort: ISO with timezone or unusual separators
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return fallback or datetime.utcnow()


def iso_datetime(value: datetime) -> str:
    """Canonical string handed to downstream ingest code (`parse_date` reads it back)."""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def parse_time(raw: str | None) -> float | None:
    """Race time in seconds: '1:23.4' -> 83.4, '83.4' -> 83.4."""
    if raw is None or str(raw).strip() == "":
        return None
    text = str(raw).strip()
    if ":" in text:
        mins, _, secs = text.partition(":")
        try:
            return int(mins) * 60 + float(secs)
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def to_int(raw: str | None) -> int | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(float(str(raw).strip()))
    except ValueError:
        return None


def to_float(raw: str | None) -> float | None:
    if raw is None or str(raw).strip() == "":
        return None
    text = str(raw).strip().replace(",", ".")
    digits = "".join(ch for ch in text if ch.isdigit() or ch in ".-")
    try:
        return float(digits or text)
    except ValueError:
        return None


def row_get(row: dict, *names: str) -> str | None:
    """Case/space/underscore-insensitive column lookup for CSV-ish row dicts."""
    lowered = {str(k).strip().lower().replace(" ", "_"): v for k, v in row.items() if k}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None
