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
- A live PostgreSQL database is a HARD REQUIREMENT (D-P2a, verify fix loop):
  db_available() pings the database via libpq keyword args synchronously, and if
  it is unreachable the session-scoped provisioning fixture FAILS LOUD (pytest
  aborts the whole run) rather than silently skipping DB-backed tests. Silent
  skips are the exact D-P7-4 defect this phase repaired; there is no no-DB run
  mode.

Run modes (SC6 — env-pointable, no hard-coded host):
  The harness reads POSTGRES_HOST / POSTGRES_PORT / POSTGRES_PASSWORD from the
  environment and forces POSTGRES_DB to TEST_POSTGRES_DB (default "biznice_test")
  so the running app DB is never touched. Required secrets: POSTGRES_PASSWORD,
  JWT_SECRET, BNS_ADMIN_PASSWORD. Knobs: TEST_POSTGRES_DB (override the test DB
  name — used to run isolated DBs in parallel).

  1. In-container (local default; POSTGRES_HOST=db comes from the container env):
       podman exec -e PYTHONPATH=/app compose_api_1 \
         sh -c 'cd /app && python -m pytest -q'

  2. Against a localhost Postgres (CI / Phase 3 — compose_db is never host-port-
     mapped, so CI provides its own localhost Postgres service):
       cd backend && POSTGRES_HOST=localhost POSTGRES_PORT=5432 \
         POSTGRES_PASSWORD=<pw> JWT_SECRET=<>=32-char secret> \
         BNS_ADMIN_PASSWORD=<pw> TEST_POSTGRES_DB=biznice_test \
         .venv/bin/python -m pytest -q
"""
from __future__ import annotations

import os
import subprocess
import sys

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
# FORCE (not setdefault) the admin bootstrap creds: the container exports the
# live app's BNS_ADMIN_* values, so a setdefault would leave seed_admin_user
# creating an identity the hard-coded login/refresh tests can't authenticate as
# (they post admin@test.local / testadminpass). Override unconditionally BEFORE
# app.main → config.py instantiates Settings() (D-P2a-5, part 1).
os.environ["BNS_ADMIN_EMAIL"] = "admin@test.local"
os.environ["BNS_ADMIN_PASSWORD"] = "testadminpass"
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
      (a) A live DB is a hard requirement (no silent-skip mode): if db_available()
          is False, abort the whole session loudly with a clear message instead
          of letting a raw connection traceback (or, worse, a silent skip)
          obscure the cause.
      (b) Connect to the maintenance DB ("postgres") and CREATE DATABASE the
          test DB if it does not already exist. autocommit is REQUIRED —
          CREATE DATABASE cannot run inside a transaction block.
      (c) Run `alembic upgrade head` as a subprocess (via sys.executable so it
          uses the SAME interpreter running pytest — a bare "python" is absent
          on standard Debian/Ubuntu/CI hosts where pytest is launched via
          .venv/bin/python) with cwd at the backend root, inheriting the forced
          POSTGRES_DB so alembic/env.py targets the test DB (SC6). check=True so
          a migration failure fails the run loudly instead of leaving an
          unmigrated DB.
    """
    import psycopg2

    from app.core.config import settings

    if not db_available():
        pytest.exit(
            "A live PostgreSQL database is required but none is reachable at "
            f"{settings.postgres_host}:{settings.postgres_port} "
            f"(db={settings.postgres_db}, user={settings.postgres_user}). "
            "The backend test suite has no no-DB run mode — set POSTGRES_HOST/"
            "POSTGRES_PORT/POSTGRES_PASSWORD to a reachable Postgres and rerun.",
            returncode=1,
        )

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
        [sys.executable, "-m", "alembic", "upgrade", "head"],
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
# Per-test isolation: truncate + reseed the baseline before every test (SC3/SC4)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _isolate():
    """
    Give every test a clean, identically-seeded database.

    Before each test, on the NullPool test engine:
      1. TRUNCATE every Base.metadata table (except alembic_version) with
         RESTART IDENTITY CASCADE in a single statement — no cross-test row
         bleed, serial sequences reset, so back-to-back reruns are stable and
         collision-free (SC3).
      2. seed_admin_user() — rebuilds roles/permissions and the real admin
         (BNS_ADMIN_EMAIL) so login-based flows work.
      3. Insert a fixed-id "admin-user" User carrying the admin role, so tokens
         minted with subject="admin-user" (used across the syerp/plum tests)
         resolve to an active admin and pass the wildcard RBAC check
         (SC4 / D-P2a-4).
    """
    from sqlalchemy import select, text

    from app.core.base import Base
    from app.modules.auth.models import Permission, Role, User
    from app.modules.auth.seed import seed_admin_user
    from app.modules.auth.service import hash_password

    truncatable = [
        f'"{table.name}"'
        for table in Base.metadata.sorted_tables
        if table.name != "alembic_version"
    ]

    async with TestSessionLocal() as session:
        await session.execute(
            text(f"TRUNCATE {', '.join(truncatable)} RESTART IDENTITY CASCADE")
        )
        await session.commit()

        # Baseline: roles/permissions + the real admin (commits internally).
        await seed_admin_user(session)

        # Fixed-id admin identity for token subjects used across the tests.
        admin_role = (
            await session.execute(select(Role).where(Role.name == "admin"))
        ).scalars().first()
        admin_user = User(
            id="admin-user",
            email="admin-user@test.local",
            hashed_password=hash_password("admin-user-test-pw"),
            is_active=True,
        )
        admin_user.roles.append(admin_role)
        session.add(admin_user)

        # ------------------------------------------------------------------
        # Fixed RBAC identity roster (D-P2a-5).
        #
        # DB-backed tests mint tokens for a handful of static subjects that are
        # NOT the wildcard admin. The shipped RBAC dependency ignores the JWT
        # `perms` claim and authorizes purely from the subject's DB roles, so
        # each of those subjects must exist as a real, limited User for negative
        # tests to get a genuine 403 (and positive read tests a genuine 200).
        #
        # Each roster identity is bound to a role granting EXACTLY the single
        # permission its name/intent implies and NOTHING more. Permission rows
        # are reused from seed_admin_user; roster roles are created once and
        # shared by identities needing the same grant. The whole block is
        # idempotent under the per-test truncate+reseed (it runs before every
        # test against a freshly-emptied DB).
        #   syerp-reader    → syerp:read  (tests/syerp/test_gl.py)
        #   regular-user-id → syerp:read  (tests/auth/test_user_admin.py — a
        #                     non-admin that has a business perm but lacks
        #                     users:manage, so the admin gates return 403)
        roster: list[tuple[str, str]] = [
            ("syerp-reader", "syerp:read"),
            ("regular-user-id", "syerp:read"),
        ]
        perms_by_code = {
            perm.code: perm
            for perm in (await session.execute(select(Permission))).scalars().all()
        }
        roster_roles: dict[str, Role] = {}
        for subject, code in roster:
            role = roster_roles.get(code)
            if role is None:
                role_name = f"roster-{code.replace(':', '-')}"  # e.g. roster-syerp-read
                role = Role(
                    name=role_name,
                    description=f"Test roster role granting exactly {code}",
                )
                role.permissions.append(perms_by_code[code])
                session.add(role)
                await session.flush()
                roster_roles[code] = role
            roster_user = User(
                id=subject,
                email=f"{subject}@roster.test.local",
                hashed_password=hash_password(f"{subject}-test-pw"),
                is_active=True,
            )
            roster_user.roles.append(role)
            session.add(roster_user)

        await session.commit()

    yield


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> httpx.AsyncClient:
    """
    Async httpx test client backed by the FastAPI ASGI app.

    No real HTTP server is started; requests are dispatched in-process through
    ASGITransport. The app's get_db dependency is overridden onto the NullPool
    test engine (see _wire_test_engine), and a live DB is a hard requirement for
    the whole session, so both liveness and readiness routes exercise the real
    test database.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def skip_if_no_db() -> None:
    """
    Retired no-op — retained only as a legacy fixture alias.

    A live DB is now a HARD REQUIREMENT: the session-scoped autouse
    `_provision_test_database` fixture aborts the whole run (pytest.exit) if no
    database is reachable, so by the time any test body runs the DB is
    guaranteed present. This fixture therefore no longer skips anything — its
    former silent-skip behavior was the D-P7-4 defect this phase repaired.

    It stays as a harmless dependency so the ~28 existing call sites that list
    `skip_if_no_db` in their signatures keep resolving without a mechanical
    parameter-strip sweep; new tests need not depend on it.
    """
    return None
