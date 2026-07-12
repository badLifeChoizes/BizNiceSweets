# ABOUTME: Router-level live-HTTP verification for the four SYERP financial-report endpoints
# ABOUTME: (Phase 9c, SYERP-13 SC6/AC8/AC9). Drives the RUNNING api over HTTP (stdlib urllib —
# ABOUTME: httpx is not in the image) to prove the syerp:read RBAC gate returns 200/401/403 on
# ABOUTME: every report GET, and that profit-loss requires both date bounds (422); exits non-zero on FAIL.
"""
Router-level live-HTTP verification for the SYERP financial-report endpoints (Phase 9c).

WHY THIS EXISTS (the router proof — the companion to verify_reports.py):
  verify_reports.py drives the report SERVICE functions directly (ap_aging_report,
  trial_balance, profit_loss, balance_sheet) and so proves the numbers, but it can
  never exercise the thing that lives only in the ROUTER: the RBAC gate enforced by
  require_permission("syerp:read"). This script closes that gap by making REAL HTTP
  calls against the running api and asserting, for EACH of the four endpoints:
    - GET /ap/aging
    - GET /reports/trial-balance
    - GET /reports/profit-loss?from=<date>&to=<date>
    - GET /reports/balance-sheet
  that a token WITH syerp:read is accepted (200), an unauthenticated request is
  refused (401), and a token WITHOUT syerp:read (a no-permission user) is refused
  (403). It additionally asserts that GET /reports/profit-loss with a MISSING bound
  (omit `to`) is rejected 422 — both `from` and `to` are required.

  These four endpoints are strictly READ-ONLY: they emit NO mutation-audit rows (the
  router writes no write_audit row for a report). SC6 is therefore proven by the RBAC
  status codes ALONE — there are no audit-log assertions here, unlike verify_ap_api.py,
  which checks bill.created / bill.posted / payment.recorded audit rows for its
  mutations. A report reads the ledger; it changes nothing, so there is nothing to audit.

  require_permission reads the user's ROLES from the DB (not the JWT perms claim), so
  the authorized case mints a token for a throwaway user carrying a throwaway role that
  holds ONLY the seeded syerp:read permission (200 on every report), and the 403 case
  mints a token for a second throwaway user with NO roles at all (no permission → 403).
  Tokens are minted with create_access_token — no password round-trip needed.

HOW TO RUN (needs the api SERVING, unlike verify_reports.py which owns its own engine):
  # From inside the running dev api container (api binds 0.0.0.0:8000):
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_reports_api.py
  # Or as a one-off container on the compose network, pointing at the api service:
  podman run --rm --network compose_default --env-file .env \
      -e POSTGRES_HOST=db -e PYTHONPATH=/app -e BNS_API_BASE_URL=http://api:8000 \
      -v ./backend:/app -w /app localhost/compose_api:latest \
      python scripts/verify_reports_api.py

The script creates two throwaway users (one syerp:read-only role + user, one no-role
user) and CLEANS UP after itself in a finally block (deletes both users and the
throwaway role), so it is safe to re-run against the same database. The reports read
the existing ledger; the script posts NO ledger rows of its own.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_reports_api.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Populate Base.metadata (FKs across modules) before any query.
import app.core.models  # noqa: F401
from app.core.config import settings
from app.modules.auth.models import Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password

_FAILURES = 0

BASE_URL = os.environ.get("BNS_API_BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v1/syerp"

# The four report endpoints under test. profit-loss requires both `from` and `to`
# bounds (year 2001 window, safely clear of any real data).
PL_WINDOW = "from=2001-01-01&to=2001-12-31"
REPORT_PATHS = (
    "/ap/aging",
    "/reports/trial-balance",
    f"/reports/profit-loss?{PL_WINDOW}",
    "/reports/balance-sheet",
)


def check(label: str, condition: bool, detail: str = "") -> None:
    """Print PASS/FAIL for one assertion and record failures for the exit code."""
    global _FAILURES
    if condition:
        print(f"PASS: {label}")
    else:
        _FAILURES += 1
        suffix = f" — {detail}" if detail else ""
        print(f"FAIL: {label}{suffix}")


def build_dsn() -> str:
    """Assemble the asyncpg DSN directly from POSTGRES_* env (self-contained)."""
    host = os.environ.get("POSTGRES_HOST", "db")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DB", "biznice")
    user = os.environ.get("POSTGRES_USER", "app")
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        print("FAIL: POSTGRES_PASSWORD is not set in the environment.")
        sys.exit(2)
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


def http(method: str, path: str, token: str | None = None, payload: dict | None = None):
    """
    Make one blocking HTTP request against the running api and return (status, body).

    Uses stdlib urllib (httpx is not installed in the runtime image). `path` is
    relative to the /api/v1/syerp base. HTTP error statuses are captured and
    returned rather than raised, so the caller can assert on 401/403/422.
    """
    url = f"{API}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode()
            return resp.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


async def run() -> None:
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid.uuid4().hex[:8]

    reader_id: str | None = None
    reader_role_id: int | None = None
    noperm_id: str | None = None

    try:
        # -------------------------------------------------------------------
        # Setup: mint a read-only role + user holding ONLY the seeded syerp:read
        # permission (→ 200 on every report), and a second user with NO roles at
        # all (→ 403, the no-permission case).
        # -------------------------------------------------------------------
        async with session_factory() as session:
            read_perm = (
                await session.execute(
                    select(Permission).where(Permission.code == "syerp:read")
                )
            ).scalars().first()
            if read_perm is None:
                print("FAIL: seeded syerp:read permission not found.")
                sys.exit(2)

            reader_role = Role(
                name=f"verify-reports-readonly-{unique}",
                description="VERIFY throwaway role: syerp:read only",
            )
            session.add(reader_role)
            await session.flush()
            (await reader_role.awaitable_attrs.permissions).append(read_perm)

            reader = User(
                email=f"verify-reports-reader-{unique}@example.test",
                hashed_password=hash_password("verify-reports-reader-pw"),
                full_name="VERIFY syerp:read-only user",
                is_active=True,
            )
            session.add(reader)
            await session.flush()
            (await reader.awaitable_attrs.roles).append(reader_role)

            noperm = User(
                email=f"verify-reports-noperm-{unique}@example.test",
                hashed_password=hash_password("verify-reports-noperm-pw"),
                full_name="VERIFY no-permission user",
                is_active=True,
            )
            session.add(noperm)
            await session.flush()

            await session.commit()
            reader_id = reader.id
            reader_role_id = reader_role.id
            noperm_id = noperm.id

        reader_token = create_access_token(reader_id, [])
        noperm_token = create_access_token(noperm_id, [])

        # -------------------------------------------------------------------
        # For EACH of the four report endpoints: 200 with a syerp:read token,
        # 401 unauthenticated, 403 with a token that lacks syerp:read (SC6/AC8/AC9).
        # These are READ-ONLY reports — no mutation-audit rows are written, so the
        # RBAC status codes alone prove SC6 (no audit-log assertions needed).
        # -------------------------------------------------------------------
        for path in REPORT_PATHS:
            s, body = http("GET", path, reader_token)
            check(
                f"syerp:read token → 200 on GET {path} (AC8/AC9)",
                s == 200,
                f"status={s} body={body!r}",
            )
            s, _ = http("GET", path, None)
            check(
                f"unauthenticated → 401 on GET {path} (AC9)",
                s == 401,
                f"status={s}",
            )
            s, _ = http("GET", path, noperm_token)
            check(
                f"no-permission token → 403 on GET {path} (SC6/AC9)",
                s == 403,
                f"status={s}",
            )

        # -------------------------------------------------------------------
        # GET /reports/profit-loss with a MISSING bound (omit `to`) → 422: both
        # `from` and `to` are required query params.
        # -------------------------------------------------------------------
        s, _ = http("GET", "/reports/profit-loss?from=2001-01-01", reader_token)
        check(
            "profit-loss with a MISSING `to` bound → 422 (both bounds required)",
            s == 422,
            f"status={s}",
        )

    finally:
        # Clean up the throwaway rows: both users, then the read-only role. The
        # seeded permission is reused and left in place (real deploy state).
        async with session_factory() as session:
            for user_id in (reader_id, noperm_id):
                if user_id is not None:
                    await session.execute(delete(User).where(User.id == user_id))
            if reader_role_id is not None:
                await session.execute(delete(Role).where(Role.id == reader_role_id))
            await session.commit()
        await engine.dispose()


def main() -> int:
    asyncio.run(run())
    if _FAILURES:
        print(f"\n{_FAILURES} assertion(s) FAILED.")
        return 1
    print("\nAll assertions PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
