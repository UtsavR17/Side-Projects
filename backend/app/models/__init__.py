"""ORM model registry — import everything from here: `from app.models import Horse`."""
from app.models.entities import NEGATIVE, POSITIVE, Horse, Jockey, Trainer
from app.models.predictions import (
    ModelArtifactMeta,
    ModelPerformance,
    Prediction,
    PredictionExplanation,
)
from app.models.races import (
    Race,
    RaceEntry,
    RaceResult,
    HorseFormSnapshot,
)
from app.models.users import (
    NOTIFICATION_CATEGORIES,
    DataQualityFlag,
    DeviceToken,
    FollowedHorse,
    Notification,
    NotificationPreference,
    User,
)

# Race status constants live with Race but are re-exported for convenience.
RACE_SCHEDULED = "scheduled"
RACE_COMPLETED = "completed"
RACE_CANCELLED = "cancelled"

__all__ = [
    "Horse",
    "Jockey",
    "Trainer",
    "Race",
    "RaceEntry",
    "RaceResult",
    "HorseFormSnapshot",
    "Prediction",
    "PredictionExplanation",
    "ModelPerformance",
    "ModelArtifactMeta",
    "User",
    "NotificationPreference",
    "FollowedHorse",
    "Notification",
    "DeviceToken",
    "DataQualityFlag",
    "NOTIFICATION_CATEGORIES",
    "POSITIVE",
    "NEGATIVE",
    "RACE_SCHEDULED",
    "RACE_COMPLETED",
    "RACE_CANCELLED",
]
