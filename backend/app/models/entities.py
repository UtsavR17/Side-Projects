"""Core SQLAlchemy models — mirrors master-plan §5 plus notification preferences
and data-quality flags (needed for §11 admin view and §10 notifications).

Portable types only (JSON rather than JSONB, integer PKs) so the same schema
runs on Postgres in production and SQLite in tests/demo runs.
"""
from __future__ import annotations

from datetime import date, datetime  # noqa: F401

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
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

# ---------------------------------------------------------------------------
# String constants
# ---------------------------------------------------------------------------
RACE_SCHEDULED = "scheduled"
RACE_COMPLETED = "completed"
RACE_CANCELLED = "cancelled"

POSITIVE = "positive"
NEGATIVE = "negative"


class Horse(Base):
    __tablename__ = "horses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_norm: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    sex: Mapped[str | None] = mapped_column(String(1))
    sire: Mapped[str | None] = mapped_column(String(200))
    dam: Mapped[str | None] = mapped_column(String(200))
    foaling_year: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("horses.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    entries: Mapped[list["RaceEntry"]] = relationship(back_populates="horse")


class Jockey(Base):
    __tablename__ = "jockeys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_norm: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    license_no: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Trainer(Base):
    __tablename__ = "trainers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_norm: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    license_no: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
