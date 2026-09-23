"""Model leaderboard payload (latest performance per model + recent history)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelPerformance


def leaderboard_dict(db: Session) -> dict:
    rows = db.scalars(
        select(ModelPerformance).order_by(ModelPerformance.computed_at.desc())
    ).all()
    by_model: dict[str, list] = {}
    for r in rows:
        by_model.setdefault(r.model_name, []).append(
            {
                "period": r.period,
                "n_samples": r.n_samples,
                "accuracy": r.accuracy,
                "precision": r.precision,
                "recall": r.recall,
                "f1": r.f1,
                "roc_auc": r.roc_auc,
                "log_loss": r.log_loss,
                "by_distance_bucket": r.by_distance_bucket,
                "by_track_condition": r.by_track_condition,
                "computed_at": r.computed_at.isoformat() if r.computed_at else None,
            }
        )
    return {
        "models": [
            {
                "model_name": name,
                "latest": history[0] if history else None,
                "history": history[:10],
            }
            for name, history in sorted(by_model.items())
        ]
    }
