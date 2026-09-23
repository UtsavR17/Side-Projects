"""Train stage (Prompt C.6 — train as its own stage).

- time-based train/holdout split at race-date level (never random, C.2)
- holdout metrics recorded per model (incl. distance/condition slices) so the
  leaderboard has content from day one
- final artifacts are refit on ALL history for deployment
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

import joblib
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import ModelArtifactMeta, ModelPerformance
from pipeline.ml.dataset import build_training_dataset, builder_up_to
from pipeline.ml.metrics import binary_metrics, top1_correct
from pipeline.ml.models import EloModel, make_all_models

logger = logging.getLogger(__name__)
MIN_RACES = 5


def save_artifact(model, n_samples: int, feature_names: list[str]) -> str:
    os.makedirs(settings.ml_artifact_dir, exist_ok=True)
    path = os.path.abspath(os.path.join(settings.ml_artifact_dir, f"{model.name}.joblib"))
    joblib.dump(model, path)
    return path


def upsert_artifact_meta(db: Session, model, n_samples: int, feature_names: list[str]) -> None:
    path = save_artifact(model, n_samples, feature_names)
    meta = db.scalar(select(ModelArtifactMeta).where(ModelArtifactMeta.model_name == model.name))
    if meta is None:
        meta = ModelArtifactMeta(model_name=model.name, path=path)
        db.add(meta)
    meta.path = path
    meta.trained_at = datetime.utcnow()
    meta.n_trained_samples = n_samples
    meta.feature_names = feature_names


def _slice_metrics(idxs: list[int], probs: list[float], meta: list[dict],
                   key_fn) -> dict:
    """idxs are global row indices; probs is aligned with idxs (by position)."""
    buckets: dict[str, list[int]] = {}
    for pos, i in enumerate(idxs):
        buckets.setdefault(key_fn(meta[i]), []).append(pos)
    out = {}
    for name, positions in sorted(buckets.items()):
        if not name or not positions:
            continue
        y = [1 if meta[idxs[p]]["finish"] == 1 else 0 for p in positions]
        m = binary_metrics(y, [probs[p] for p in positions])
        out[name] = {"n": m.get("n_samples", 0), "roc_auc": m.get("roc_auc"),
                     "log_loss": m.get("log_loss")}
    return out


def _group_top1(idxs: list[int], probs: list[float], meta: list[dict]) -> float | None:
    """idxs are global row indices; probs is aligned with idxs (by position)."""
    by_race: dict[int, list[int]] = {}
    for pos, i in enumerate(idxs):
        by_race.setdefault(meta[i]["race_id"], []).append(pos)
    per_race = []
    for positions in by_race.values():
        winner_pos = next(
            (k for k, p in enumerate(positions) if meta[idxs[p]]["finish"] == 1), None
        )
        per_race.append({"probs": [probs[p] for p in positions],
                         "winner_idx": winner_pos})
    return top1_correct(per_race)


def stage_train(db: Session | None = None) -> dict:
    own = db is None
    if own:
        db = SessionLocal()
    try:
        rows, meta, builder_full = build_training_dataset(db)
        race_ids = {m["race_id"] for m in meta}
        if len(race_ids) < MIN_RACES:
            return {"skipped": f"only {len(race_ids)} completed races (need {MIN_RACES})"}

        dates = sorted({m["date"] for m in meta})
        cut_idx = min(max(int(len(dates) * (1 - settings.ml_test_fraction)), 1), len(dates) - 1)
        cut_date = dates[cut_idx]
        train_idx = [i for i, m in enumerate(meta) if m["date"] < cut_date]
        test_idx = [i for i, m in enumerate(meta) if m["date"] >= cut_date]
        if not train_idx or not test_idx:
            train_idx, test_idx = list(range(len(meta))), list(range(len(meta)))

        y_win = [1 if m["finish"] == 1 else 0 for m in meta]
        y_place = [1 if (m["finish"] is not None and m["finish"] <= 3) else 0 for m in meta]
        builder_cut = builder_up_to(db, cut_date)

        period = f"{cut_date[:10]}..{dates[-1][:10]} holdout"
        trained = []
        for model in make_all_models():
            if isinstance(model, EloModel):
                model.set_ratings(builder_cut.ratings())
                model.fit(rows)
            else:
                model.fit([rows[i] for i in train_idx],
                          [y_win[i] for i in train_idx],
                          [y_place[i] for i in train_idx])

            t_idx = test_idx or list(range(len(meta)))
            probs = [float(p) for p in model.predict_win([rows[i] for i in t_idx])]
            y_test = [y_win[i] for i in t_idx]
            m = binary_metrics(y_test, probs)
            top1 = _group_top1(t_idx, probs, meta)
            if top1 is not None:
                m["accuracy"] = top1
            db.add(ModelPerformance(
                model_name=model.name, period=period, n_samples=m.get("n_samples", 0),
                accuracy=m.get("accuracy"), precision=m.get("precision"),
                recall=m.get("recall"), f1=m.get("f1"), roc_auc=m.get("roc_auc"),
                log_loss=m.get("log_loss"),
                by_distance_bucket=_slice_metrics(
                    t_idx, probs, meta, lambda x: x["distance_bucket"]),
                by_track_condition=_slice_metrics(
                    t_idx, probs, meta, lambda x: x["condition"]),
            ))

            # Refit on ALL history for the deployed artifact.
            if isinstance(model, EloModel):
                model.set_ratings(builder_full.ratings())
                model.fit(rows)
            else:
                model.fit(rows, y_win, y_place)
            upsert_artifact_meta(db, model, len(rows), list(rows[0].keys()))
            trained.append(model.name)

        db.commit()
        logger.info("train: %s | rows=%d holdout_races=%d",
                    trained, len(rows), len({meta[i]["race_id"] for i in test_idx}))
        return {"trained": trained, "rows": len(rows), "races": len(race_ids),
                "holdout_races": len({meta[i]["race_id"] for i in test_idx}),
                "cut_date": cut_date}
    finally:
        if own:
            db.close()
