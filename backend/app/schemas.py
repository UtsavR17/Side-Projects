"""Pydantic response/request schemas."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth -------------------------------------------------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: int
    email: EmailStr
    display_name: str | None
    is_admin: bool


class NotificationPrefsIn(BaseModel):
    fixtures: bool = True
    predictions_ready: bool = True
    prediction_updated: bool = True
    result_posted: bool = True
    weekly_summary: bool = True
    followed_horse: bool = True


class NotificationPrefsOut(NotificationPrefsIn):
    user_id: int


# --- races / entries --------------------------------------------------------
class ResultOut(ORMModel):
    finish_position: int | None
    margin: str | None
    time_s: float | None
    dn_category: str | None


class ExplanationOut(ORMModel):
    factor: str
    direction: str
    weight: float
    detail: str | None


class PredictionOut(ORMModel):
    id: int
    model_name: str
    win_prob: float
    place_prob: float
    predicted_rank: int
    confidence: float | None
    generated_at: datetime
    explanations: list[ExplanationOut] = []


class EntryOut(ORMModel):
    id: int
    barrier: int | None
    weight_kg: float | None
    odds: float | None
    scratched: bool
    horse_id: int
    horse_name: str
    jockey_id: int | None
    jockey_name: str | None
    trainer_id: int | None
    trainer_name: str | None
    result: ResultOut | None
    predictions: list[PredictionOut] = []


class RaceSummaryOut(ORMModel):
    id: int
    date: datetime
    venue: str
    race_no: int
    race_name: str | None
    distance_m: int | None
    race_class: str | None
    track_condition: str | None
    weather: str | None
    status: str


class RaceDetailOut(RaceSummaryOut):
    entries: list[EntryOut] = []
