"""FormEdge FastAPI application.

Contract (master plan §4/§6): this process only ever READS from Redis/Postgres.
Scraping, feature engineering, model runs and notifications all happen in the
background `pipeline` package.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cache import cache
from app.config import settings
from app.db import init_db
from app.routers import (
    admin,
    auth,
    events,
    horses,
    notifications,
    people,
    predictions,
    races,
    simulator,
)


def _ensure_admin() -> None:
    """Create the bootstrap admin account from env settings (dev convenience)."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import NotificationPreference, User
    from app.security import hash_password

    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.email == settings.admin_email.lower()))
        if existing is None:
            user = User(
                email=settings.admin_email.lower(),
                password_hash=hash_password(settings.admin_password),
                display_name="Admin",
                is_admin=True,
            )
            db.add(user)
            db.flush()
            db.add(NotificationPreference(user_id=user.id))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    _ensure_admin()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(races.router)
app.include_router(horses.router)
app.include_router(people.router)
app.include_router(predictions.router)
app.include_router(notifications.router)
app.include_router(simulator.router)
app.include_router(admin.router)
app.include_router(events.router)


@app.get("/api/health")
def health():
    from app.db import engine

    db_ok = True
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"status": "ok", "cache": cache.backend, "database": db_ok}
