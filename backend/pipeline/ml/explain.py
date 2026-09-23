"""Explain stage (Prompt C.6): top-5 positive/negative factors per prediction,
STORED at prediction time (SHAP when available, importance fallback)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import NEGATIVE, POSITIVE, Prediction, PredictionExplanation, Race
from pipeline.ml.dataset import FEATURE_NAMES, build_training_dataset, builder_after_history
from pipeline.ml.models import EloModel, TreeModel, to_matrix
from pipeline.ml.predict import ensemble_weights, load_artifacts

logger = logging.getLogger(__name__)

FACTOR_LABELS = {
    "form_score": "recent form score", "win_rate": "career win rate",
    "dist_win_rate": "win rate at this distance", "cond_win_rate": "win rate on this going",
    "elo_rating": "Elo rating", "market_prob": "market-implied chance",
    "days_since_last": "days since last run", "weight_kg": "weight carried",
    "barrier": "barrier draw", "field_size": "field size",
    "avg_finish": "average finishing position", "runs": "number of career runs",
    "place_rate": "career place rate", "dist_runs": "runs at this distance",
    "cond_runs": "runs on this going", "jockey_win_rate": "jockey strike rate",
    "trainer_win_rate": "trainer strike rate", "market_prob_odds": "market odds",
    "distance_m": "race distance", "condition_index": "track condition",
    "days_since_last": "days since last race",
}
TOP_K = 5
SCOPE_WINDOW_HOURS = 48

_EXPLAINER_CACHE: dict[int, object] = {}


def _get_explainer(estimator):
    key = id(estimator)
    if key not in _EXPLAINER_CACHE:
        import shap  # noqa: PLC0415

        _EXPLAINER_CACHE[key] = shap.TreeExplainer(estimator)
    return _EXPLAINER_CACHE[key]


def _feature_stats(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    X = to_matrix(rows)
    return X.mean(axis=0), X.std(axis=0)


def _tree_contributions(model, rows, mean, std) -> list[dict]:
    """SHAP when available; importance x deviation fallback otherwise (C.6)."""
    X = to_matrix(rows)
    values = None
    try:
        import shap  # noqa: F401,PLC0415

        explainer = _get_explainer(model.win)
        raw = explainer.shap_values(X)
        if isinstance(raw, list):  # older shap: [class0, class1]
            values = np.asarray(raw[-1])
        else:
            values = np.asarray(raw)
            if values.ndim == 3:  # (n, f, classes)
                values = values[:, :, -1]
    except Exception as exc:  # noqa: BLE001 — shap optional (requirements-ml.txt)
        logger.debug("SHAP unavailable (%s); using importance fallback", exc)
        imp = getattr(model.win, "feature_importances_", None)
        if imp is None and hasattr(model.win, "base_estimator_"):
            imp = model.win.base_estimator_.feature_importances_
        if imp is None:
            imp = np.ones(len(FEATURE_NAMES)) / len(FEATURE_NAMES)
        values = imp * (X - mean)

    out = []
    for row_values in values:
        out.append({FEATURE_NAMES[j]: float(row_values[j]) for j in range(len(FEATURE_NAMES))})
    return out


def _elo_contributions(rows, mean, std) -> list[dict]:
    """Transparent heuristic: z-scored rating/market/form, fixed weights."""
    weights = {"elo_rating": 0.5, "market_prob": 0.3, "form_score": 0.2}
    out = []
    for row in rows:
        contrib = {}
        for feat, w in weights.items():
            idx = FEATURE_NAMES.index(feat)
            z = (float(row.get(feat, 0.0) or 0.0) - mean[idx]) / (std[idx] or 1.0)
            contrib[feat] = w * z
        out.append(contrib)
    return out


def contributions_for(model, rows, mean, std) -> list[dict]:
    if isinstance(model, EloModel):
        return _elo_contributions(rows, mean, std)
    if isinstance(model, TreeModel):
        return _tree_contributions(model, rows, mean, std)
    return [{} for _ in rows]


def _write_explanations(pred: Prediction, contrib: dict, row: dict, mean, std) -> int:
    """Replace this prediction's factors with top-5 positive + top-5 negative."""
    for old in list(pred.explanations):
        db_delete = old
        pred.explanations.remove(db_delete)

    ranked = sorted(contrib.items(), key=lambda kv: -kv[1])
    positives = [(f, v) for f, v in ranked if v > 0][:TOP_K]
    negatives = [(f, v) for f, v in reversed(ranked) if v < 0][:TOP_K]

    for direction, items in ((POSITIVE, positives), (NEGATIVE, negatives)):
        for feat, value in items:
            idx = FEATURE_NAMES.index(feat) if feat in FEATURE_NAMES else None
            val = float(row.get(feat, 0.0) or 0.0)
            avg = float(mean[idx]) if idx is not None else 0.0
            pred.explanations.append(PredictionExplanation(
                factor=FACTOR_LABELS.get(feat, feat.replace("_", " ")),
                direction=direction,
                weight=round(value, 5),
                detail=f"{val:.2f} vs avg {avg:.2f}"[:300],
            ))
    return len(positives) + len(negatives)


def stage_explain(db: Session | None = None) -> dict:
    own = db is None
    if own:
        db = SessionLocal()
    try:
        models = load_artifacts(db)
        if not models:
            return {"skipped": "no artifacts"}

        train_rows, _, _ = build_training_dataset(db)
        if not train_rows:
            return {"skipped": "no historical rows for feature statistics"}
        mean, std = _feature_stats(train_rows)
        weights = ensemble_weights(db, list(models.keys()))
        builder = builder_after_history(db)

        horizon = datetime.utcnow() - timedelta(hours=SCOPE_WINDOW_HOURS)
        preds = db.scalars(
            select(Prediction).where(
                (Prediction.generated_at >= horizon)
                | (Prediction.model_name == "ensemble")
            )
        ).unique().all()
        race_ids = sorted({p.race_id for p in preds})

        explained = 0
        for race_id in race_ids:
            race = db.get(Race, race_id)
            if race is None:
                continue
            entries = race.entries
            rows = builder.race_rows(
                race, entries, {e.id: e.odds for e in entries}
            )
            row_by_horse = {r["horse_id"]: r for r in rows}
            if not row_by_horse:
                continue

            # Per-model contributions for this field, in horse_id row order.
            ordered_horses = [r["horse_id"] for r in rows]
            model_contribs: dict[str, dict[int, dict]] = {}
            for name, model in models.items():
                contribs = contributions_for(model, rows, mean, std)
                model_contribs[name] = dict(zip(ordered_horses, contribs))

            ens_contribs: dict[int, dict] = {}
            wsum = sum(weights.get(n, 0.0) for n in model_contribs)
            for name, by_horse in model_contribs.items():
                w = weights.get(name, 0.0) / (wsum or 1.0)
                for horse_id, contrib in by_horse.items():
                    acc = ens_contribs.setdefault(horse_id, {})
                    for feat, value in contrib.items():
                        acc[feat] = acc.get(feat, 0.0) + w * value
            model_contribs["ensemble"] = ens_contribs

            race_preds = [p for p in preds if p.race_id == race_id]
            for pred in race_preds:
                row = row_by_horse.get(pred.horse_id)
                contrib = model_contribs.get(pred.model_name, {}).get(pred.horse_id)
                if row is None or contrib is None:
                    continue
                _write_explanations(pred, contrib, row, mean, std)
                explained += 1

        db.commit()
        logger.info("explain: %d predictions annotated", explained)
        return {"predictions_explained": explained, "races": len(race_ids)}
    finally:
        if own:
            db.close()
