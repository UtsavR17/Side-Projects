"""Stage runner / orchestrator:  python -m pipeline.run --stage <name>

Stages (Prompt B.5): scrape, weather, features, train, predict, explain,
evaluate, warm, weekly, all. Notification triggers live here — pipeline-only
(Prompt F.3), never from a user request.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import HorseFormSnapshot, ModelPerformance, Notification, RACE_SCHEDULED, Race
from app.services.notifications import notify_followers_of_horses, notify_users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("pipeline")


def _stage_scrape() -> dict:
    from pipeline.scrape_mtc import stage_scrape

    result = stage_scrape()
    if result.get("ok") and result.get("races_created", 0) > 0:
        created = result["races_created"]
        notify_users(SessionLocal(), "fixtures",
                     f"{created} new race(s) published",
                     "New fixtures are on the board — predictions will follow shortly.",
                     {"races_created": created})
    for move in result.get("odds_moves", [])[:10]:
        notify_users(SessionLocal(), "prediction_updated",
                     f"Odds move: {move['horse']}",
                     f"{move['from']} -> {move['to']} — predictions will be refreshed.",
                     move)
    return result


def _stage_features() -> dict:
    from pipeline.features import stage_features

    return stage_features()


def _stage_weather() -> dict:
    from pipeline.weather import enrich_upcoming_races

    return enrich_upcoming_races()


def _stage_train() -> dict:
    from pipeline.ml.train import stage_train

    return stage_train()


def _stage_predict() -> dict:
    from pipeline.ml.predict import stage_predict

    result = stage_predict()
    race_ids = result.get("race_ids", [])
    if race_ids:
        db = SessionLocal()
        try:
            for race_id in race_ids:
                race = db.get(Race, race_id)
                if race is None:
                    continue
                notify_users(db, "predictions_ready",
                             f"Predictions ready: Race {race.race_no} "
                             f"{race.date.strftime('%d %b')}",
                             "The full field with win/place probabilities and explanations.",
                             {"race_id": race_id})
                horse_ids = {e.horse_id for e in race.entries}
                notify_followers_of_horses(
                    db, horse_ids, "followed_horse",
                    f"Your followed horse runs in Race {race.race_no} "
                    f"({race.date.strftime('%d %b')})",
                    "New predictions are available for this race.",
                    {"race_id": race_id},
                )
        finally:
            db.close()
    return result


def _stage_explain() -> dict:
    from pipeline.ml.explain import stage_explain

    return stage_explain()


def _stage_evaluate() -> dict:
    from pipeline.ml.evaluate import stage_evaluate

    result = stage_evaluate()
    models = result.get("models", {})
    ens = models.get("ensemble")
    if ens and ens.get("races"):
        top1 = ens.get("top1")
        hit_txt = f"top pick hit {int(top1 * ens['races'])}/{ens['races']} times" \
            if top1 is not None else "recorded"
        notify_users(SessionLocal(), "result_posted",
                     "Results in — how we did",
                     f"Ensemble {hit_txt} (ROC-AUC {ens.get('roc_auc')}).",
                     {"ensemble": ens})
    return result


def _stage_warm() -> dict:
    from pipeline.cache_warm import stage_cache_warm

    return stage_cache_warm()


def _stage_weekly() -> dict:
    """Weekly model-performance digest (§10)."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)
        rows = db.scalars(
            select(ModelPerformance).where(ModelPerformance.computed_at >= cutoff)
        ).all()
        latest: dict[str, ModelPerformance] = {}
        for r in rows:
            latest.setdefault(r.model_name, r)
        if not latest:
            return {"skipped": "no recent performance rows"}
        lines = [
            f"{name}: top-1 {m.accuracy:.0%}" if m.accuracy is not None else
            f"{name}: AUC {m.roc_auc}" if m.roc_auc is not None else f"{name}: n/a"
            for name, m in sorted(latest.items())
        ]
        created = notify_users(db, "weekly_summary", "Weekly model report",
                               " | ".join(lines), {"models": list(latest)})
        return {"notified": created, "models": list(latest)}
    finally:
        db.close()


STAGES = {
    "scrape": _stage_scrape,
    "weather": _stage_weather,
    "features": _stage_features,
    "train": _stage_train,
    "predict": _stage_predict,
    "explain": _stage_explain,
    "evaluate": _stage_evaluate,
    "warm": _stage_warm,
    "weekly": _stage_weekly,
}

FULL_ORDER = ["scrape", "weather", "features", "train", "predict", "explain",
              "evaluate", "warm"]


def run_stage(name: str) -> dict:
    fn = STAGES[name]
    result = fn()
    logger.info("stage %s -> %s", name, json.dumps(result, default=str))
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="FormEdge pipeline stage runner")
    parser.add_argument("--stage", default="all", choices=[*STAGES, "all"])
    args = parser.parse_args(argv)

    if args.stage == "all":
        for name in FULL_ORDER:
            run_stage(name)
    else:
        run_stage(args.stage)


if __name__ == "__main__":
    main()
