"""SQLAlchemy engine / session management.

Works with Postgres in production and SQLite for local tests / demo runs.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    url = settings.database_url
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        engine_ = create_engine(url, **kwargs)
        _attach_sqlite_pragmas(engine_)
        return engine_
    kwargs["pool_pre_ping"] = True
    return create_engine(url, **kwargs)


def _attach_sqlite_pragmas(engine_) -> None:
    """WAL + busy_timeout stop 'database table is locked' during tests/dev,
    and foreign_keys makes FK cascade deletes actually fire."""
    from sqlalchemy import event

    @event.listens_for(engine_, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they don't exist (MVP substitute for migrations)."""
    from app import models  # noqa: F401  (register mappings)

    Base.metadata.create_all(bind=engine)
