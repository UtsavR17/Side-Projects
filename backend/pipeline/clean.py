"""Cleaning & entity-resolution stage (Prompt B.2).

Racing data is messy: "Belle Isle", "belle isle", "Belleisle" and
"Belle Isle (NZ)" are usually the same horse. Normalization collapses the
easy cases; fuzzy candidate detection is exposed for the admin merge view.
"""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataQualityFlag

_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")
_HORSE_SUFFIX = re.compile(r"\s+\([a-z]{2,3}\)$")  # trailing (NZ), (Aus), (SAF)


def normalize_name(name: str) -> str:
    """Canonical key for entity resolution (horses, jockeys, trainers)."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().strip()
    s = _HORSE_SUFFIX.sub("", s)
    s = s.replace("&", " and ")
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    if s.startswith("the "):
        s = s[4:]
    return s


def resolve_or_create(db: Session, model, name: str, **extra):
    """Find an existing record by normalized name or create it."""
    norm = normalize_name(name)
    if not norm:
        return None
    existing = db.scalar(select(model).where(model.name_norm == norm))
    if existing is not None:
        return existing
    obj = model(name=name.strip(), name_norm=norm, **extra)
    db.add(obj)
    db.flush()
    return obj


def flag_issue(
    db: Session,
    source: str,
    kind: str,
    message: str,
    url: str | None = None,
    context: dict | None = None,
) -> DataQualityFlag:
    """Record a data-quality problem for the admin view (§11) instead of crashing."""
    flag = DataQualityFlag(
        source=source, kind=kind, message=message, url=url, context=context
    )
    db.add(flag)
    db.commit()
    return flag
