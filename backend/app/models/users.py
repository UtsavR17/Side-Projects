from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

NOTIFICATION_CATEGORIES = (
    "fixtures",
    "predictions_ready",
    "prediction_updated",
    "result_posted",
    "weekly_summary",
    "followed_horse",
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    preferences: Mapped["NotificationPreference | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    followed_horses: Mapped[list["FollowedHorse"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    fixtures: Mapped[bool] = mapped_column(Boolean, default=True)
    predictions_ready: Mapped[bool] = mapped_column(Boolean, default=True)
    prediction_updated: Mapped[bool] = mapped_column(Boolean, default=True)
    result_posted: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    followed_horse: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="preferences")


class FollowedHorse(Base):
    __tablename__ = "followed_horses"
    __table_args__ = (UniqueConstraint("user_id", "horse_id", name="uq_follow"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    horse_id: Mapped[int] = mapped_column(ForeignKey("horses.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="followed_horses")
    horse: Mapped["Horse"] = relationship()


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSON)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class DeviceToken(Base):
    """Mobile push tokens — populated by the Flutter app at login (Prompt E)."""

    __tablename__ = "device_tokens"
    __table_args__ = (UniqueConstraint("user_id", "token", name="uq_device_token"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(500))
    platform: Mapped[str | None] = mapped_column(String(20))  # ios / android
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DataQualityFlag(Base):
    """Raised by the scrape/clean stages; reviewed in the admin view (§11)."""

    __tablename__ = "data_quality_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))
    context: Mapped[dict | None] = mapped_column(JSON)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
