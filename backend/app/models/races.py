from __future__ import annotations

from datetime import date, datetime

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


class Race(Base):
    __tablename__ = "races"
    __table_args__ = (UniqueConstraint("date", "venue", "race_no", name="uq_race_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    venue: Mapped[str] = mapped_column(String(120), nullable=False, default="Champ de Mars")
    race_no: Mapped[int] = mapped_column(Integer, nullable=False)
    race_name: Mapped[str | None] = mapped_column(String(200))
    distance_m: Mapped[int | None] = mapped_column(Integer)
    race_class: Mapped[str | None] = mapped_column(String(50))
    track_condition: Mapped[str | None] = mapped_column(String(50))
    weather: Mapped[str | None] = mapped_column(String(120))
    going: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)
    source_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    entries: Mapped[list["RaceEntry"]] = relationship(back_populates="race")


class RaceEntry(Base):
    __tablename__ = "race_entries"
    __table_args__ = (UniqueConstraint("race_id", "horse_id", name="uq_entry"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), index=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"), index=True)
    jockey_id: Mapped[int | None] = mapped_column(ForeignKey("jockeys.id"))
    trainer_id: Mapped[int | None] = mapped_column(ForeignKey("trainers.id"))
    barrier: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    odds: Mapped[float | None] = mapped_column(Float)
    scratched: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    race: Mapped["Race"] = relationship(back_populates="entries")
    horse: Mapped["Horse"] = relationship(back_populates="entries")
    jockey: Mapped["Jockey | None"] = relationship()
    trainer: Mapped["Trainer | None"] = relationship()
    result: Mapped["RaceResult | None"] = relationship(back_populates="entry", uselist=False)


class RaceResult(Base):
    __tablename__ = "race_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_entry_id: Mapped[int] = mapped_column(
        ForeignKey("race_entries.id"), unique=True, index=True
    )
    finish_position: Mapped[int | None] = mapped_column(Integer)
    margin: Mapped[str | None] = mapped_column(String(50))
    time_s: Mapped[float | None] = mapped_column(Float)
    sp_odds: Mapped[float | None] = mapped_column(Float)
    dn_category: Mapped[str | None] = mapped_column(String(20))
    stewards_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    entry: Mapped["RaceEntry"] = relationship(back_populates="result")


class HorseFormSnapshot(Base):
    """Precomputed form — never calculated on request (master plan §5/§6.3)."""

    __tablename__ = "horse_form_snapshots"
    __table_args__ = (UniqueConstraint("horse_id", "as_of_date", name="uq_snapshot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"), index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    runs: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    places: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    place_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_finish: Mapped[float | None] = mapped_column(Float)
    days_since_last_race: Mapped[int | None] = mapped_column(Integer)
    form_score: Mapped[float] = mapped_column(Float, default=0.0)
    by_distance: Mapped[dict | None] = mapped_column(JSON)
    by_track_condition: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
