"""
pytest conftest for BizNiceSweets backend tests.

Key design decisions:
- POSTGRES_PASSWORD is injected as an env var BEFORE any app modules are
  imported. pydantic-settings reads env vars at Settings() instantiation
  (module-level in config.py), so the var must be present in os.environ
  before the first `import app.*`.
- The async test client uses httpx.ASGITransport pointing at the FastAPI
  app — no real HTTP server is started.
- db_available() pings the database URL synchronously; if unreachable, tests
  that require a live DB are skipped with a clear message rather than failing.
"""
from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Inject a test password BEFORE any app module is imported.
# This satisfies pydantic-settings' requirement that POSTGRES_PASSWORD is set.
# The value "testpassword" is used only in unit tests; it does not connect to
# a real database.
# ---------------------------------------------------------------------------
os.environ.setdefault("POSTGRES_PASSWORD", "testpassword")

import pytest
import httpx

from app.main import app


# ---------------------------------------------------------------------------
# DB availability probe
# ---------------------------------------------------------------------------

def _check_db_available() -> bool:
    """
    Return True if a synchronous psycopg2 connection to the configured
    database succeeds, False otherwise.

    Uses the sync URL (psycopg2) to avoid asyncio complexity in a probe
    that intentionally runs at fixture setup time.
    """
    try:
        import psycopg2  # type: ignore[import]
        from app.core.config import settings

        conn = psycopg2.connect(
            settings.database_url_sync,
            connect_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False


# Computed once per test session
_DB_AVAILABLE: bool | None = None


def db_available() -> bool:
    global _DB_AVAILABLE
    if _DB_AVAILABLE is None:
        _DB_AVAILABLE = _check_db_available()
    return _DB_AVAILABLE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> httpx.AsyncClient:
    """
    Async httpx test client backed by the FastAPI ASGI app.

    No real HTTP server is started. Works without a live database.
    Liveness tests use this fixture. Readiness tests skip when no DB.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def skip_if_no_db() -> None:
    """
    Skip the test that uses this fixture when no DB is reachable.

    Usage:
        def test_something(skip_if_no_db):
            ...  # only runs when DB is available
    """
    if not db_available():
        pytest.skip("No live database available — skipping DB-dependent test")
