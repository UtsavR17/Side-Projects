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
    """Create tables if they don't exist, then add any columns added since."""
    from app import models  # noqa: F401  (register mappings)

    Base.metadata.create_all(bind=engine)
    light_migrations()


# Columns introduced after the first release. create_all() never ALTERs an
# existing table, so older databases need these added explicitly.
# (Lightweight stand-in for Alembic — portable across SQLite and Postgres.)
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "horses": {
        "external_id": "VARCHAR(40)",
    },
    "races": {
        "meeting_no": "INTEGER",
        "race_time_label": "VARCHAR(10)",
        "prize": "VARCHAR(60)",
        "win_time_s": "FLOAT",
        "tote_dividends": "JSON",
        "sectional_times": "JSON",
    },
    "race_entries": {
        "saddle_no": "INTEGER",
        "sp_odds": "FLOAT",
        "rating": "INTEGER",
        "gear": "VARCHAR(30)",
        "body_weight_kg": "FLOAT",
        "body_weight_delta": "FLOAT",
    },
    "race_results": {
        "sp_odds": "FLOAT",
        "win_dividend": "FLOAT",
        "place_dividend": "FLOAT",
    },
}


def light_migrations() -> list[str]:
    """Add missing columns in place; returns the list of columns added."""
    from sqlalchemy import inspect, text

    added: list[str] = []
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table, columns in _ADDED_COLUMNS.items():
        if table not in tables:
            continue
        existing = {col["name"] for col in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name in existing:
                continue
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            added.append(f"{table}.{name}")
    return added
