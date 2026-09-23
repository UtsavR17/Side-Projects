"""Application configuration, loaded from environment / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- API ---
    app_name: str = "FormEdge API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://formedge:formedge@localhost:5432/formedge"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 300

    # --- Auth ---
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    cors_origins: str = "http://localhost:3000"
    admin_email: str = "admin@example.com"
    admin_password: str = "admin1234"

    # --- Scraping (polite defaults) ---
    scrape_user_agent: str = "FormEdgeBot/0.1 (personal project; contact: you@example.com)"
    scrape_min_interval_seconds: float = 2.0
    raw_html_cache_dir: str = "./raw_cache"
    mtc_fixtures_url: str = "https://www.mtcjockeyclub.com/form-guide/fixtures"

    # --- Weather (Open-Meteo) ---
    weather_enabled: bool = True
    race_venue_lat: float = -20.2927
    race_venue_lon: float = 57.5025

    # --- ML ---
    ml_artifact_dir: str = "./ml_artifacts"
    ml_test_fraction: float = 0.2

    # --- Notifications (optional FCM push) ---
    fcm_enabled: bool = False
    fcm_project_id: str = ""
    fcm_credentials_json: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
