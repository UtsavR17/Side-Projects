"""Evaluate stage (§9): score STORED predictions against real results,
sliced by distance bucket and track condition, incrementally per run."""
from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import ModelPerformance, Prediction, RACE_COMPLETED, Race
from app.services.form_stats import distance_bucket
from pipeline.ml.metrics import binary_metrics, top1_correct

logger = logging.getLogger(__name__)


def _period_end(period: str, suffix: str) -> date | None:
    """End date of a prior post-race coverage period, or None."""
    if suffix not in period:
        return None
    try:
        return date.fromisoformat(period.split("..")[1].split()[0])
    except (IndexError, ValueError):
        return None


def _upsert_performance(db: Session, **fields) -> ModelPerformance:
    """Insert or UPDATE the (model_name, period) row.

    Upserting keeps repeated runs (hourly schedule, late result imports) from
    piling up duplicate periods on the leaderboard.
    """
    row = db.scalar(
        select(ModelPerformance).where(
            ModelPerformance.model_name == fields["model_name"],
            ModelPerformance.period == fields["period"],
        )
    )
    if row is None:
        row = ModelPerformance(**fields)
        db.add(row)
        return row
    for key, value in fields.items():
        setattr(row, key, value)
    row.computed_at = datetime.utcnow()
    return row


def _slices(y_true, y_prob, idx_map: dict[str, list[int]]) -> dict:
    out = {}
    for name, idxs in sorted(idx_map.items()):
        if not idxs:
            continue
        m = binary_metrics([y_true[i] for i in idxs], [y_prob[i] for i in idxs])
        out[name] = {"n": m.get("n_samples", 0), "roc_auc": m.get("roc_auc"),
                     "log_loss": m.get("log_loss")}
    return out


def stage_evaluate(db: Session | None = None, full: bool = False) -> dict:
    """Score stored predictions against results.

    Incremental by default: only races on/after the last covered date are
    re-scored (so a late-imported result for the boundary meeting is picked up
    and existing rows are updated in place). Pass ``full=True`` to re-score
    every completed race that has predictions.
    """
    own = db is None
    if own:
        db = SessionLocal()
    try:
        completed = db.scalars(
            select(Race).where(Race.status == RACE_COMPLETED).order_by(Race.date.asc())
        ).all()
        completed = [r for r in completed if any(e.result for e in r.entries)]
        if not completed:
            return {"skipped": "no completed races"}

        completed_ids = [r.id for r in completed]
        preds = db.scalars(
            select(Prediction).where(Prediction.race_id.in_(completed_ids))
        ).all()
        if not preds:
            return {"skipped": "no stored predictions to evaluate"}
        model_names = sorted({p.model_name for p in preds})
        preds_by_model_race = {
            m: {(p.race_id, p.horse_id): p for p in preds if p.model_name == m}
            for m in model_names
        }

        covered: dict[str, date] = {}
        for perf in db.scalars(
            select(ModelPerformance).order_by(ModelPerformance.computed_at.desc())
        ).all():
            end = _period_end(perf.period, "post-race")
            if end and perf.model_name not in covered:
                covered[perf.model_name] = end

        summary: dict[str, dict] = {}
        for model_name in model_names:
            per_race_map = preds_by_model_race[model_name]
            until = None if full else covered.get(model_name)
            eligible = [
                r for r in completed
                if any((r.id, e.horse_id) in per_race_map for e in r.entries)
                and (until is None or r.date.date() >= until)
            ]
            if not eligible:
                continue

            y_true: list[int] = []
            y_prob: list[float] = []
            slice_dist: dict[str, list[int]] = {}
            slice_cond: dict[str, list[int]] = {}
            per_race_top1 = []

            for race in eligible:
                idx_base = len(y_true)
                field = [e for e in race.entries if e.result is not None]
                winner_horse = next(
                    (e.horse_id for e in field if e.result.finish_position == 1), None
                )
                for entry in field:
                    pred = per_race_map.get((race.id, entry.horse_id))
                    if pred is None:
                        continue
                    y_true.append(1 if entry.result.finish_position == 1 else 0)
                    y_prob.append(pred.win_prob)

                race_slice = list(range(idx_base, len(y_true)))
                slice_dist.setdefault(distance_bucket(race.distance_m) or "unknown",
                                      []).extend(race_slice)
                slice_cond.setdefault((race.track_condition or "unknown").lower(),
                                      []).extend(race_slice)

                probs = [per_race_map[(race.id, e.horse_id)].win_prob
                         for e in field if (race.id, e.horse_id) in per_race_map]
                horses_in_order = [e.horse_id for e in field
                                   if (race.id, e.horse_id) in per_race_map]
                winner_pos = (horses_in_order.index(winner_horse)
                              if winner_horse in horses_in_order else None)
                per_race_top1.append({"probs": probs, "winner_idx": winner_pos})

            m = binary_metrics(y_true, y_prob)
            top1 = top1_correct(per_race_top1)
            if top1 is not None:
                m["accuracy"] = top1

            period = (f"{eligible[0].date.date().isoformat()}.."
                      f"{eligible[-1].date.date().isoformat()} post-race")
            _upsert_performance(
                db,
                model_name=model_name, period=period, n_samples=m.get("n_samples", 0),
                accuracy=m.get("accuracy"), precision=m.get("precision"),
                recall=m.get("recall"), f1=m.get("f1"), roc_auc=m.get("roc_auc"),
                log_loss=m.get("log_loss"),
                by_distance_bucket=_slices(y_true, y_prob, slice_dist),
                by_track_condition=_slices(y_true, y_prob, slice_cond),
            )
            summary[model_name] = {"races": len(eligible), "top1": top1,
                                   "roc_auc": m.get("roc_auc")}

        db.commit()
        logger.info("evaluate: %s", summary)
        return {"models": summary,
                "evaluated_races": max((v["races"] for v in summary.values()), default=0)}
    finally:
        if own:
            db.close()
