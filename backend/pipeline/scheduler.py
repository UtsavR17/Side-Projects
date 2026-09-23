"""Background scheduler (Prompt A / B): runs the pipeline on a cadence.

Docker Compose runs this as the `worker` service:  python -m pipeline.scheduler
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from pipeline.run import run_stage

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("scheduler")


def build_scheduler() -> BlockingScheduler:
    sched = BlockingScheduler(timezone="Indian/Mauritius")

    # Full ingest -> features -> predict cycle every 4 hours.
    sched.add_job(
        _run_pipeline_cycle,
        IntervalTrigger(hours=4),
        id="pipeline_cycle",
        max_instances=1,
        coalesce=True,
    )
    # Results + performance scoring every hour (cheap, catches finish times).
    sched.add_job(
        lambda: [run_stage("scrape"), run_stage("evaluate")],
        IntervalTrigger(hours=1),
        id="scrape_evaluate",
        max_instances=1,
        coalesce=True,
    )
    # Cache warm every 15 minutes keeps API reads hot.
    sched.add_job(lambda: run_stage("warm"), IntervalTrigger(minutes=15),
                  id="warm", max_instances=1, coalesce=True)
    # Full retrain nightly at 03:00.
    sched.add_job(lambda: run_stage("train"), CronTrigger(hour=3, minute=0),
                  id="train", max_instances=1, coalesce=True)
    # Weekly performance digest, Mondays 08:00.
    sched.add_job(lambda: run_stage("weekly"), CronTrigger(day_of_week="mon", hour=8),
                  id="weekly", max_instances=1, coalesce=True)
    return sched


def _run_pipeline_cycle() -> None:
    for stage in ("scrape", "weather", "features", "predict", "explain", "warm"):
        try:
            run_stage(stage)
        except Exception:  # noqa: BLE001 — one failed stage must not kill the worker
            logger.exception("stage %s failed", stage)


if __name__ == "__main__":
    logger.info("FormEdge pipeline scheduler starting")
    build_scheduler().start()
