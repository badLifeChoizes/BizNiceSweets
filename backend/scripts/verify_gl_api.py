# ABOUTME: Router-level live-HTTP verification for the SYERP GL endpoints (Phase 9a, SYERP-12
# ABOUTME: AC8/AC9). Drives the RUNNING api over HTTP (stdlib urllib — httpx is not in the image)
# ABOUTME: to prove the gl.journal_posted / gl.journal_reversed AUDIT rows are written and
# ABOUTME: attributable, and that the syerp:read/write RBAC gate returns 403/401; exits non-zero on FAIL.
"""
Router-level live-HTTP verification for the SYERP GL posting endpoints (Phase 9a).

WHY THIS EXISTS (the router proof — the companion to verify_gl.py):
  verify_gl.py drives the GL SERVICE functions directly and so can never exercise
  the two things that live only in the ROUTER: the audit rows written by
  write_audit (AC8) and the RBAC gate enforced by require_permission (AC9). Those
  were previously provable only by hand (Phase 9a verify gap G2/M4). This script
  closes that gap by making REAL HTTP calls against the running api and asserting:
    - a POST that posts a journal entry writes an attributable gl.journal_posted
      audit_log row targeting the exact entry id;
    - a POST that reverses one writes gl.journal_reversed targeting the reversal;
    - every GL endpoint refuses a token WITHOUT the required syerp permission (403)
      and an unauthenticated request (401).
  require_permission reads the user's ROLES from the DB (not the JWT perms claim),
  so the 403 case uses a throwaway user with NO roles; the authorized case mints a
  token for the seeded admin (whose 'admin' role is a wildcard). Tokens are minted
  with create_access_token — no password round-trip needed.

HOW TO RUN (needs the api SERVING, unlike verify_gl.py which owns its own engine):
  # From inside the running api container (api binds 0.0.0.0:8000):
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_gl_api.py
  # Or as a one-off container on the compose network, pointing at the api service:
  podman run --rm --network compose_default --env-file .env \
      -e POSTGRES_HOST=db -e PYTHONPATH=/app -e BNS_API_BASE_URL=http://api:8000 \
      -v ./backend:/app -w /app localhost/compose_api:latest \
      python scripts/verify_gl_api.py

The script creates throwaway rows (two GL accounts, one no-role user) and the
entries it posts over HTTP, and CLEANS UP after itself in a finally block (deletes
the journal lines/entries, the audit_log rows it created, the throwaway accounts,
and the throwaway user), so it is safe to re-run against the same database.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Populate Base.metadata (FKs across modules) before any query.
import app.core.models  # noqa: F401
from app.core.config import settings
from app.modules.auth.models import AuditLog, User
from app.modules.auth.service import create_access_token, hash_password
from app.modules.syerp.models import GLAccount, JournalEntry, JournalLine

_FAILURES = 0

BASE_URL = os.environ.get("BNS_API_BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v1/syerp"


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
    returned rather than raised, so the caller can assert on 403/401/422.
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

    admin_id: str | None = None
    noperm_id: str | None = None
    acct_a_id: int | None = None
    acct_b_id: int | None = None
    created_entry_ids: list[str] = []
    audit_target_ids: list[str] = []

    try:
        # -------------------------------------------------------------------
        # Setup: resolve the seeded admin, create a NO-ROLE user, and two
        # throwaway GL accounts to post between.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            admin = (
                await session.execute(
                    select(User).where(User.email == settings.bns_admin_email)
                )
            ).scalars().first()
            if admin is None:
                print(f"FAIL: seeded admin {settings.bns_admin_email} not found.")
                sys.exit(2)
            admin_id = admin.id

            noperm = User(
                email=f"verify-noperm-{unique}@example.test",
                hashed_password=hash_password("verify-noperm-pw"),
                full_name="VERIFY no-perm user",
                is_active=True,
            )  # deliberately NO roles → require_permission must 403 on every gate.
            session.add(noperm)

            acct_a = GLAccount(
                code=f"ZC{unique[:6]}", name=f"VERIFY API Debit {unique}", account_type="ASSET"
            )
            acct_b = GLAccount(
                code=f"ZD{unique[:6]}", name=f"VERIFY API Credit {unique}", account_type="LIABILITY"
            )
            session.add_all([acct_a, acct_b])
            await session.commit()
            noperm_id = noperm.id
            acct_a_id, acct_b_id = acct_a.id, acct_b.id

        admin_token = create_access_token(admin_id, [])
        noperm_token = create_access_token(noperm_id, [])

        je_body = {
            "entry_date": date.today().isoformat(),
            "memo": f"VERIFY API balanced {unique}",
            "lines": [
                {"account_id": acct_a_id, "debit": "10"},
                {"account_id": acct_b_id, "credit": "10"},
            ],
        }

        # -------------------------------------------------------------------
        # (a) POST a balanced JE as admin → 201, and a gl.journal_posted audit
        #     row is written, attributable to the admin, targeting the entry.
        # -------------------------------------------------------------------
        status_code, body = http("POST", "/gl/journal-entries", admin_token, je_body)
        entry_id = body.get("id") if isinstance(body, dict) else None
        if entry_id:
            created_entry_ids.append(entry_id)
            audit_target_ids.append(entry_id)
        check(
            "POST /gl/journal-entries as admin returns 201 with an entry id",
            status_code == 201 and entry_id is not None,
            f"status={status_code} body={body!r}",
        )

        async with session_factory() as session:
            posted_audit = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "gl.journal_posted",
                        AuditLog.target_id == entry_id,
                    )
                )
            ).scalars().first()
        check(
            "a gl.journal_posted audit row was written, attributable to the admin, "
            "targeting the posted entry (AC8)",
            posted_audit is not None
            and posted_audit.actor_id == admin_id
            and posted_audit.target_type == "journal_entry",
            f"audit={posted_audit!r}",
        )

        # -------------------------------------------------------------------
        # (b) POST reverse as admin → 201, and a gl.journal_reversed audit row
        #     is written targeting the reversal entry.
        # -------------------------------------------------------------------
        status_code, body = http(
            "POST", f"/gl/journal-entries/{entry_id}/reverse", admin_token, {"memo": None}
        )
        reversal_id = body.get("id") if isinstance(body, dict) else None
        if reversal_id:
            created_entry_ids.append(reversal_id)
            audit_target_ids.append(reversal_id)
        check(
            "POST /gl/journal-entries/{id}/reverse as admin returns 201",
            status_code == 201 and reversal_id is not None,
            f"status={status_code} body={body!r}",
        )
        async with session_factory() as session:
            reversed_audit = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "gl.journal_reversed",
                        AuditLog.target_id == reversal_id,
                    )
                )
            ).scalars().first()
        check(
            "a gl.journal_reversed audit row was written targeting the reversal (AC8)",
            reversed_audit is not None and reversed_audit.actor_id == admin_id,
            f"audit={reversed_audit!r}",
        )

        # -------------------------------------------------------------------
        # (c) RBAC: a token WITHOUT syerp permission is refused 403 on every GL
        #     endpoint (write AND read), and an unauthenticated request is 401.
        # -------------------------------------------------------------------
        s_post, _ = http("POST", "/gl/journal-entries", noperm_token, je_body)
        check("no-permission token → 403 on POST /gl/journal-entries (AC9)", s_post == 403, f"status={s_post}")

        s_list, _ = http("GET", "/gl/journal-entries", noperm_token)
        check("no-permission token → 403 on GET /gl/journal-entries (AC9)", s_list == 403, f"status={s_list}")

        s_rev, _ = http("POST", f"/gl/journal-entries/{entry_id}/reverse", noperm_token, {"memo": None})
        check("no-permission token → 403 on POST .../reverse (AC9)", s_rev == 403, f"status={s_rev}")

        s_reg, _ = http("GET", f"/gl/accounts/{acct_a_id}/register", noperm_token)
        check("no-permission token → 403 on GET /gl/accounts/{id}/register (AC9)", s_reg == 403, f"status={s_reg}")

        s_anon, _ = http("GET", "/gl/journal-entries", None)
        check("unauthenticated request → 401 on GET /gl/journal-entries (AC9)", s_anon == 401, f"status={s_anon}")

    finally:
        # Clean up in FK-safe order: journal lines → entries → audit rows → GL
        # accounts → throwaway user. The seeded admin stays.
        async with session_factory() as session:
            if created_entry_ids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.entry_id.in_(created_entry_ids))
                )
                await session.execute(
                    delete(JournalEntry).where(JournalEntry.id.in_(created_entry_ids))
                )
            if audit_target_ids:
                await session.execute(
                    delete(AuditLog).where(AuditLog.target_id.in_(audit_target_ids))
                )
            acct_ids = [aid for aid in (acct_a_id, acct_b_id) if aid is not None]
            if acct_ids:
                await session.execute(delete(GLAccount).where(GLAccount.id.in_(acct_ids)))
            if noperm_id is not None:
                await session.execute(delete(User).where(User.id == noperm_id))
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
