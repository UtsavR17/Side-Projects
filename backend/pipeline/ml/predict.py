"""Predict stage (Prompt C.4-C.5): batch-score upcoming races, store
win/place probabilities, ranks, confidence, and ensemble weights."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta

import joblib
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    ModelArtifactMeta,
    ModelPerformance,
    Prediction,
    PredictionExplanation,
    RACE_SCHEDULED,
    Race,
    RaceEntry,
)
from app.services.events import publish_event
from pipeline.ml.dataset import builder_after_history, builder_up_to
from pipeline.ml.models import EloModel

logger = logging.getLogger(__name__)


def load_artifacts(db: Session) -> dict:
    models = {}
    for meta in db.scalars(select(ModelArtifactMeta)).all():
        try:
            models[meta.model_name] = joblib.load(meta.path)
        except (OSError, ValueError) as exc:
            logger.warning("could not load artifact %s: %s", meta.path, exc)
    return models


def ensemble_weights(db: Session, available: list[str]) -> dict[str, float]:
    """Softmax weights from each model's most recent real-world track record (C.4)."""
    rows = db.scalars(
        select(ModelPerformance).order_by(ModelPerformance.computed_at.desc())
    ).all()
    scores: dict[str, float] = {}
    for r in rows:
        if r.model_name in available and r.model_name not in scores:
            score = r.roc_auc if r.roc_auc is not None else (
                r.accuracy if r.accuracy is not None else 0.5)
            scores[r.model_name] = score
    for name in available:
        scores.setdefault(name, 0.5)
    if not scores:
        return {}
    # softmax with temperature: a clearly better model dominates gradually
    temps = {k: math.exp(8.0 * (v - 0.5)) for k, v in scores.items()}
    total = sum(temps.values())
    return {k: v / total for k, v in temps.items()}


def _normalize(probs) -> list[float]:
    total = float(sum(probs))
    if total <= 0:
        n = max(len(probs), 1)
        return [1.0 / n] * len(probs)
    return [p / total for p in probs]


def confidence_of(probs: list[float]) -> float:
    """1 - normalized entropy: high when the model is sure, low when confused."""
    n = len(probs)
    if n <= 1:
        return 1.0
    h = -sum(p * math.log(p) for p in probs if p > 0)
    return round(1.0 - h / math.log(n), 4)


def clear_predictions(db: Session, race_id: int) -> None:
    preds = db.scalars(select(Prediction).where(Prediction.race_id == race_id)).all()
    for p in preds:
        db.query(PredictionExplanation).filter(
            PredictionExplanation.prediction_id == p.id
        ).delete(synchronize_session=False)
    for p in preds:
        db.delete(p)
    db.flush()


def _score_store(db, models, weights, builder, race, entries) -> int:
    """Score one race with every model + ensemble and persist the rows."""
    rows = builder.race_rows(race, entries, {e.id: e.odds for e in entries})
    if not rows:
        return 0

    per_model: dict[str, tuple] = {}
    for name, model in models.items():
        win = _normalize([float(p) for p in model.predict_win(rows)])
        place = [min(max(float(p), 0.0), 1.0) for p in model.predict_place(rows)]
        per_model[name] = (win, place)

    ens_win = [0.0] * len(rows)
    ens_place = [0.0] * len(rows)
    for name, (win, place) in per_model.items():
        w = weights.get(name, 0.0)
        ens_win = [a + w * b for a, b in zip(ens_win, win)]
        ens_place = [a + w * b for a, b in zip(ens_place, place)]
    per_model["ensemble"] = (_normalize(ens_win), ens_place)

    clear_predictions(db, race.id)
    written = 0
    for model_name, (win, place) in per_model.items():
        order = sorted(range(len(rows)), key=lambda i: -win[i])
        rank_of = {row_i: rank for rank, row_i in enumerate(order, start=1)}
        conf = confidence_of(win)
        for i, row in enumerate(rows):
            db.add(Prediction(
                race_id=race.id, horse_id=row["horse_id"], model_name=model_name,
                win_prob=round(win[i], 5), place_prob=round(min(place[i], 1.0), 5),
                predicted_rank=rank_of[i], confidence=conf,
            ))
            written += 1
    return written


def stage_predict(db: Session | None = None) -> dict:
    own = db is None
    if own:
        db = SessionLocal()
    try:
        models = load_artifacts(db)
        if not models:
            return {"skipped": "no trained artifacts yet — run the train stage first"}
        weights = ensemble_weights(db, list(models.keys()))

        builder = builder_after_history(db)
        cutoff = datetime.utcnow() - timedelta(hours=12)
        races = db.scalars(
            select(Race).where(Race.status == RACE_SCHEDULED, Race.date >= cutoff)
            .order_by(Race.date.asc())
        ).all()

        total = 0
        predicted_races = []
        for race in races:
            entries = db.scalars(
                select(RaceEntry).where(RaceEntry.race_id == race.id)
            ).all()
            if len([e for e in entries if not e.scratched]) < 2:
                continue
            written = _score_store(db, models, weights, builder, race, entries)
            if written:
                total += written
                predicted_races.append(race.id)

        # Backfill: recent completed races with no predictions yet, replayed
        # leak-free with builder_up_to(race date) so §9 accuracy tracking and
        # the prediction-history views have substance from day one.
        backfill_races = db.scalars(
            select(Race)
            .where(
                Race.status == "completed",
                Race.date >= datetime.utcnow() - timedelta(days=120),
            )
            .order_by(Race.date.asc())
        ).all()
        backfilled = 0
        for race in backfill_races:
            already = db.scalar(
                select(Prediction.id).where(Prediction.race_id == race.id).limit(1)
            )
            if already is not None:
                continue
            entries = db.scalars(
                select(RaceEntry).where(RaceEntry.race_id == race.id)
            ).all()
            if len([e for e in entries if not e.scratched]) < 2:
                continue
            hist_builder = builder_up_to(db, race.date.isoformat())
            written = _score_store(db, models, weights, hist_builder, race, entries)
            if written:
                total += written
                backfilled += 1
        db.commit()

        if predicted_races:
            publish_event({"type": "predictions_updated", "races": len(predicted_races)})
        logger.info("predict: %d upcoming, %d backfilled, %d rows",
                    len(predicted_races), backfilled, total)
        return {"races": len(predicted_races), "backfilled": backfilled,
                "predictions": total,
                "models": sorted(list(models.keys()) + ["ensemble"]),
                "race_ids": predicted_races}
    finally:
        if own:
            db.close()
