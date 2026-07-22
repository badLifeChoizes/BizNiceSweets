# ABOUTME: Root pytest conftest — env forcing, test DB provisioning, engine/session wiring, per-test isolation.
# ABOUTME: All DB-backed tests run against a dedicated migrated PostgreSQL test database via a NullPool engine.
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
import subprocess

# ---------------------------------------------------------------------------
# Inject a test password BEFORE any app module is imported.
# This satisfies pydantic-settings' requirement that POSTGRES_PASSWORD is set.
# The value "testpassword" is used only in unit tests; it does not connect to
# a real database.
# ---------------------------------------------------------------------------
os.environ.setdefault("POSTGRES_PASSWORD", "testpassword")
# Auth fields (supply before app.main imports config.py via Settings())
# jwt_secret → pydantic-settings env var JWT_SECRET
# bns_admin_password → pydantic-settings env var BNS_ADMIN_PASSWORD
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-at-least-32-chars-long")
os.environ.setdefault("BNS_ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("BNS_ADMIN_PASSWORD", "testadminpass")
# DEBUG=true so the dev/test-only /_rbac_probe route is reachable in tests
# (it 404s in production when debug is false — CR-02 guard).
os.environ.setdefault("DEBUG", "true")

# ---------------------------------------------------------------------------
# Force the harness onto a DEDICATED test database (SC6).
# The container exports POSTGRES_DB=biznice (the live app DB); tests must never
# touch it. OVERRIDE (not setdefault) POSTGRES_DB before app.main → config.py
# instantiates Settings(), so both the app's async engine and Alembic target
# the test DB. POSTGRES_HOST/POSTGRES_PORT are left to the environment so the
# same harness runs against the in-container `db` host or a CI localhost
# Postgres unchanged.
# ---------------------------------------------------------------------------
os.environ["POSTGRES_DB"] = os.environ.get("TEST_POSTGRES_DB", "biznice_test")

import httpx
import pytest
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.db import get_db
from app.main import app

# ---------------------------------------------------------------------------
# NullPool test engine (SC2) — one async engine for the whole session.
# NullPool opens and closes a fresh connection per checkout, so no pooled
# connection stays bound to a since-closed event loop. That is the fix for the
# "attached to a different loop" InterfaceError raised under pytest-asyncio's
# function-scoped loops. settings.database_url already targets the test DB
# because POSTGRES_DB was forced before Settings() was instantiated (above).
# ---------------------------------------------------------------------------
test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

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
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password.get_secret_value(),
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
# Test database provisioning (session-scoped, sync, autouse)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _provision_test_database() -> None:
    """
    Create the dedicated test database if absent and migrate it to head.

    Runs ONCE per session, synchronously, before any async fixture. Sync +
    session scope deliberately sidesteps the function-scoped event-loop
    conflict an async session-scoped fixture would hit under pytest-asyncio's
    asyncio_mode="auto".

    Steps:
      (a) Connect to the maintenance DB ("postgres") and CREATE DATABASE the
          test DB if it does not already exist. autocommit is REQUIRED —
          CREATE DATABASE cannot run inside a transaction block.
      (b) Run `alembic upgrade head` as a subprocess with cwd at the backend
          root, inheriting the forced POSTGRES_DB so alembic/env.py targets
          the test DB (SC6). check=True so a migration failure fails the run
          loudly instead of leaving an unmigrated DB.
    """
    import psycopg2

    from app.core.config import settings

    conn = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname="postgres",
        user=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        connect_timeout=5,
    )
    conn.autocommit = True  # CREATE DATABASE cannot run in a transaction
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (settings.postgres_db,),
            )
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{settings.postgres_db}"')
    finally:
        conn.close()

    # Backend root (holds alembic.ini) — conftest.py lives at <backend>/tests/.
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run(
        ["python", "-m", "alembic", "upgrade", "head"],
        cwd=backend_root,
        check=True,
    )


# ---------------------------------------------------------------------------
# Resolve the app's session machinery to the NullPool test engine (SC2)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _wire_test_engine(_provision_test_database: None):
    """
    Bind every path that opens a DB session to the NullPool test engine.

    Two distinct binding paths must both resolve to the test engine:
      1. Direct-session fixtures do ``from app.core.db import AsyncSessionLocal``
         (lazily, inside the fixture body) — monkeypatch app.core.db.engine and
         .AsyncSessionLocal so those lookups return the test objects.
      2. Route handlers and get_current_user acquire their session via the
         get_db FastAPI dependency — override it on app.main.app so the client
         fixture's requests run against a test-engine session.

    Session-scoped + autouse so the wiring is in place for the whole run;
    depends on _provision_test_database so the DB exists and is migrated first.
    """
    import app.core.db as core_db

    core_db.engine = test_engine
    core_db.AsyncSessionLocal = TestSessionLocal

    async def _override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def test_sessionmaker() -> async_sessionmaker:
    """Expose the NullPool test sessionmaker to fixtures needing a raw session."""
    return TestSessionLocal


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
