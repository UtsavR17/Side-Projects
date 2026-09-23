import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="formedge_test_")
# Force test-critical settings (env beats .env files in pydantic-settings).
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["REDIS_URL"] = "redis://127.0.0.1:1/0"  # unreachable -> memory cache
os.environ["ML_ARTIFACT_DIR"] = f"{_TMP}/artifacts"
os.environ["RAW_HTML_CACHE_DIR"] = f"{_TMP}/raw"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["WEATHER_ENABLED"] = "false"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "adminpass123"

import pytest  # noqa: E402

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clear_cache():
    """The cache is a process-wide singleton; tests must not see each other's keys."""
    from app.cache import cache

    cache.delete_prefix("")
    yield
    cache.delete_prefix("")


@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus):  # pragma: no cover
    shutil.rmtree(_TMP, ignore_errors=True)
