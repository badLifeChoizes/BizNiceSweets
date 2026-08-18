# ABOUTME: FLAN (Project Management) API router — projects, phases, tasks, team
# ABOUTME: roster and assignment. Task 17 landed the project and phase routes
# ABOUTME: (list/create/read/patch/archive a project; list/create/patch/delete a
# ABOUTME: phase); the task, roster and assignment routes land in Task 18. Thin:
# ABOUTME: each delegates to flan/service, gates on flan:read (GET) /
# ABOUTME: flan:write (mutations), and writes an audit row AFTER the service commit.
"""
FLAN API router — projects, phases, tasks, team & assignment (FLAN-01).

Endpoints (mount_all in registry.py adds the /api/v1 prefix — full paths are
/api/v1/flan/projects, etc.; this router carries no prefix and spells the
/flan/... path on each route). The first eight are implemented here; the rest
land in Task 18 below the banner at the foot of this module:

  GET    /flan/projects                        — list projects (flan:read)
  POST   /flan/projects                        — create a project (flan:write) → 201
  GET    /flan/projects/{project_id}           — read one project (flan:read)
  PATCH  /flan/projects/{project_id}           — patch a project (flan:write)
  POST   /flan/projects/{project_id}/archive   — soft-archive a project (flan:write)
  GET    /flan/projects/{project_id}/phases    — list a project's phases (flan:read)
  POST   /flan/projects/{project_id}/phases    — create a phase (flan:write) → 201
  PATCH  /flan/phases/{phase_id}               — patch a phase (flan:write)
  DELETE /flan/phases/{phase_id}               — delete a phase, cascading to its tasks (flan:write) → 204
  GET    /flan/projects/{project_id}/tasks     — list tasks (phase_id/assignee_id filters, flan:read)
  POST   /flan/projects/{project_id}/tasks     — create a task (flan:write) → 201
  GET    /flan/tasks/{task_id}                 — read one task (flan:read)
  PATCH  /flan/tasks/{task_id}                 — patch a task (flan:write)
  DELETE /flan/tasks/{task_id}                 — delete a task (flan:write)
  GET    /flan/projects/{project_id}/team      — list the project roster (flan:read)
  POST   /flan/projects/{project_id}/team      — add a team member (flan:write) → 201
  PATCH  /flan/team/{member_id}                — patch a team member (flan:write)
  DELETE /flan/team/{member_id}                — remove a member, clearing assignments (flan:write)
  PUT    /flan/tasks/{task_id}/assignees       — set a task's assignees (flan:write)
  PUT    /flan/phases/{phase_id}/assignees     — set a phase's assignees (flan:write)

Permission gating (D-P10-6, mirrors the GELATO/MOUSSE routers):
  - Every mutation (POST/PATCH/PUT/DELETE) requires flan:write; every read (GET)
    requires flan:read. Unauthenticated → 401, wrong permission → 403 (admin is
    wildcard, handled inside require_permission).

Audit logging (D-10): every mutation writes one AuditLog row AFTER the service's
own commit (write_audit self-commits, mirroring the SYERP/GELATO router order).
Every target_id is passed through `str(...)` explicitly — FLAN's primary keys are
uuid strings, but the GELATO int-PK lesson (136e98d) is that this gets assumed
rather than checked. Implemented here:
  - project.created  on POST   /flan/projects                      (target_type="flan_project")
  - project.updated  on PATCH  /flan/projects/{id}                 (target_type="flan_project")
  - project.archived on POST   /flan/projects/{id}/archive         (target_type="flan_project")
  - phase.created    on POST   /flan/projects/{id}/phases          (target_type="flan_phase")
  - phase.updated    on PATCH  /flan/phases/{id}                   (target_type="flan_phase")
  - phase.deleted    on DELETE /flan/phases/{id}                   (target_type="flan_phase",
    detail names the number of tasks the database cascade took with the phase —
    delete_phase counts them BEFORE the delete precisely so this row can say so;
    it is the only record that deleting one row removed five others)
Task 18 adds task.created / task.updated / task.deleted, team_member.created /
team_member.updated / team_member.removed, task.assignees_set and
phase.assignees_set. GET routes are read-only and write no audit row.

One route makes a judgement the service layer deliberately left open:
`list_phases` returns `[]` for an unknown project id rather than raising, so
GET /flan/projects/{project_id}/phases calls `get_project_or_404` first. A
nonexistent project must not read as "a project with no phases" — the same
distinction GET /flan/projects/{project_id} already draws. The service keeps its
"a list query returns a list" idiom; the HTTP layer owns the 404.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.service import write_audit
from app.modules.flan.schemas import (
    PhaseCreate,
    PhaseRead,
    PhaseUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)
from app.modules.flan.service import (
    archive_project,
    create_phase,
    create_project,
    delete_phase,
    get_project,
    get_project_or_404,
    list_phases,
    list_projects,
    update_phase,
    update_project,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Projects — reads (FLAN-01.1, FLAN-01.6)
# ---------------------------------------------------------------------------


@router.get("/flan/projects", response_model=list[ProjectRead])
async def list_projects_endpoint(
    include_archived: bool = False,
    current_user=Depends(require_permission("flan:read")),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectRead]:
    """
    List the projects the module switcher offers (FLAN-01.6), each with its tags.

    Archived (active=False) projects are excluded unless `include_archived=true`
    — an archived project is retained and fully readable, it is simply not part
    of the day-to-day list. Ordered by name, then creation time (duplicate names
    are allowed, so the timestamp is the stable tiebreak). Read-only: no audit
    row. Requires flan:read permission.
    """
    return await list_projects(db, include_archived=include_archived)


@router.get("/flan/projects/{project_id}", response_model=ProjectRead)
async def get_project_endpoint(
    project_id: str,
    current_user=Depends(require_permission("flan:read")),
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    """
    Read one project with its tag list (404 if it does not exist).

    An archived project is served exactly like a live one — archiving is a soft
    delete that refuses writes, not a read (FLAN-01.1). Read-only: no audit row.
    Requires flan:read permission.
    """
    return await get_project(db, project_id)


# ---------------------------------------------------------------------------
# Projects — create + mutations (FLAN-01.1)
# ---------------------------------------------------------------------------


@router.post(
    "/flan/projects",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_endpoint(
    data: ProjectCreate,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    """
    Create a project (FLAN-01.1) and its tag rows in one transaction.

    `key_prefix` is taken verbatim when supplied and otherwise derived from the
    name (D-V5P1-2). Duplicate names are allowed by design, so nothing here
    rejects one. Requires flan:write. Writes a project.created audit row after
    the create commits.
    """
    project = await create_project(db, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="project.created",
        target_type="flan_project",
        target_id=str(project.id),
        detail=f"Project created: {project.name} (key prefix {project.key_prefix})",
    )
    return project


@router.patch("/flan/projects/{project_id}", response_model=ProjectRead)
async def update_project_endpoint(
    project_id: str,
    data: ProjectUpdate,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    """
    Apply a partial update to a project (PATCH semantics).

    Only the supplied fields are written; `id` is immutable and `active` belongs
    to the archive route, so neither appears in the payload. `key_prefix` is
    refused with a 422 once the project has any task (D-V5P1-2). Supplying
    `tags` REPLACES the project's tag set. Rejects a missing project (404) and
    an archived one (422). Requires flan:write. Writes a project.updated audit
    row after the update commits.
    """
    project = await update_project(db, project_id, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="project.updated",
        target_type="flan_project",
        target_id=str(project.id),
        detail=f"Project updated: {project.name}",
    )
    return project


@router.post("/flan/projects/{project_id}/archive", response_model=ProjectRead)
async def archive_project_endpoint(
    project_id: str,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> ProjectRead:
    """
    Soft-archive a project (active=False) — it keeps every field and stays
    readable, but every write inside it is refused from now on: phase, task,
    roster and assignment writes included (FLAN-01.1).

    Idempotent — archiving an already-archived project is a no-op that returns
    the row. Rejects a missing project (404). Requires flan:write. Writes a
    project.archived audit row after the archive commits.
    """
    project = await archive_project(db, project_id)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="project.archived",
        target_type="flan_project",
        target_id=str(project.id),
        detail=f"Project archived: {project.name}",
    )
    return project


# ---------------------------------------------------------------------------
# Phases — read (FLAN-01.2, D-V5-1)
# ---------------------------------------------------------------------------


@router.get("/flan/projects/{project_id}/phases", response_model=list[PhaseRead])
async def list_phases_endpoint(
    project_id: str,
    current_user=Depends(require_permission("flan:read")),
    db: AsyncSession = Depends(get_db),
) -> list[PhaseRead]:
    """
    List one project's phases in display order, each with its derived rollup.

    The dates, percentage and task counts are computed per read from the phase's
    tasks and stored in no column (D-V5-1). An archived project's phases are
    listed normally — archiving refuses writes, not reads.

    `get_project_or_404` runs first so an unknown project id 404s instead of
    reading as an empty phase list: `list_phases` returns `[]` for both cases and
    only the HTTP layer can tell "no such project" from "no phases yet".
    Read-only: no audit row. Requires flan:read permission.
    """
    await get_project_or_404(db, project_id)
    return await list_phases(db, project_id)


# ---------------------------------------------------------------------------
# Phases — create + mutations (FLAN-01.2)
# ---------------------------------------------------------------------------


@router.post(
    "/flan/projects/{project_id}/phases",
    response_model=PhaseRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_phase_endpoint(
    project_id: str,
    data: PhaseCreate,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> PhaseRead:
    """
    Create a phase inside a project (FLAN-01.2).

    The owning project comes from the path — `PhaseCreate` carries no
    `project_id`, so a phase cannot be pointed at a project it was not posted
    to. The new phase comes back with the rollup of an empty phase: no derived
    dates, "0.00" complete. Rejects a missing project (404) and an archived one
    (422). Requires flan:write. Writes a phase.created audit row after the
    create commits.
    """
    phase = await create_phase(db, project_id, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="phase.created",
        target_type="flan_phase",
        target_id=str(phase.id),
        detail=f"Phase created: {phase.name} in project {phase.project_id}",
    )
    return phase


@router.patch("/flan/phases/{phase_id}", response_model=PhaseRead)
async def update_phase_endpoint(
    phase_id: str,
    data: PhaseUpdate,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> PhaseRead:
    """
    Apply a partial update to a phase (PATCH name/sort_order/status/description).

    Those four are the only writable fields, structurally: `PhaseUpdate` has no
    date and no percent field at all, because a phase's dates and % complete are
    derived from its tasks on every read (D-V5-1). Rejects a missing phase (404)
    and an archived owning project (422). Requires flan:write. Writes a
    phase.updated audit row after the update commits.
    """
    phase = await update_phase(db, phase_id, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="phase.updated",
        target_type="flan_phase",
        target_id=str(phase.id),
        detail=f"Phase updated: {phase.name} (status {phase.status})",
    )
    return phase


@router.delete("/flan/phases/{phase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phase_endpoint(
    phase_id: str,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a phase and, with it, its tasks (FLAN-01.2).

    The cascade is the database's (`flan_task.phase_id` is ondelete="CASCADE"),
    so the phase's tasks — and transitively their tag and assignee rows — go in
    the same statement. `delete_phase` counts those tasks BEFORE the delete and
    returns the count so the audit detail can NAME it: that row is the only
    record that removing one phase removed five tasks. Rejects a missing phase
    (404) and an archived owning project (422). Requires flan:write. Writes a
    phase.deleted audit row after the delete commits.
    """
    task_count = await delete_phase(db, phase_id)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="phase.deleted",
        target_type="flan_phase",
        target_id=str(phase_id),
        detail=f"Phase deleted: {phase_id} (cascaded to {task_count} task(s))",
    )


# ---------------------------------------------------------------------------
# Task 18 inserts here: tasks (FLAN-01.3), team roster (FLAN-01.4) and
# assignment (FLAN-01.5) routes — same shape as above (thin delegation,
# flan:read / flan:write gating, write_audit AFTER the service returns).
# ---------------------------------------------------------------------------
