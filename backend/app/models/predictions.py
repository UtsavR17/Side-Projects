from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

POSITIVE = "positive"
NEGATIVE = "negative"


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("race_id", "horse_id", "model_name", name="uq_prediction"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"), index=True)
    model_name: Mapped[str] = mapped_column(String(50), index=True)
    win_prob: Mapped[float] = mapped_column(Float)
    place_prob: Mapped[float] = mapped_column(Float)
    predicted_rank: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    explanations: Mapped[list["PredictionExplanation"]] = relationship(
        back_populates="prediction", cascade="all, delete-orphan"
    )


class PredictionExplanation(Base):
    __tablename__ = "prediction_explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id", ondelete="CASCADE"), index=True
    )
    factor: Mapped[str] = mapped_column(String(120))
    direction: Mapped[str] = mapped_column(String(10))
    weight: Mapped[float] = mapped_column(Float)
    detail: Mapped[str | None] = mapped_column(String(300))

    prediction: Mapped["Prediction"] = relationship(back_populates="explanations")


class ModelPerformance(Base):
    __tablename__ = "model_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(50), index=True)
    period: Mapped[str] = mapped_column(String(60))
    n_samples: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float | None] = mapped_column(Float)  # top-1 pick accuracy
    precision: Mapped[float | None] = mapped_column(Float)
    recall: Mapped[float | None] = mapped_column(Float)
    f1: Mapped[float | None] = mapped_column(Float)
    roc_auc: Mapped[float | None] = mapped_column(Float)
    log_loss: Mapped[float | None] = mapped_column(Float)
    by_distance_bucket: Mapped[dict | None] = mapped_column(JSON)
    by_track_condition: Mapped[dict | None] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ModelArtifactMeta(Base):
    """Where the trained .joblib for each model lives + when it was trained."""

    __tablename__ = "model_artifact_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(50), unique=True)
    path: Mapped[str] = mapped_column(String(500))
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    n_trained_samples: Mapped[int] = mapped_column(Integer, default=0)
    feature_names: Mapped[list | None] = mapped_column(JSON)
