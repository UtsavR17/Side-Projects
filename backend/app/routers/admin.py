"""Admin / data-quality view (§11): scrape flags, duplicate merging, manual import."""
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DataQualityFlag, Horse, RaceEntry, User
from app.security import get_current_admin
from app.services.cache_keys import invalidate_all_profiles
from pipeline.import_files import import_text
from pipeline.parsing import parse_date

router = APIRouter(prefix="/api/admin", tags=["admin"])


class MergeIn(BaseModel):
    source_id: int  # duplicate to retire
    target_id: int  # canonical record to keep


@router.get("/flags")
def list_flags(
    resolved: bool = False,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(DataQualityFlag)
        .where(DataQualityFlag.resolved.is_(resolved))
        .order_by(DataQualityFlag.created_at.desc())
        .limit(200)
    ).all()
    return {
        "flags": [
            {
                "id": f.id,
                "source": f.source,
                "kind": f.kind,
                "message": f.message,
                "url": f.url,
                "context": f.context,
                "resolved": f.resolved,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in rows
        ]
    }


@router.post("/flags/{flag_id}/resolve")
def resolve_flag(flag_id: int, _: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    flag = db.get(DataQualityFlag, flag_id)
    if flag is None:
        raise HTTPException(404, "Flag not found")
    flag.resolved = True
    db.commit()
    return {"id": flag.id, "resolved": True}


@router.post("/horses/merge")
def merge_horses(body: MergeIn, _: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Merge a duplicate horse record into the canonical one (§11)."""
    if body.source_id == body.target_id:
        raise HTTPException(400, "source and target must differ")
    source = db.get(Horse, body.source_id)
    target = db.get(Horse, body.target_id)
    if source is None or target is None:
        raise HTTPException(404, "Horse not found")
    if target.merged_into_id is not None:
        raise HTTPException(400, "Target is itself merged into another record")

    # Move race entries across (skip ones that would collide on race+horse).
    entries = db.scalars(select(RaceEntry).where(RaceEntry.horse_id == source.id)).all()
    existing_pairs = {
        (e.race_id)
        for e in db.scalars(select(RaceEntry).where(RaceEntry.horse_id == target.id)).all()
    }
    moved = 0
    for entry in entries:
        if entry.race_id in existing_pairs:
            continue
        entry.horse_id = target.id
        existing_pairs.add(entry.race_id)
        moved += 1

    source.merged_into_id = target.id
    db.commit()
    invalidate_all_profiles()
    return {
        "merged": True,
        "source_id": source.id,
        "target_id": target.id,
        "entries_moved": moved,
    }


@router.post("/import")
async def import_document(
    request: Request,
    kind: str = Query("auto", pattern="^(auto|fixtures-csv|results-csv|fixtures-html|results-html)$"),
    default_date: str | None = Query(None, description="fallback date, YYYY-MM-DD"),
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Import a human-supplied race card / results document.

    Needed because the primary source (mtcjockeyclub.com) is behind Cloudflare
    bot protection, so a person supplies what they legitimately viewed/saved.

    Two ways to call it::

        # raw body — send the saved page or CSV exactly as-is
        curl -X POST "$API/api/admin/import?kind=fixtures-csv" \
             -H "Authorization: Bearer $TOKEN" -H "Content-Type: text/csv" \
             --data-binary @racecard.csv

        # JSON envelope
        {"content": "...", "kind": "auto", "filename": "card.html",
         "default_date": "2026-05-12"}
    """
    raw = (await request.body()).decode("utf-8", errors="replace")
    if not raw.strip():
        raise HTTPException(400, "Empty request body")

    label = request.headers.get("X-Filename", "")
    payload = raw
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON body")
        payload = data.get("content") or ""
        kind = data.get("kind") or kind
        label = data.get("filename") or label
        default_date = data.get("default_date") or default_date
        if not payload.strip():
            raise HTTPException(400, "JSON body must include a non-empty 'content' field")

    fallback = parse_date(default_date) if default_date else None
    result = import_text(db, payload, kind=kind, default_date=fallback,
                         label=label or "api-import")
    invalidate_all_profiles()
    return {"imported_by": "admin", **result}
