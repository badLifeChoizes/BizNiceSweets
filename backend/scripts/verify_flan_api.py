# ABOUTME: Router-level live-HTTP verification for the FLAN project-management endpoints
# ABOUTME: (v5.0 Phase 1, FLAN-01.7). Drives the RUNNING api over HTTP (stdlib urllib — httpx is
# ABOUTME: not in the image) across ALL TWENTY routes to prove the flan:read/flan:write RBAC gate
# ABOUTME: answers 2xx/401/403 on every one of them, and that all FOURTEEN mutations write an
# ABOUTME: attributable audit_log row while the six GETs write none; exits non-zero on FAIL and
# ABOUTME: self-cleans (FLAN rows + throwaway users/roles; audit rows are append-only, D-14).
"""
Router-level live-HTTP verification for the FLAN endpoints (v5.0 Phase 1).

WHY THIS EXISTS (the router proof — the companion to verify_flan.py):
  verify_flan.py drives the flan SERVICE functions directly and so proves the
  derived phase rollup, the numeric-safe key increment, the date-order rejection
  and the archived-project guard — but it can never exercise the two things that
  live only in the ROUTER: the audit rows written by write_audit and the RBAC
  gate enforced by require_permission("flan:read" / "flan:write"). This script
  closes that gap (the 9a/11a/12a HTTP-verify discipline) by making REAL HTTP
  calls against the running api and asserting, for EACH of the twenty routes:
    - every MUTATION (14 of them) accepts a flan:write token (2xx), refuses a
      token WITHOUT flan:write (403 — a flan:read-only user), refuses a token
      with no permissions at all (403), and refuses an unauthenticated request
      (401);
    - every READ (6 of them) accepts a flan:read token (200), refuses a
      no-permission token (403), and refuses an unauthenticated request (401);
    - each of the FOURTEEN audit actions (project.created/updated/archived,
      phase.created/updated/deleted, task.created/updated/deleted,
      team_member.created/updated/removed, task.assignees_set,
      phase.assignees_set) exists as an audit_log row attributable to the acting
      user (actor_id), carrying the right target_type and a target_id that is a
      STRING of uuid shape — asserted, not assumed. That last clause is the
      GELATO int-PK lesson (136e98d): FLAN's primary keys are uuid strings, and
      "the id type is whatever I remember it being" is exactly how a target_id
      assertion silently stops matching anything;
    - the six GETs write NO audit row at all — counted before and after a full
      read sweep, over rows attributable to this run's users only.

  THREE SILENT-FAILURE HAZARDS THIS SCRIPT DELIBERATELY AVOIDS:
    1. It does NOT enumerate endpoints by walking app.routes. On FastAPI 0.138
       an include is wrapped in _IncludedRouter and app.routes no longer yields
       flattened APIRoutes, so such a walk finds ZERO module routes and the
       sweep passes having measured nothing. The twenty routes are spelled out
       explicitly below and the count is asserted (ROUTE_COUNT == 20, split
       6 read / 14 write).
    2. It does NOT infer RBAC from OpenAPI's `security` block. That block
       records only the bearer SCHEME, never WHICH permission — a route gated on
       the wrong permission passes such a check unnoticed. Only a real HTTP call
       with a real token proves the gate, which is all this script makes.
    3. It runs as a FILE (`python scripts/verify_flan_api.py`), never as a
       `python -` heredoc: without `podman run/exec -i`, stdin is unattached,
       `python -` reads an empty program and exits 0 having run nothing.

  require_permission reads the user's ROLES FROM THE DATABASE (not the JWT perms
  claim), so this mints THREE throwaway users backed by throwaway ROLE rows:
    * writer   — role holding flan:read + flan:write (drives the whole lifecycle
                 over HTTP; every audit row asserted below is attributable to
                 THIS user);
    * reader   — role holding ONLY flan:read (200 on the six reads, 403 on all
                 fourteen mutations);
    * noperm   — no roles at all (403 everywhere).
  Tokens are minted with create_access_token rather than through the OAuth2 form
  login at /api/v1/auth/login, for a reason that matters to the audit assertions:
  a login round-trip would itself write audit rows attributable to these users
  and break the exact "this run wrote precisely N rows" count below.

HOW TO RUN (needs the api SERVING, unlike verify_flan.py which owns its engine):
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_flan_api.py

CLEANUP: a finally block deletes this run's FLAN rows (assignments -> tasks ->
phases -> tags -> roster -> project) and the three throwaway users + roles, so
the script is re-runnable against the same database. It deliberately LEAVES THE
AUDIT ROWS BEHIND: the audit trail is append-only (D-14), so each run leaves ~18
audit_log rows whose actor_id names a user that no longer exists (actor_id is a
plain String(36), not a FK — that dangling reference is the intended shape of an
append-only trail, and the rows are found by target_id, which is unique per run).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_flan_api.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Populate Base.metadata (FKs across modules) before any query.
import app.core.models  # noqa: F401
from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password
from app.modules.flan.models import (
    Phase,
    PhaseAssignee,
    Project,
    ProjectTag,
    Task,
    TaskAssignee,
    TaskTag,
    TeamMember,
)

_FAILURES = 0

BASE_URL = os.environ.get("BNS_API_BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v1"

# The FLAN surface, spelled out rather than discovered (hazard 1 above): six
# flan:read GETs and fourteen flan:write mutations, matching the router's module
# docstring one for one.
ROUTE_COUNT = 20
READ_ROUTE_COUNT = 6
WRITE_ROUTE_COUNT = 14

# The fourteen audit actions the fourteen mutations write (hazard: a partial list
# would let a missing action pass unnoticed, so the count is asserted too).
AUDIT_ACTION_COUNT = 14


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
    relative to the /api/v1 base. HTTP error statuses are captured and returned
    rather than raised, so the caller can assert on 401/403/422.
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


async def _audit_row(session_factory, action: str, target_id: str):
    """Fetch the audit_log row for (action, target_id), or None."""
    async with session_factory() as session:
        return (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == action,
                    AuditLog.target_id == target_id,
                )
            )
        ).scalars().first()


async def _audit_count(session_factory, actor_ids: list[str]) -> int:
    """Count audit_log rows attributable to the given actors (this run only)."""
    async with session_factory() as session:
        return (
            await session.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.actor_id.in_(actor_ids))
            )
        ).scalar_one()


async def run() -> None:  # noqa: C901 - one long linear verification scenario
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid.uuid4().hex[:8]

    # Throwaway-row registries for the finally cleanup.
    project_id: str | None = None
    user_ids: list[str] = []
    role_ids: list[int] = []

    # Every route the writer actually drove, keyed by "METHOD /template" — the
    # sweep below asserts this set equals the twenty declared routes, so a route
    # that was never called cannot be mistaken for one that passed.
    exercised: dict[str, int] = {}
    # One increment per mutation that returned 2xx, i.e. per audit row this run
    # should have written. Compared to the real row count at the end.
    expected_audit_rows = 0

    def writer_call(key: str, method: str, path: str, payload=None, expect: int = 200):
        """Drive one route as the writer, record it as exercised, assert the status."""
        nonlocal expected_audit_rows
        status, body = http(method, path, writer_token, payload)
        exercised[key] = status
        check(
            f"(A) writer (flan:read+flan:write) → {expect} on {key}",
            status == expect,
            f"status={status} body={body!r}",
        )
        if method != "GET" and 200 <= status < 300:
            expected_audit_rows += 1
        return body

    try:
        # -------------------------------------------------------------------
        # Setup: mint the three throwaway users (writer = read+write,
        # reader = read-only, noperm = no roles). require_permission reads the
        # ROLES from the DB, so real Role rows are what make these tokens mean
        # anything — a hand-forged perms claim would prove nothing.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            perms = {
                p.code: p
                for p in (
                    await session.execute(
                        select(Permission).where(
                            Permission.code.in_(["flan:read", "flan:write"])
                        )
                    )
                ).scalars().all()
            }
            if "flan:read" not in perms or "flan:write" not in perms:
                print("FAIL: seeded flan:read/flan:write permissions not found.")
                sys.exit(2)

            writer_role = Role(
                name=f"verify-flan-writer-{unique}",
                description="VERIFY throwaway role: flan:read + flan:write",
            )
            session.add(writer_role)
            await session.flush()
            (await writer_role.awaitable_attrs.permissions).extend(
                [perms["flan:read"], perms["flan:write"]]
            )

            reader_role = Role(
                name=f"verify-flan-reader-{unique}",
                description="VERIFY throwaway role: flan:read only",
            )
            session.add(reader_role)
            await session.flush()
            (await reader_role.awaitable_attrs.permissions).append(perms["flan:read"])

            writer = User(
                email=f"verify-flan-writer-{unique}@example.test",
                hashed_password=hash_password("verify-flan-writer-pw"),
                full_name="VERIFY flan:write user",
                is_active=True,
            )
            session.add(writer)
            await session.flush()
            (await writer.awaitable_attrs.roles).append(writer_role)

            reader = User(
                email=f"verify-flan-reader-{unique}@example.test",
                hashed_password=hash_password("verify-flan-reader-pw"),
                full_name="VERIFY flan:read-only user",
                is_active=True,
            )
            session.add(reader)
            await session.flush()
            (await reader.awaitable_attrs.roles).append(reader_role)

            noperm = User(
                email=f"verify-flan-noperm-{unique}@example.test",
                hashed_password=hash_password("verify-flan-noperm-pw"),
                full_name="VERIFY no-permission user",
                is_active=True,
            )
            session.add(noperm)
            await session.flush()

            await session.commit()
            writer_id, reader_id, noperm_id = writer.id, reader.id, noperm.id
            role_ids.extend([writer_role.id, reader_role.id])
        user_ids.extend([writer_id, reader_id, noperm_id])

        writer_token = create_access_token(writer_id, [])
        reader_token = create_access_token(reader_id, [])
        noperm_token = create_access_token(noperm_id, [])

        # ===================================================================
        # (A) HAPPY PATH over HTTP with the writer — every one of the twenty
        #     routes, in dependency order, each recorded in `exercised`.
        #     The archive comes LAST: it freezes every write inside the
        #     project (422), so nothing may follow it.
        # ===================================================================
        body = writer_call(
            "POST /flan/projects",
            "POST",
            "/flan/projects",
            {
                "name": f"VERIFY-FLAN-API project {unique}",
                "key_prefix": "VFA",
                "category": "work",
                "tags": ["verify", "api"],
            },
            expect=201,
        )
        project_id = body.get("id") if isinstance(body, dict) else None
        if not project_id:
            print("FAIL: the project create returned no id — cannot continue.")
            sys.exit(2)

        writer_call(
            "PATCH /flan/projects/{project_id}",
            "PATCH",
            f"/flan/projects/{project_id}",
            {"description": "patched by verify_flan_api"},
        )

        # Two phases: PH1 is the live one, PH2 exists to be deleted (its task
        # goes with it, which is what phase.deleted's detail counts).
        body = writer_call(
            "POST /flan/projects/{project_id}/phases",
            "POST",
            f"/flan/projects/{project_id}/phases",
            {"name": f"Phase one {unique}", "sort_order": 1},
            expect=201,
        )
        phase1_id = body.get("id") if isinstance(body, dict) else None
        s, body = http(
            "POST",
            f"/flan/projects/{project_id}/phases",
            writer_token,
            {"name": f"Phase two {unique}", "sort_order": 2},
        )
        phase2_id = body.get("id") if isinstance(body, dict) else None
        if s == 201:
            expected_audit_rows += 1
        check(
            "(A) writer → 201 on POST .../phases (second phase, the delete target)",
            s == 201 and phase2_id is not None,
            f"status={s} body={body!r}",
        )

        writer_call(
            "PATCH /flan/phases/{phase_id}",
            "PATCH",
            f"/flan/phases/{phase1_id}",
            {"status": "in-progress"},
        )

        # Three tasks: T1 lives (patch/assignee/read target), T2 sits in PH2 so
        # the phase delete cascades to it, T3 is the delete target.
        body = writer_call(
            "POST /flan/projects/{project_id}/tasks",
            "POST",
            f"/flan/projects/{project_id}/tasks",
            {
                "phase_id": phase1_id,
                "summary": "Task one",
                "start_date": "2026-01-05",
                "due_date": "2026-01-09",
            },
            expect=201,
        )
        task1_id = body.get("id") if isinstance(body, dict) else None
        task1_key = body.get("key") if isinstance(body, dict) else None
        check(
            "(A) the created task carries a server-generated VFA-<n> key",
            isinstance(task1_key, str) and task1_key.startswith("VFA-"),
            f"key={task1_key!r}",
        )
        for label, phase_for, summary in (
            ("second task (cascade fodder in PH2)", phase2_id, "Task two"),
            ("third task (the delete target)", phase1_id, "Task three"),
        ):
            s, body = http(
                "POST",
                f"/flan/projects/{project_id}/tasks",
                writer_token,
                {"phase_id": phase_for, "summary": summary},
            )
            if s == 201:
                expected_audit_rows += 1
            check(
                f"(A) writer → 201 on POST .../tasks ({label})",
                s == 201,
                f"status={s} body={body!r}",
            )
            if summary == "Task two":
                task2_id = body.get("id") if isinstance(body, dict) else None
            else:
                task3_id = body.get("id") if isinstance(body, dict) else None

        writer_call(
            "PATCH /flan/tasks/{task_id}",
            "PATCH",
            f"/flan/tasks/{task1_id}",
            {"status": "Done"},
        )

        # Two roster members: M1 lives (patch/assignee target), M2 is removed.
        body = writer_call(
            "POST /flan/projects/{project_id}/team",
            "POST",
            f"/flan/projects/{project_id}/team",
            {"name": f"Member one {unique}", "role": "Engineer", "hourly_rate": "125.50"},
            expect=201,
        )
        member1_id = body.get("id") if isinstance(body, dict) else None
        s, body = http(
            "POST",
            f"/flan/projects/{project_id}/team",
            writer_token,
            {"name": f"Member two {unique}"},
        )
        member2_id = body.get("id") if isinstance(body, dict) else None
        if s == 201:
            expected_audit_rows += 1
        check(
            "(A) writer → 201 on POST .../team (second member, the remove target)",
            s == 201 and member2_id is not None,
            f"status={s} body={body!r}",
        )

        writer_call(
            "PATCH /flan/team/{member_id}",
            "PATCH",
            f"/flan/team/{member1_id}",
            {"role": "Lead engineer"},
        )

        writer_call(
            "PUT /flan/tasks/{task_id}/assignees",
            "PUT",
            f"/flan/tasks/{task1_id}/assignees",
            {"member_ids": [member1_id]},
        )
        writer_call(
            "PUT /flan/phases/{phase_id}/assignees",
            "PUT",
            f"/flan/phases/{phase1_id}/assignees",
            {"member_ids": [member1_id]},
        )

        writer_call(
            "DELETE /flan/tasks/{task_id}",
            "DELETE",
            f"/flan/tasks/{task3_id}",
            expect=204,
        )
        writer_call(
            "DELETE /flan/team/{member_id}",
            "DELETE",
            f"/flan/team/{member2_id}",
            expect=204,
        )
        writer_call(
            "DELETE /flan/phases/{phase_id}",
            "DELETE",
            f"/flan/phases/{phase2_id}",
            expect=204,
        )

        # --- the six reads, as the writer (who also holds flan:read) --------
        audit_before_reads = await _audit_count(session_factory, user_ids)

        body = writer_call("GET /flan/projects", "GET", "/flan/projects")
        listed = [p["id"] for p in body] if isinstance(body, list) else []
        check(
            "(A) GET /flan/projects lists the live project",
            project_id in listed,
            f"listed={len(listed)} ids",
        )
        writer_call(
            "GET /flan/projects/{project_id}", "GET", f"/flan/projects/{project_id}"
        )
        body = writer_call(
            "GET /flan/projects/{project_id}/phases",
            "GET",
            f"/flan/projects/{project_id}/phases",
        )
        phase_ids = [p["id"] for p in body] if isinstance(body, list) else []
        check(
            "(A) GET .../phases lists the live phase and not the deleted one",
            phase1_id in phase_ids and phase2_id not in phase_ids,
            f"phases={phase_ids!r}",
        )
        tasks_q = "?" + urllib.parse.urlencode({"phase_id": phase1_id})
        body = writer_call(
            "GET /flan/projects/{project_id}/tasks",
            "GET",
            f"/flan/projects/{project_id}/tasks{tasks_q}",
        )
        task_ids = [t["id"] for t in body] if isinstance(body, list) else []
        check(
            "(A) GET .../tasks lists the live task; the deleted and cascaded ones are gone",
            task1_id in task_ids and task2_id not in task_ids and task3_id not in task_ids,
            f"tasks={task_ids!r}",
        )
        writer_call("GET /flan/tasks/{task_id}", "GET", f"/flan/tasks/{task1_id}")
        body = writer_call(
            "GET /flan/projects/{project_id}/team",
            "GET",
            f"/flan/projects/{project_id}/team",
        )
        member_ids = [m["id"] for m in body] if isinstance(body, list) else []
        check(
            "(A) GET .../team lists the live member; the soft-removed one is hidden",
            member1_id in member_ids and member2_id not in member_ids,
            f"members={member_ids!r}",
        )

        audit_after_reads = await _audit_count(session_factory, user_ids)
        check(
            "(D) the six GET routes wrote NO audit rows (count unchanged across the read sweep)",
            audit_after_reads == audit_before_reads,
            f"before={audit_before_reads} after={audit_after_reads}",
        )

        # --- the archive goes last: it freezes every write in the project ---
        body = writer_call(
            "POST /flan/projects/{project_id}/archive",
            "POST",
            f"/flan/projects/{project_id}/archive",
        )
        check(
            "(A) the archive answers with active=False",
            isinstance(body, dict) and body.get("active") is False,
            f"body={body!r}",
        )

        # ===================================================================
        # (B) + (C) RBAC over EVERY route. The twenty are declared here as
        #     data — not discovered from app.routes, which on FastAPI 0.138
        #     yields _IncludedRouter wrappers and would enumerate nothing.
        #     Auth failures short-circuit before the service, so firing the
        #     mutations with a refused token cannot change any state.
        # ===================================================================
        write_routes = [
            ("POST /flan/projects", "POST", "/flan/projects", {"name": f"rbac-{unique}"}),
            ("PATCH /flan/projects/{project_id}", "PATCH", f"/flan/projects/{project_id}",
             {"description": "rbac"}),
            ("POST /flan/projects/{project_id}/archive", "POST",
             f"/flan/projects/{project_id}/archive", None),
            ("POST /flan/projects/{project_id}/phases", "POST",
             f"/flan/projects/{project_id}/phases", {"name": "rbac"}),
            ("PATCH /flan/phases/{phase_id}", "PATCH", f"/flan/phases/{phase1_id}",
             {"status": "complete"}),
            ("DELETE /flan/phases/{phase_id}", "DELETE", f"/flan/phases/{phase1_id}", None),
            ("POST /flan/projects/{project_id}/tasks", "POST",
             f"/flan/projects/{project_id}/tasks",
             {"phase_id": phase1_id, "summary": "rbac"}),
            ("PATCH /flan/tasks/{task_id}", "PATCH", f"/flan/tasks/{task1_id}",
             {"status": "To Do"}),
            ("DELETE /flan/tasks/{task_id}", "DELETE", f"/flan/tasks/{task1_id}", None),
            ("POST /flan/projects/{project_id}/team", "POST",
             f"/flan/projects/{project_id}/team", {"name": "rbac"}),
            ("PATCH /flan/team/{member_id}", "PATCH", f"/flan/team/{member1_id}",
             {"role": "rbac"}),
            ("DELETE /flan/team/{member_id}", "DELETE", f"/flan/team/{member1_id}", None),
            ("PUT /flan/tasks/{task_id}/assignees", "PUT",
             f"/flan/tasks/{task1_id}/assignees", {"member_ids": []}),
            ("PUT /flan/phases/{phase_id}/assignees", "PUT",
             f"/flan/phases/{phase1_id}/assignees", {"member_ids": []}),
        ]
        read_routes = [
            ("GET /flan/projects", "GET", "/flan/projects"),
            ("GET /flan/projects/{project_id}", "GET", f"/flan/projects/{project_id}"),
            ("GET /flan/projects/{project_id}/phases", "GET",
             f"/flan/projects/{project_id}/phases"),
            ("GET /flan/projects/{project_id}/tasks", "GET",
             f"/flan/projects/{project_id}/tasks"),
            ("GET /flan/tasks/{task_id}", "GET", f"/flan/tasks/{task1_id}"),
            ("GET /flan/projects/{project_id}/team", "GET",
             f"/flan/projects/{project_id}/team"),
        ]

        check(
            f"(B) the sweep declares all {ROUTE_COUNT} FLAN routes "
            f"({READ_ROUTE_COUNT} read + {WRITE_ROUTE_COUNT} write)",
            len(write_routes) == WRITE_ROUTE_COUNT
            and len(read_routes) == READ_ROUTE_COUNT
            and len(write_routes) + len(read_routes) == ROUTE_COUNT,
            f"write={len(write_routes)} read={len(read_routes)}",
        )
        declared_keys = {r[0] for r in write_routes} | {r[0] for r in read_routes}
        check(
            f"(A) the writer drove all {ROUTE_COUNT} routes to 2xx — the exercised set "
            "equals the declared set",
            declared_keys == set(exercised)
            and len(exercised) == ROUTE_COUNT
            and all(200 <= s < 300 for s in exercised.values()),
            f"missing={sorted(declared_keys - set(exercised))} "
            f"extra={sorted(set(exercised) - declared_keys)} statuses={exercised!r}",
        )

        for key, method, path, payload in write_routes:
            s, _ = http(method, path, reader_token, payload)
            check(f"(B) flan:read-only token → 403 on {key}", s == 403, f"status={s}")
            s, _ = http(method, path, noperm_token, payload)
            check(f"(B) no-permission token → 403 on {key}", s == 403, f"status={s}")
            s, _ = http(method, path, None, payload)
            check(f"(B) unauthenticated → 401 on {key}", s == 401, f"status={s}")

        for key, method, path in read_routes:
            s, _ = http(method, path, reader_token)
            check(f"(C) flan:read token → 200 on {key}", s == 200, f"status={s}")
            s, _ = http(method, path, noperm_token)
            check(f"(C) no-permission token → 403 on {key}", s == 403, f"status={s}")
            s, _ = http(method, path, None)
            check(f"(C) unauthenticated → 401 on {key}", s == 401, f"status={s}")

        # ===================================================================
        # (D) AUDIT — all fourteen actions, attributable, right target_type,
        #     and a target_id that IS a string of uuid shape (asserted, never
        #     assumed — the GELATO int-PK lesson, 136e98d).
        # ===================================================================
        audit_expectations = [
            ("project.created", "flan_project", project_id),
            ("project.updated", "flan_project", project_id),
            ("project.archived", "flan_project", project_id),
            ("phase.created", "flan_phase", phase1_id),
            ("phase.updated", "flan_phase", phase1_id),
            ("phase.deleted", "flan_phase", phase2_id),
            ("task.created", "flan_task", task1_id),
            ("task.updated", "flan_task", task1_id),
            ("task.deleted", "flan_task", task3_id),
            ("team_member.created", "flan_team_member", member1_id),
            ("team_member.updated", "flan_team_member", member1_id),
            ("team_member.removed", "flan_team_member", member2_id),
            ("task.assignees_set", "flan_task", task1_id),
            ("phase.assignees_set", "flan_phase", phase1_id),
        ]
        check(
            f"(D) all {AUDIT_ACTION_COUNT} FLAN audit actions are asserted",
            len(audit_expectations) == AUDIT_ACTION_COUNT
            and len({a for a, _, _ in audit_expectations}) == AUDIT_ACTION_COUNT,
            f"declared={len(audit_expectations)}",
        )

        for action, target_type, target_id in audit_expectations:
            row = await _audit_row(session_factory, action, target_id)
            check(
                f"(D) {action} audit row exists, actor=writer, target_type={target_type}",
                row is not None
                and row.actor_id == writer_id
                and row.target_type == target_type,
                f"row={row!r}",
            )
            shaped = False
            if row is not None and isinstance(row.target_id, str):
                try:
                    uuid.UUID(row.target_id)
                    shaped = row.target_id == target_id
                except ValueError:
                    shaped = False
            check(
                f"(D) {action} target_id is a STRING of uuid shape (not an int PK)",
                shaped,
                f"target_id={None if row is None else row.target_id!r} "
                f"type={None if row is None else type(row.target_id).__name__}",
            )

        # Every mutation wrote exactly one row and nothing else did: the count
        # attributable to this run's three users equals the 2xx mutation count.
        actual_rows = await _audit_count(session_factory, user_ids)
        check(
            "(D) this run wrote exactly one audit row per successful mutation, and the "
            "reader/noperm users wrote none",
            actual_rows == expected_audit_rows,
            f"expected={expected_audit_rows} actual={actual_rows}",
        )

    finally:
        await _cleanup(session_factory, project_id, user_ids, role_ids)
        await engine.dispose()


# ---------------------------------------------------------------------------
# Cleanup — delete only the throwaway rows, in FK-safe order
# ---------------------------------------------------------------------------


async def _cleanup(
    session_factory,
    project_id: str | None,
    user_ids: list[str],
    role_ids: list[int],
) -> None:
    """
    Delete this run's throwaway rows in FK-safe order: assignment rows -> task
    tags -> tasks -> phases -> project tags -> roster -> project -> the three
    throwaway users -> their roles.

    The audit_log rows are deliberately NOT deleted: the trail is append-only
    (D-14). They are found by target_id, which is a fresh uuid on every run, so
    leaving them cannot make a later run pass on an earlier run's evidence.
    """
    async with session_factory() as session:
        if project_id is not None:
            phase_ids = select(Phase.id).where(Phase.project_id == project_id)
            task_ids = select(Task.id).where(Task.project_id == project_id)
            await session.execute(
                delete(PhaseAssignee).where(PhaseAssignee.phase_id.in_(phase_ids))
            )
            await session.execute(
                delete(TaskAssignee).where(TaskAssignee.task_id.in_(task_ids))
            )
            await session.execute(delete(TaskTag).where(TaskTag.task_id.in_(task_ids)))
            await session.execute(delete(Task).where(Task.project_id == project_id))
            await session.execute(delete(Phase).where(Phase.project_id == project_id))
            await session.execute(
                delete(ProjectTag).where(ProjectTag.project_id == project_id)
            )
            await session.execute(
                delete(TeamMember).where(TeamMember.project_id == project_id)
            )
            await session.execute(delete(Project).where(Project.id == project_id))
        if user_ids:
            await session.execute(delete(User).where(User.id.in_(user_ids)))
        if role_ids:
            await session.execute(delete(Role).where(Role.id.in_(role_ids)))

        await session.commit()


def main() -> int:
    asyncio.run(run())
    if _FAILURES:
        print(f"\n{_FAILURES} assertion(s) FAILED.")
        return 1
    print(
        f"\nAll assertions PASSED — {ROUTE_COUNT} routes "
        f"({READ_ROUTE_COUNT} read + {WRITE_ROUTE_COUNT} write) and "
        f"{AUDIT_ACTION_COUNT} audit actions exercised over real HTTP."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
