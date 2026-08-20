# ABOUTME: HTTP client-layer port of verify_flan_api.py — the FLAN RBAC + audit crux (FLAN-01.7, NFR-5).
# ABOUTME: Drives the five entity groups (project, phase, task, member, assignment) through the ASGI
# ABOUTME: client, proving the 401/403/2xx triad and an attributable AuditLog row per group, plus the
# ABOUTME: HTTP 422 a client actually receives for `due < start` on task create and a one-date PATCH.
"""
FLAN router RBAC + audit crux — ported from ``backend/scripts/verify_flan_api.py``
to the ``client`` (httpx-ASGI) layer (NFR-5).

WHY THIS EXISTS (the router proof — the companion to test_rollup.py):
  test_rollup.py drives the flan SERVICE functions directly and so proves the
  phase-rollup crux (derived dates, % complete, numeric-safe keys, roster
  removal, cascade), but it can never exercise the two things that live only in
  the ROUTER: the audit row written by ``write_audit`` and the RBAC gate
  enforced by ``require_permission("flan:read" / "flan:write")``. This module
  closes that gap by making REAL HTTP calls against the ASGI app and asserting,
  for each of the FIVE entity groups, on one representative mutation and one
  representative read:

    | group      | mutation                                | read                                  |
    |------------|-----------------------------------------|---------------------------------------|
    | project    | POST   /flan/projects                   | GET /flan/projects/{id}               |
    | phase      | POST   /flan/projects/{id}/phases       | GET /flan/projects/{id}/phases        |
    | task       | POST   /flan/projects/{id}/tasks        | GET /flan/tasks/{id}                  |
    | member     | POST   /flan/projects/{id}/team         | GET /flan/projects/{id}/team          |
    | assignment | PUT    /flan/tasks/{id}/assignees       | GET /flan/projects/{id}/tasks?assignee_id= |

  Each mutation: writer token → 2xx, flan:read-only reader → 403, no token →
  401. Each read: reader token → 200, no-permission token → 403, no token →
  401. After each 2xx mutation, the matching AuditLog row must exist, be
  attributable to the acting writer (``actor_id``) and target the affected row
  (``target_type``/``target_id``, asserted to be a **string** — the GELATO
  int-PK lesson, 136e98d; a FLAN id is already a uuid4 string, and this pins it).

WHAT THE AMENDMENT ADDS — the HTTP 422 for ``due < start`` (FLAN-01.3):
  Three checks in this phase touch ``due < start`` and none of them proved the
  status a CLIENT receives. ``verify_flan.py`` (C1/C2) proves the refusal
  in-process — a ``pydantic.ValidationError`` on create and a service
  ``HTTPException`` on the merged PATCH — and would still pass if the router
  swallowed the exception and answered 200; ``verify_flan_api.py`` posts dates
  but never asserts a wire status for the inverted pair. FLAN-01.3 says
  ``due < start`` is "rejected server-side (4xx)", which is a statement about
  the wire, so the last two tests here assert it there:

    * ``POST /flan/projects/{id}/tasks`` with due before start → **422** (the
      schema validator, surfaced by FastAPI as a request-validation error), with
      ``due == start`` accepted alongside it as the zero-duration milestone;
    * ``PATCH /flan/tasks/{id}`` moving only ONE date past the other → **422**
      (the service's merged re-check, the only place a one-date PATCH can be
      caught), in both directions, with the stored row left untouched.

  Neither of these routes is enumerated from ``app.routes``: on FastAPI 0.138 an
  ``include_router`` is wrapped in ``_IncludedRouter`` and ``app.routes`` yields
  ZERO module routes, so a discovery-driven sweep would pass vacuously. Every
  path here is spelled out as a literal, exactly as verify_flan_api.py does.

``require_permission`` reads the user's ROLES from the DB (not the JWT perms
claim, D-P2a-4), so a genuine 403 requires a REAL limited User bound to a Role
holding only the read scope. This mints THREE throwaway identities in a LOCAL
per-test fixture (D-P2b-4) on the clean per-test DB (created AFTER _isolate,
whose reseed creates the flan:read/flan:write Permission rows; the next test's
TRUNCATE sweeps them):
  * writer — role holding flan:read + flan:write (the 2xx; the audit rows are
             attributable to THIS user);
  * reader — role holding ONLY flan:read (200 on reads, 403 on mutations);
  * noperm — no roles at all (403 on reads, the no-permission case).
Tokens are minted with create_access_token — no password round-trip needed.
"""
from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import select

# app.core.models imports every module's models, so flan_team_member's
# user_id → users.id FK resolves (a bare `from app.modules.flan.models import ...`
# raises NoReferencedTableError when auth's User table is not yet mapped).
import app.core.models  # noqa: F401
from app.modules.auth.models import AuditLog, Permission, Role, User
from app.modules.auth.service import create_access_token, hash_password

# ---------------------------------------------------------------------------
# Local per-test identity fixture (D-P2b-4) — writer / reader / noperm.
#
# Minted on the clean per-test DB (test_sessionmaker runs AFTER the autouse
# _isolate truncate+reseed, which creates the flan:read/flan:write Permission
# rows). Mirrors verify_flan_api.py's throwaway-identity minting near-verbatim;
# no cleanup — the next test's TRUNCATE RESTART IDENTITY CASCADE sweeps these.
# ---------------------------------------------------------------------------


@pytest.fixture
async def flan_identities(test_sessionmaker) -> dict:
    """
    Mint five real Users bound to real Roles and return their ids + Bearer tokens.

    writer → role with flan:read + flan:write; reader → role with flan:read
    only; noperm → no roles. Tokens are minted with create_access_token (the
    perms claim is ignored by RBAC, which authorizes from the DB roles —
    D-P2a-4).

    Two more exist for the `hourly_rate` field gate, which is a scope ABOVE
    flan:write (auth/seed.py grants the default 'user' role flan:read+flan:write
    and NOT flan:rates, so `writer` is deliberately the realistic non-holder):
      * rater — role with flan:read + flan:write + flan:rates (the holder);
      * wildcard_admin — a role literally NAMED "admin" holding NO permission
        rows at all, which is the only way to prove the wildcard in
        has_permission grants flan:rates rather than a stray explicit grant
        doing it.
    """
    unique = uuid.uuid4().hex[:8]
    async with test_sessionmaker() as session:
        perms = {
            p.code: p
            for p in (
                await session.execute(
                    select(Permission).where(
                        Permission.code.in_(["flan:read", "flan:write", "flan:rates"])
                    )
                )
            ).scalars().all()
        }
        assert "flan:read" in perms and "flan:write" in perms, (
            "seeded flan:read/flan:write permissions not found"
        )
        assert "flan:rates" in perms, "seeded flan:rates permission not found"

        writer_role = Role(
            name=f"test-flan-writer-{unique}",
            description="test throwaway role: flan:read + flan:write",
        )
        session.add(writer_role)
        await session.flush()
        (await writer_role.awaitable_attrs.permissions).extend(
            [perms["flan:read"], perms["flan:write"]]
        )

        reader_role = Role(
            name=f"test-flan-reader-{unique}",
            description="test throwaway role: flan:read only",
        )
        session.add(reader_role)
        await session.flush()
        (await reader_role.awaitable_attrs.permissions).append(perms["flan:read"])

        writer = User(
            email=f"test-flan-writer-{unique}@example.test",
            hashed_password=hash_password("test-flan-writer-pw"),
            full_name="TEST flan:write user",
            is_active=True,
        )
        session.add(writer)
        await session.flush()
        (await writer.awaitable_attrs.roles).append(writer_role)

        reader = User(
            email=f"test-flan-reader-{unique}@example.test",
            hashed_password=hash_password("test-flan-reader-pw"),
            full_name="TEST flan:read-only user",
            is_active=True,
        )
        session.add(reader)
        await session.flush()
        (await reader.awaitable_attrs.roles).append(reader_role)

        noperm = User(
            email=f"test-flan-noperm-{unique}@example.test",
            hashed_password=hash_password("test-flan-noperm-pw"),
            full_name="TEST no-permission user",
            is_active=True,
        )
        session.add(noperm)
        await session.flush()

        rater_role = Role(
            name=f"test-flan-rater-{unique}",
            description="test throwaway role: flan:read + flan:write + flan:rates",
        )
        session.add(rater_role)
        await session.flush()
        (await rater_role.awaitable_attrs.permissions).extend(
            [perms["flan:read"], perms["flan:write"], perms["flan:rates"]]
        )

        rater = User(
            email=f"test-flan-rater-{unique}@example.test",
            hashed_password=hash_password("test-flan-rater-pw"),
            full_name="TEST flan:rates user",
            is_active=True,
        )
        session.add(rater)
        await session.flush()
        (await rater.awaitable_attrs.roles).append(rater_role)

        # The wildcard admin. `roles.name` is UNIQUE, so this must reuse the
        # SEEDED 'admin' role — which holds every permission code, flan:rates
        # included, and would therefore satisfy the field gate explicitly and
        # make the wildcard assertion pass for the wrong reason. So flan:rates
        # is STRIPPED from it here: after this, the only thing that can grant
        # this user the rate field is role.name == "admin". The next test's
        # TRUNCATE + reseed puts the grant back.
        admin_role = (
            await session.execute(select(Role).where(Role.name == "admin"))
        ).scalars().first()
        assert admin_role is not None, "seeded 'admin' role not found"
        admin_perms = await admin_role.awaitable_attrs.permissions
        for granted in list(admin_perms):
            if granted.code == "flan:rates":
                admin_perms.remove(granted)
        await session.flush()
        assert "flan:rates" not in {
            granted.code for granted in await admin_role.awaitable_attrs.permissions
        }, "flan:rates still explicitly granted to the admin role — wildcard unproven"

        wildcard_admin = User(
            email=f"test-flan-admin-{unique}@example.test",
            hashed_password=hash_password("test-flan-admin-pw"),
            full_name="TEST wildcard admin",
            is_active=True,
        )
        session.add(wildcard_admin)
        await session.flush()
        (await wildcard_admin.awaitable_attrs.roles).append(admin_role)

        await session.commit()
        writer_id, reader_id, noperm_id = writer.id, reader.id, noperm.id
        rater_id, admin_id = rater.id, wildcard_admin.id

    return {
        "writer_id": writer_id,
        "reader_id": reader_id,
        "noperm_id": noperm_id,
        "rater_id": rater_id,
        "admin_id": admin_id,
        "writer_token": create_access_token(writer_id, []),
        "reader_token": create_access_token(reader_id, []),
        "noperm_token": create_access_token(noperm_id, []),
        "rater_token": create_access_token(rater_id, []),
        "admin_token": create_access_token(admin_id, []),
    }


# ---------------------------------------------------------------------------
# Helpers — auth headers, the writer-driven scaffold, and the audit oracle.
# ---------------------------------------------------------------------------


def _auth(token: str) -> dict[str, str]:
    """Bearer header for one of the three throwaway identities."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def flan_scaffold(client: httpx.AsyncClient, flan_identities: dict) -> dict:
    """
    One project with a phase, a task and a roster member, built over REAL HTTP.

    Driven entirely by the writer token through the same routes under test, so
    the scaffold is itself evidence the happy path works before any group test
    asserts a refusal on it.
    """
    unique = uuid.uuid4().hex[:8]
    headers = _auth(flan_identities["writer_token"])

    resp = await client.post(
        "/api/v1/flan/projects",
        json={"name": f"FLAN-API scaffold {unique}", "key_prefix": "FAS", "category": "work"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/flan/projects/{project_id}/phases",
        json={"name": f"Scaffold phase {unique}", "sort_order": 1},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    phase_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/flan/projects/{project_id}/tasks",
        json={"phase_id": phase_id, "summary": "Scaffold task"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    task_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/flan/projects/{project_id}/team",
        json={"name": f"Scaffold member {unique}", "role": "Engineer"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    member_id = resp.json()["id"]

    return {
        "unique": unique,
        "project_id": project_id,
        "phase_id": phase_id,
        "task_id": task_id,
        "member_id": member_id,
    }


async def _assert_audit(
    test_sessionmaker,
    *,
    action: str,
    target_type: str,
    target_id: str,
    actor_id: str,
) -> None:
    """
    Assert exactly one attributable AuditLog row for the mutation just made.

    Read on its own session so the router's own commit is what is being
    observed, never a cached identity-map object. `target_id` is asserted to be
    a STRING as well as equal: AuditLog.target_id is VARCHAR(36) and a router
    handing it a non-string is the 12a int-PK defect (136e98d).
    """
    async with test_sessionmaker() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.action == action,
                    AuditLog.target_id == target_id,
                )
            )
        ).scalars().all()
    assert len(rows) == 1, f"expected exactly one {action} audit row, got {len(rows)}"
    row = rows[0]
    assert row.actor_id == actor_id, f"{action} is not attributable to the acting writer"
    assert row.target_type == target_type
    assert row.target_id == target_id
    assert isinstance(row.target_id, str)


async def _assert_no_audit(test_sessionmaker, *, action: str) -> int:
    """Return the current row count for one action (the refusals must not add any)."""
    async with test_sessionmaker() as session:
        rows = (
            await session.execute(select(AuditLog).where(AuditLog.action == action))
        ).scalars().all()
    return len(rows)


# ---------------------------------------------------------------------------
# Group 1 — PROJECT: POST /flan/projects + GET /flan/projects/{id}
# ---------------------------------------------------------------------------


async def test_flan_project_rbac_and_audit(
    client: httpx.AsyncClient,
    test_sessionmaker,
    flan_identities: dict,
) -> None:
    """
    Project create/read RBAC triad + an attributable project.created audit row.

    POST /flan/projects: writer → 201, flan:read-only reader → 403, no token →
    401 (and neither refusal writes an audit row — auth short-circuits before
    the service, so no project can leak out of a 403).
    GET /flan/projects/{id}: reader → 200, noperm → 403, no token → 401.
    """
    unique = uuid.uuid4().hex[:8]
    writer_id = flan_identities["writer_id"]
    payload = {"name": f"FLAN-API project {unique}", "key_prefix": "FAP", "category": "work"}

    # --- writer (flan:write) → 201 ---
    resp = await client.post(
        "/api/v1/flan/projects", json=payload, headers=_auth(flan_identities["writer_token"])
    )
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]
    assert resp.json()["key_prefix"] == "FAP"

    # --- attributable project.created audit row ---
    await _assert_audit(
        test_sessionmaker,
        action="project.created",
        target_type="flan_project",
        target_id=str(project_id),
        actor_id=writer_id,
    )
    before = await _assert_no_audit(test_sessionmaker, action="project.created")

    # --- flan:read-only reader → 403; unauthenticated → 401 ---
    resp = await client.post(
        "/api/v1/flan/projects", json=payload, headers=_auth(flan_identities["reader_token"])
    )
    assert resp.status_code == 403, resp.text
    resp = await client.post("/api/v1/flan/projects", json=payload)
    assert resp.status_code == 401, resp.text
    assert await _assert_no_audit(test_sessionmaker, action="project.created") == before, (
        "a refused project create wrote an audit row"
    )

    # --- READ GET /flan/projects/{id}: reader 200 / noperm 403 / no token 401 ---
    resp = await client.get(
        f"/api/v1/flan/projects/{project_id}", headers=_auth(flan_identities["reader_token"])
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == project_id

    resp = await client.get(
        f"/api/v1/flan/projects/{project_id}", headers=_auth(flan_identities["noperm_token"])
    )
    assert resp.status_code == 403, resp.text

    resp = await client.get(f"/api/v1/flan/projects/{project_id}")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Group 2 — PHASE: POST /flan/projects/{id}/phases + GET .../phases
# ---------------------------------------------------------------------------


async def test_flan_phase_rbac_and_audit(
    client: httpx.AsyncClient,
    test_sessionmaker,
    flan_identities: dict,
    flan_scaffold: dict,
) -> None:
    """
    Phase create/list RBAC triad + an attributable phase.created audit row.

    POST /flan/projects/{id}/phases: writer → 201, reader → 403, no token → 401.
    GET /flan/projects/{id}/phases: reader → 200 (and the created phase is in
    the list, carrying its DERIVED rollup fields — the read really ran), noperm
    → 403, no token → 401.
    """
    project_id = flan_scaffold["project_id"]
    writer_id = flan_identities["writer_id"]
    payload = {"name": f"RBAC phase {flan_scaffold['unique']}", "sort_order": 2}
    path = f"/api/v1/flan/projects/{project_id}/phases"

    # --- writer (flan:write) → 201 ---
    resp = await client.post(path, json=payload, headers=_auth(flan_identities["writer_token"]))
    assert resp.status_code == 201, resp.text
    phase_id = resp.json()["id"]

    await _assert_audit(
        test_sessionmaker,
        action="phase.created",
        target_type="flan_phase",
        target_id=str(phase_id),
        actor_id=writer_id,
    )
    before = await _assert_no_audit(test_sessionmaker, action="phase.created")

    # --- reader → 403; unauthenticated → 401 ---
    resp = await client.post(path, json=payload, headers=_auth(flan_identities["reader_token"]))
    assert resp.status_code == 403, resp.text
    resp = await client.post(path, json=payload)
    assert resp.status_code == 401, resp.text
    assert await _assert_no_audit(test_sessionmaker, action="phase.created") == before, (
        "a refused phase create wrote an audit row"
    )

    # --- READ GET .../phases: reader 200 / noperm 403 / no token 401 ---
    resp = await client.get(path, headers=_auth(flan_identities["reader_token"]))
    assert resp.status_code == 200, resp.text
    listed = {p["id"]: p for p in resp.json()}
    assert phase_id in listed
    assert listed[phase_id]["percent_complete"] == "0.00"

    resp = await client.get(path, headers=_auth(flan_identities["noperm_token"]))
    assert resp.status_code == 403, resp.text

    resp = await client.get(path)
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Group 3 — TASK: POST /flan/projects/{id}/tasks + GET /flan/tasks/{id}
# ---------------------------------------------------------------------------


async def test_flan_task_rbac_and_audit(
    client: httpx.AsyncClient,
    test_sessionmaker,
    flan_identities: dict,
    flan_scaffold: dict,
) -> None:
    """
    Task create/read RBAC triad + an attributable task.created audit row.

    POST /flan/projects/{id}/tasks: writer → 201 with a server-generated
    `FAS-<n>` key, reader → 403, no token → 401.
    GET /flan/tasks/{id}: reader → 200, noperm → 403, no token → 401.
    """
    project_id = flan_scaffold["project_id"]
    writer_id = flan_identities["writer_id"]
    payload = {"phase_id": flan_scaffold["phase_id"], "summary": "RBAC task"}
    path = f"/api/v1/flan/projects/{project_id}/tasks"

    # --- writer (flan:write) → 201 ---
    resp = await client.post(path, json=payload, headers=_auth(flan_identities["writer_token"]))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    task_id = body["id"]
    assert body["key"].startswith("FAS-"), body["key"]

    await _assert_audit(
        test_sessionmaker,
        action="task.created",
        target_type="flan_task",
        target_id=str(task_id),
        actor_id=writer_id,
    )
    before = await _assert_no_audit(test_sessionmaker, action="task.created")

    # --- reader → 403; unauthenticated → 401 ---
    resp = await client.post(path, json=payload, headers=_auth(flan_identities["reader_token"]))
    assert resp.status_code == 403, resp.text
    resp = await client.post(path, json=payload)
    assert resp.status_code == 401, resp.text
    assert await _assert_no_audit(test_sessionmaker, action="task.created") == before, (
        "a refused task create wrote an audit row"
    )

    # --- READ GET /flan/tasks/{id}: reader 200 / noperm 403 / no token 401 ---
    resp = await client.get(
        f"/api/v1/flan/tasks/{task_id}", headers=_auth(flan_identities["reader_token"])
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == task_id

    resp = await client.get(
        f"/api/v1/flan/tasks/{task_id}", headers=_auth(flan_identities["noperm_token"])
    )
    assert resp.status_code == 403, resp.text

    resp = await client.get(f"/api/v1/flan/tasks/{task_id}")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Group 4 — TEAM MEMBER: POST /flan/projects/{id}/team + GET .../team
# ---------------------------------------------------------------------------


async def test_flan_team_member_rbac_and_audit(
    client: httpx.AsyncClient,
    test_sessionmaker,
    flan_identities: dict,
    flan_scaffold: dict,
) -> None:
    """
    Roster create/list RBAC triad + an attributable team_member.created audit row.

    POST /flan/projects/{id}/team: writer → 201, reader → 403, no token → 401.
    GET /flan/projects/{id}/team: reader → 200 (the new member listed), noperm →
    403, no token → 401.
    """
    project_id = flan_scaffold["project_id"]
    writer_id = flan_identities["writer_id"]
    # No `hourly_rate` here: this writer holds flan:read + flan:write and NOT
    # flan:rates, so a body carrying the rate would (correctly) 403 before the
    # create ever ran. The rate matrix is test_flan_hourly_rate_* below.
    payload = {"name": f"RBAC member {flan_scaffold['unique']}"}
    path = f"/api/v1/flan/projects/{project_id}/team"

    # --- writer (flan:write) → 201 ---
    resp = await client.post(path, json=payload, headers=_auth(flan_identities["writer_token"]))
    assert resp.status_code == 201, resp.text
    member_id = resp.json()["id"]

    await _assert_audit(
        test_sessionmaker,
        action="team_member.created",
        target_type="flan_team_member",
        target_id=str(member_id),
        actor_id=writer_id,
    )
    before = await _assert_no_audit(test_sessionmaker, action="team_member.created")

    # --- reader → 403; unauthenticated → 401 ---
    resp = await client.post(path, json=payload, headers=_auth(flan_identities["reader_token"]))
    assert resp.status_code == 403, resp.text
    resp = await client.post(path, json=payload)
    assert resp.status_code == 401, resp.text
    assert await _assert_no_audit(test_sessionmaker, action="team_member.created") == before, (
        "a refused roster create wrote an audit row"
    )

    # --- READ GET .../team: reader 200 / noperm 403 / no token 401 ---
    resp = await client.get(path, headers=_auth(flan_identities["reader_token"]))
    assert resp.status_code == 200, resp.text
    assert member_id in [m["id"] for m in resp.json()]

    resp = await client.get(path, headers=_auth(flan_identities["noperm_token"]))
    assert resp.status_code == 403, resp.text

    resp = await client.get(path)
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Group 5 — ASSIGNMENT: PUT /flan/tasks/{id}/assignees + the by-assignee board read
# ---------------------------------------------------------------------------


async def test_flan_assignment_rbac_and_audit(
    client: httpx.AsyncClient,
    test_sessionmaker,
    flan_identities: dict,
    flan_scaffold: dict,
) -> None:
    """
    Assignee-set RBAC triad + an attributable task.assignees_set audit row.

    PUT /flan/tasks/{id}/assignees: writer → 200 answering with the stored set,
    reader → 403, no token → 401.
    GET /flan/projects/{id}/tasks?assignee_id=… (the board's filter-by-assignee,
    FLAN-01.5): reader → 200 returning exactly the assigned task, noperm → 403,
    no token → 401.
    """
    project_id = flan_scaffold["project_id"]
    task_id = flan_scaffold["task_id"]
    member_id = flan_scaffold["member_id"]
    writer_id = flan_identities["writer_id"]
    payload = {"member_ids": [member_id]}
    path = f"/api/v1/flan/tasks/{task_id}/assignees"

    # --- writer (flan:write) → 200 with the assignee set read back ---
    resp = await client.put(path, json=payload, headers=_auth(flan_identities["writer_token"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["member_ids"] == [member_id]

    await _assert_audit(
        test_sessionmaker,
        action="task.assignees_set",
        target_type="flan_task",
        target_id=str(task_id),
        actor_id=writer_id,
    )
    before = await _assert_no_audit(test_sessionmaker, action="task.assignees_set")

    # --- reader → 403; unauthenticated → 401 ---
    resp = await client.put(path, json=payload, headers=_auth(flan_identities["reader_token"]))
    assert resp.status_code == 403, resp.text
    resp = await client.put(path, json=payload)
    assert resp.status_code == 401, resp.text
    assert await _assert_no_audit(test_sessionmaker, action="task.assignees_set") == before, (
        "a refused assignee replacement wrote an audit row"
    )

    # --- READ the filtered board: reader 200 / noperm 403 / no token 401 ---
    board = f"/api/v1/flan/projects/{project_id}/tasks?assignee_id={member_id}"
    resp = await client.get(board, headers=_auth(flan_identities["reader_token"]))
    assert resp.status_code == 200, resp.text
    assert [t["id"] for t in resp.json()] == [task_id]

    resp = await client.get(board, headers=_auth(flan_identities["noperm_token"]))
    assert resp.status_code == 403, resp.text

    resp = await client.get(board)
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Group 6 — the `hourly_rate` FIELD gate (flan:rates).
#
# flan:read opens a project's whole roster, and auth/seed.py grants the default
# 'user' role flan:read + flan:write, so before this gate any rostered
# contractor could read AND PATCH every teammate's pay. `flan:rates` is seeded
# and granted to no role; `writer` below is the realistic non-holder.
#
# Two shapes are asserted rather than assumed:
#   * a non-holder's payload has NO `hourly_rate` KEY — not the key set to null,
#     which already means "no rate recorded" and would come straight back on the
#     next save as a deliberate clear;
#   * a non-holder SETTING the key is refused with 403, not silently dropped —
#     including an explicit `hourly_rate: null`, which is a write.
# ---------------------------------------------------------------------------

RATE = "125.500000"


async def test_hourly_rate_key_is_absent_for_a_caller_without_flan_rates(
    client: httpx.AsyncClient,
    flan_identities: dict,
    flan_scaffold: dict,
) -> None:
    """
    GET .../team omits the `hourly_rate` KEY entirely for a non-holder.

    The rater (flan:read+write+rates) stores a real rate; then the same roster is
    read three ways. The writer — flan:read + flan:write, exactly the default
    'user' role — must not see the key AT ALL: `is None` would pass on a nulled
    field, so this asserts `not in`. The rater sees the backend's own Decimal
    string verbatim (D-11), and the wildcard admin sees it through role.name
    alone (the fixture strips the explicit grant from the admin role).
    """
    project_id = flan_scaffold["project_id"]
    path = f"/api/v1/flan/projects/{project_id}/team"

    resp = await client.post(
        path,
        json={"name": f"Rated member {flan_scaffold['unique']}", "hourly_rate": RATE},
        headers=_auth(flan_identities["rater_token"]),
    )
    assert resp.status_code == 201, resp.text
    member_id = resp.json()["id"]
    assert resp.json()["hourly_rate"] == RATE, "the holder's create response lost the rate"

    def member_of(body: list[dict]) -> dict:
        return next(m for m in body if m["id"] == member_id)

    # --- the non-holder: the KEY is gone, not nulled ---
    resp = await client.get(path, headers=_auth(flan_identities["writer_token"]))
    assert resp.status_code == 200, resp.text
    row = member_of(resp.json())
    assert "hourly_rate" not in row, (
        f"flan:write without flan:rates was served the pay field: {row!r}"
    )
    # Every other roster field is still there — this omits one key, not a column.
    assert row["name"].startswith("Rated member")
    assert {"id", "project_id", "name", "role", "email", "color", "user_id", "active"} <= set(row)

    # --- the reader (flan:read only) is equally a non-holder ---
    resp = await client.get(path, headers=_auth(flan_identities["reader_token"]))
    assert resp.status_code == 200, resp.text
    assert "hourly_rate" not in member_of(resp.json())

    # --- the holder sees it, as the exact string the backend stored (D-11) ---
    resp = await client.get(path, headers=_auth(flan_identities["rater_token"]))
    assert resp.status_code == 200, resp.text
    assert member_of(resp.json())["hourly_rate"] == RATE

    # --- the admin wildcard grants it with no explicit flan:rates row ---
    resp = await client.get(path, headers=_auth(flan_identities["admin_token"]))
    assert resp.status_code == 200, resp.text
    assert member_of(resp.json())["hourly_rate"] == RATE


async def test_setting_hourly_rate_without_flan_rates_is_refused_not_dropped(
    client: httpx.AsyncClient,
    test_sessionmaker,
    flan_identities: dict,
    flan_scaffold: dict,
) -> None:
    """
    A non-holder sending `hourly_rate` gets 403 — on create AND on patch.

    Silently dropping the field would make the UI report a save that did not
    happen, so the refusal is loud and comes BEFORE the service: neither a row
    nor an audit entry is written. An explicit `hourly_rate: null` is refused
    too — it CLEARS stored compensation data, so it is a write, and
    `model_fields_set` is what tells it apart from an omitted key.
    """
    project_id = flan_scaffold["project_id"]
    path = f"/api/v1/flan/projects/{project_id}/team"
    headers = _auth(flan_identities["writer_token"])
    detail = "Permission denied: flan:rates required"

    # A member that already HAS a rate, stored by the holder.
    resp = await client.post(
        path,
        json={"name": f"Paid member {flan_scaffold['unique']}", "hourly_rate": RATE},
        headers=_auth(flan_identities["rater_token"]),
    )
    assert resp.status_code == 201, resp.text
    member_id = resp.json()["id"]
    created_before = await _assert_no_audit(test_sessionmaker, action="team_member.created")
    updated_before = await _assert_no_audit(test_sessionmaker, action="team_member.updated")

    # --- CREATE carrying a rate → 403 ---
    resp = await client.post(
        path, json={"name": "Refused create", "hourly_rate": RATE}, headers=headers
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == detail

    # --- CREATE carrying an EXPLICIT NULL rate → 403 (null is a write) ---
    resp = await client.post(
        path, json={"name": "Refused null create", "hourly_rate": None}, headers=headers
    )
    assert resp.status_code == 403, resp.text

    # --- PATCH carrying a rate → 403, and PATCH nulling it → 403 ---
    member_path = f"/api/v1/flan/team/{member_id}"
    resp = await client.patch(member_path, json={"hourly_rate": "1.00"}, headers=headers)
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == detail
    resp = await client.patch(member_path, json={"hourly_rate": None}, headers=headers)
    assert resp.status_code == 403, resp.text

    # Nothing was created, nothing was updated, nothing was audited.
    assert await _assert_no_audit(test_sessionmaker, action="team_member.created") == (
        created_before
    ), "a refused rate-bearing create wrote an audit row"
    assert await _assert_no_audit(test_sessionmaker, action="team_member.updated") == (
        updated_before
    ), "a refused rate-bearing patch wrote an audit row"

    # The stored rate is untouched — the refusals did not clear it.
    resp = await client.get(path, headers=_auth(flan_identities["rater_token"]))
    assert resp.status_code == 200, resp.text
    stored = next(m for m in resp.json() if m["id"] == member_id)
    assert stored["hourly_rate"] == RATE
    assert stored["name"] == f"Paid member {flan_scaffold['unique']}"
    assert "Refused create" not in [m["name"] for m in resp.json()]


async def test_a_non_holder_still_creates_and_edits_members_without_the_rate_key(
    client: httpx.AsyncClient,
    flan_identities: dict,
    flan_scaffold: dict,
) -> None:
    """
    Omitting `hourly_rate` needs no permission — the gate is on the KEY, not the route.

    A member of the project holding only flan:read + flan:write must still be
    able to run the roster: add people and edit them, as long as the body says
    nothing about pay. If this failed, the field gate would have become a route
    gate.
    """
    project_id = flan_scaffold["project_id"]
    path = f"/api/v1/flan/projects/{project_id}/team"
    headers = _auth(flan_identities["writer_token"])

    resp = await client.post(
        path,
        json={"name": f"Unpaid member {flan_scaffold['unique']}", "role": "Technician"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    member_id = body["id"]
    assert "hourly_rate" not in body, f"the create response leaked the pay field: {body!r}"

    resp = await client.patch(
        f"/api/v1/flan/team/{member_id}",
        json={"role": "Senior technician", "color": "#0EA5E9"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "Senior technician"
    assert body["color"] == "#0EA5E9"
    assert "hourly_rate" not in body

    # The holder confirms the member really was stored with no rate — "the key
    # was absent" and "the rate is null" are different facts and both are true.
    resp = await client.get(path, headers=_auth(flan_identities["rater_token"]))
    assert resp.status_code == 200, resp.text
    stored = next(m for m in resp.json() if m["id"] == member_id)
    assert stored["hourly_rate"] is None
    assert stored["role"] == "Senior technician"


# ---------------------------------------------------------------------------
# The amendment — `due < start` is refused ON THE WIRE (FLAN-01.3).
#
# verify_flan.py (C1/C2) proves the refusal in-process and would still pass if
# the router answered 200; these two assert the status a CLIENT receives.
# ---------------------------------------------------------------------------


async def test_task_create_refuses_due_before_start_on_the_wire(
    client: httpx.AsyncClient,
    flan_identities: dict,
    flan_scaffold: dict,
) -> None:
    """
    POST /flan/projects/{id}/tasks with due < start answers **HTTP 422**.

    This is the wire half of FLAN-01.3's "rejected server-side (4xx)". The
    schema's model validator raises a ValueError, which FastAPI surfaces as a
    request-validation error — but that translation is exactly what nothing else
    in this phase asserted. `due == start` is posted alongside it and MUST be
    accepted: the guard rejects an inverted pair, not a zero-duration milestone.
    """
    project_id = flan_scaffold["project_id"]
    phase_id = flan_scaffold["phase_id"]
    headers = _auth(flan_identities["writer_token"])
    path = f"/api/v1/flan/projects/{project_id}/tasks"

    # --- due BEFORE start → 422 on the wire ---
    resp = await client.post(
        path,
        json={
            "phase_id": phase_id,
            "summary": "Inverted dates",
            "start_date": "2026-03-10",
            "due_date": "2026-03-09",
        },
        headers=headers,
    )
    assert resp.status_code == 422, (
        f"due < start was accepted over HTTP: status={resp.status_code} body={resp.text}"
    )
    assert "must not precede" in resp.text

    # --- the task must not exist: a 4xx that still wrote the row is no refusal ---
    resp = await client.get(path, headers=headers)
    assert resp.status_code == 200, resp.text
    assert "Inverted dates" not in [t["summary"] for t in resp.json()]

    # --- due == start → 201, the zero-duration milestone (FLAN-01.3) ---
    resp = await client.post(
        path,
        json={
            "phase_id": phase_id,
            "summary": "Milestone",
            "start_date": "2026-03-10",
            "due_date": "2026-03-10",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["start_date"] == resp.json()["due_date"] == "2026-03-10"


async def test_one_date_task_patch_refuses_due_before_start_on_the_wire(
    client: httpx.AsyncClient,
    flan_identities: dict,
    flan_scaffold: dict,
) -> None:
    """
    A ONE-DATE PATCH /flan/tasks/{id} that inverts the pair answers **HTTP 422**.

    The schema validator cannot see this: a payload carrying only `due_date` has
    no `start_date` to compare against, so the refusal comes from `update_task`
    re-checking the order over the STORED row merged with the patch. That
    service check raises an HTTPException(422) — verify_flan.py (C2) proves it
    in-process, and this proves the router hands the 422 to the client rather
    than swallowing it. Both directions are exercised, and the stored row must
    come through untouched.
    """
    project_id = flan_scaffold["project_id"]
    phase_id = flan_scaffold["phase_id"]
    headers = _auth(flan_identities["writer_token"])

    resp = await client.post(
        f"/api/v1/flan/projects/{project_id}/tasks",
        json={
            "phase_id": phase_id,
            "summary": "Dated task",
            "start_date": "2026-03-10",
            "due_date": "2026-03-20",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    task_id = resp.json()["id"]
    path = f"/api/v1/flan/tasks/{task_id}"

    # --- pull the due date BEFORE the stored start → 422 ---
    resp = await client.patch(path, json={"due_date": "2026-03-01"}, headers=headers)
    assert resp.status_code == 422, (
        f"a one-date PATCH inverted the pair over HTTP: status={resp.status_code} "
        f"body={resp.text}"
    )
    assert "must not precede" in resp.text

    # --- push the start date PAST the stored due → 422 (the mirror case) ---
    resp = await client.patch(path, json={"start_date": "2026-03-25"}, headers=headers)
    assert resp.status_code == 422, (
        f"a one-date PATCH inverted the pair over HTTP: status={resp.status_code} "
        f"body={resp.text}"
    )
    assert "must not precede" in resp.text

    # --- the stored row is untouched by either refusal ---
    resp = await client.get(path, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["start_date"] == "2026-03-10"
    assert body["due_date"] == "2026-03-20"

    # --- a one-date PATCH that keeps the order is ordinary work → 200 ---
    resp = await client.patch(path, json={"due_date": "2026-03-31"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["due_date"] == "2026-03-31"
