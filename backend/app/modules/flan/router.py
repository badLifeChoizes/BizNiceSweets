# ABOUTME: FLAN (Project Management) API router — projects, phases, tasks, team
# ABOUTME: roster and assignment: the whole FLAN-01 HTTP surface, 20 operations
# ABOUTME: over 11 paths (project CRUD + archive, phase CRUD, task CRUD, roster
# ABOUTME: CRUD with a soft-remove, two assignee PUTs). Thin:
# ABOUTME: each delegates to flan/service, gates on flan:read (GET) /
# ABOUTME: flan:write (mutations), and writes an audit row AFTER the service commit.
"""
FLAN API router — projects, phases, tasks, team & assignment (FLAN-01).

Endpoints (mount_all in registry.py adds the /api/v1 prefix — full paths are
/api/v1/flan/projects, etc.; this router carries no prefix and spells the
/flan/... path on each route):

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
  DELETE /flan/tasks/{task_id}                 — delete a task, cascading to its tags and
                                                 assignments (flan:write) → 204
  GET    /flan/projects/{project_id}/team      — list the project roster (flan:read)
  POST   /flan/projects/{project_id}/team      — add a team member (flan:write) → 201
  PATCH  /flan/team/{member_id}                — patch a team member (flan:write)
  DELETE /flan/team/{member_id}                — soft-remove a member, clearing its
                                                 assignments (flan:write) → 204
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
  - project.created     on POST   /flan/projects               (target_type="flan_project")
  - project.updated     on PATCH  /flan/projects/{id}          (target_type="flan_project")
  - project.archived    on POST   /flan/projects/{id}/archive  (target_type="flan_project")
  - phase.created       on POST   /flan/projects/{id}/phases   (target_type="flan_phase")
  - phase.updated       on PATCH  /flan/phases/{id}            (target_type="flan_phase")
  - phase.deleted       on DELETE /flan/phases/{id}            (target_type="flan_phase",
    detail names the number of tasks the database cascade took with the phase —
    delete_phase counts them BEFORE the delete precisely so this row can say so;
    it is the only record that deleting one row removed five others)
  - task.created        on POST   /flan/projects/{id}/tasks    (target_type="flan_task",
    detail names the GENERATED key — the client never supplies one, so this row
    is where the `<PREFIX>-<n>` the task will be known by first appears)
  - task.updated        on PATCH  /flan/tasks/{id}             (target_type="flan_task")
  - task.deleted        on DELETE /flan/tasks/{id}             (target_type="flan_task")
  - team_member.created on POST   /flan/projects/{id}/team     (target_type="flan_team_member")
  - team_member.updated on PATCH  /flan/team/{id}              (target_type="flan_team_member")
  - team_member.removed on DELETE /flan/team/{id}              (target_type="flan_team_member",
    detail names how many assignments the soft-remove cleared — remove_member
    returns that count for the same reason delete_phase returns its task count:
    the member row itself survives, so nothing else records what was detached
    from it)
  - task.assignees_set  on PUT    /flan/tasks/{id}/assignees   (target_type="flan_task")
  - phase.assignees_set on PUT    /flan/phases/{id}/assignees  (target_type="flan_phase")
GET routes are read-only and write no audit row.

Three routes make a judgement the service layer deliberately left open — the
project-scoped list endpoints. `list_phases`, `list_tasks` and `list_members`
each return `[]` for an unknown project id rather than raising, so
GET /flan/projects/{project_id}/phases, .../tasks and .../team all call
`get_project_or_404` first. A nonexistent project must not read as "a project
with no phases" — the same distinction GET /flan/projects/{project_id} already
draws. The service keeps its "a list query returns a list" idiom; the HTTP layer
owns the 404.

The two assignee PUTs answer with the stored id list (`AssigneeSet` — the same
shape they accept) rather than with the target row: `set_*_assignees` returns
exactly the ids it read back after the commit, and `PhaseRead` carries no
assignee field at all, so a phase row could not show the caller what was set.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.service import write_audit
from app.modules.flan.schemas import (
    AssigneeSet,
    PhaseCreate,
    PhaseRead,
    PhaseUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    TaskCreate,
    TaskRead,
    TaskUpdate,
    TeamMemberCreate,
    TeamMemberRead,
    TeamMemberUpdate,
)
from app.modules.flan.service import (
    archive_project,
    create_member,
    create_phase,
    create_project,
    create_task,
    delete_phase,
    delete_task,
    get_project,
    get_project_or_404,
    get_task,
    list_members,
    list_phases,
    list_projects,
    list_tasks,
    remove_member,
    set_phase_assignees,
    set_task_assignees,
    update_member,
    update_phase,
    update_project,
    update_task,
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
# Tasks — reads (FLAN-01.3, FLAN-01.5)
# ---------------------------------------------------------------------------


@router.get("/flan/projects/{project_id}/tasks", response_model=list[TaskRead])
async def list_tasks_endpoint(
    project_id: str,
    phase_id: str | None = None,
    assignee_id: str | None = None,
    current_user=Depends(require_permission("flan:read")),
    db: AsyncSession = Depends(get_db),
) -> list[TaskRead]:
    """
    List one project's tasks, each with its tags and assignees.

    Always scoped to a single project (FLAN-01.6 — no view mixes two projects'
    data) and narrowed further by two optional query filters: `phase_id` for one
    phase's list and `assignee_id` for the board's filter-by-assignee
    (FLAN-01.5). Ordered by the NUMERIC suffix of the key, so `PRJ-9` precedes
    `PRJ-10` (keys are unpadded — D-V5P1-7).

    `get_project_or_404` runs first for the same reason it does on the phase
    list: `list_tasks` answers `[]` for an unknown project id, and a nonexistent
    project must not read as a project with no tasks. An archived project's
    tasks are listed normally — archiving refuses writes, not reads. Read-only:
    no audit row. Requires flan:read permission.
    """
    await get_project_or_404(db, project_id)
    return await list_tasks(db, project_id, phase_id=phase_id, assignee_id=assignee_id)


@router.get("/flan/tasks/{task_id}", response_model=TaskRead)
async def get_task_endpoint(
    task_id: str,
    current_user=Depends(require_permission("flan:read")),
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    """
    Read one task with its tags and assignees (404 if it does not exist).

    A task inside an archived project is served exactly like any other —
    archiving is a soft delete that refuses writes, not reads (FLAN-01.1).
    Read-only: no audit row. Requires flan:read permission.
    """
    return await get_task(db, task_id)


# ---------------------------------------------------------------------------
# Tasks — create + mutations (FLAN-01.3)
# ---------------------------------------------------------------------------


@router.post(
    "/flan/projects/{project_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_endpoint(
    project_id: str,
    data: TaskCreate,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    """
    Create a task inside a phase (FLAN-01.3) and return it with its generated key.

    **The key is server-generated** as `<PREFIX>-<n>` from the project's
    key_prefix under a row lock (D-V5P1-2, D-V5P1-7) — `TaskCreate` has no `key`
    field for a caller to fight over. The owning project comes from the phase,
    never from the client.

    The path's `project_id` is passed to the service as its scope argument, so a
    task posted to project A naming a phase of project B is a 422 rather than a
    task silently landing in B. Rejects a missing phase or project (404), an
    archived project (422), `due_date < start_date` (422) and an assignee who is
    not an active member of the project (422). Requires flan:write. Writes a
    task.created audit row — naming the generated key, which appears nowhere
    else in the audit trail — after the create commits.
    """
    task = await create_task(db, data, project_id=project_id)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="task.created",
        target_type="flan_task",
        target_id=str(task.id),
        detail=f"Task created: {task.key} — {task.summary} (phase {task.phase_id})",
    )
    return task


@router.patch("/flan/tasks/{task_id}", response_model=TaskRead)
async def update_task_endpoint(
    task_id: str,
    data: TaskUpdate,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    """
    Apply a partial update to a task (PATCH semantics).

    `key` and `project_id` are immutable and absent from the payload — the key
    is issued once (D-V5P1-2) and the project always follows the phase.
    `phase_id` IS writable: moving a task between phases of the SAME project is
    ordinary work, a move across projects is 422. The date order is re-checked
    over the stored row MERGED with the patch, which is the only place a
    one-date PATCH can be caught. Supplying `tags` or `assignee_ids` REPLACES
    that set. Rejects a missing task (404) and an archived project (422).
    Requires flan:write. Writes a task.updated audit row after the update
    commits.
    """
    task = await update_task(db, task_id, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="task.updated",
        target_type="flan_task",
        target_id=str(task.id),
        detail=f"Task updated: {task.key} (status {task.status})",
    )
    return task


@router.delete("/flan/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_endpoint(
    task_id: str,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a task (FLAN-01.3).

    Its tag and assignee rows go with it in the database (both FKs are
    `ondelete="CASCADE"`), so no orphan survives; the roster members on the
    other side of those assignments are untouched — only the assignment rows go
    (D-V5P1-6). Rejects a missing task (404) and an archived owning project
    (422): archiving freezes everything inside a project, deletions included.
    Requires flan:write. Writes a task.deleted audit row after the delete
    commits.
    """
    await delete_task(db, task_id)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="task.deleted",
        target_type="flan_task",
        target_id=str(task_id),
        detail=f"Task deleted: {task_id}",
    )


# ---------------------------------------------------------------------------
# Team roster — read (FLAN-01.4)
# ---------------------------------------------------------------------------


@router.get("/flan/projects/{project_id}/team", response_model=list[TeamMemberRead])
async def list_members_endpoint(
    project_id: str,
    include_removed: bool = False,
    current_user=Depends(require_permission("flan:read")),
    db: AsyncSession = Depends(get_db),
) -> list[TeamMemberRead]:
    """
    List one project's roster — the pool every assignee is drawn from
    (FLAN-01.4, FLAN-01.5).

    Soft-removed (`active=False`) members are excluded unless
    `include_removed=true` (D-V5P1-6): the row is retained so past references
    still resolve, but a removed member is not on the team and must not appear
    in an assignee picker. Ordered by name, then creation time (two people on
    one roster may share a name, so the timestamp is the stable tiebreak) —
    mirrors the project list.

    `get_project_or_404` runs first so an unknown project id 404s instead of
    reading as an empty roster. An archived project's roster is listed normally.
    Read-only: no audit row. Requires flan:read permission.
    """
    await get_project_or_404(db, project_id)
    return await list_members(db, project_id, include_removed=include_removed)


# ---------------------------------------------------------------------------
# Team roster — create + mutations (FLAN-01.4)
# ---------------------------------------------------------------------------


@router.post(
    "/flan/projects/{project_id}/team",
    response_model=TeamMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_member_endpoint(
    project_id: str,
    data: TeamMemberCreate,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberRead:
    """
    Add a member to a project's roster (FLAN-01.4).

    The roster is per-project, so the owning project comes from the path and
    `TeamMemberCreate` carries no `project_id`. `name` is the only required
    field: a person can be rostered before an email or a platform account
    exists, and an UNLINKED member (`user_id` null) is a full collaborator —
    listed and assignable. A supplied `user_id` must name an existing user (404)
    that no other active member of this project already links (422). Members are
    always created active; removal is its own endpoint. Rejects a missing
    project (404) and an archived one (422). Requires flan:write. Writes a
    team_member.created audit row after the create commits.
    """
    member = await create_member(db, project_id, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="team_member.created",
        target_type="flan_team_member",
        target_id=str(member.id),
        detail=f"Team member added: {member.name} to project {member.project_id}",
    )
    return member


@router.patch("/flan/team/{member_id}", response_model=TeamMemberRead)
async def update_member_endpoint(
    member_id: str,
    data: TeamMemberUpdate,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberRead:
    """
    Apply a partial update to a roster member (PATCH semantics).

    `project_id` and `active` are both absent from the payload: a member belongs
    to one roster for its whole life, and removal is the one endpoint that also
    clears assignments (D-V5P1-6) — a PATCH able to flip `active` on its own
    would leave those rows orphaned. An explicit null `user_id` un-links the
    member; re-sending its own link is a no-op. Rejects a missing member (404),
    an archived project (422) and an unlinkable user (404/422). Requires
    flan:write. Writes a team_member.updated audit row after the update commits.
    """
    member = await update_member(db, member_id, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="team_member.updated",
        target_type="flan_team_member",
        target_id=str(member.id),
        detail=f"Team member updated: {member.name}",
    )
    return member


@router.delete("/flan/team/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member_endpoint(
    member_id: str,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Remove a member from a project's roster — a SOFT remove (D-V5P1-6).

    The row survives with `active=False`, keeping its name, role, email, colour,
    rate and user link so every past reference still resolves (FLAN-01.4); what
    goes is the member's task and phase assignment rows, deleted in the same
    transaction. `remove_member` returns how many that was and the audit detail
    NAMES it: the member row is still there, so this row is the only record that
    removing one person detached them from N pieces of work. The tasks
    themselves are untouched.

    Idempotent — removing an already-removed member is a no-op that clears 0.
    Rejects a missing member (404) and an archived project (422). Requires
    flan:write. Writes a team_member.removed audit row after the removal
    commits.
    """
    cleared = await remove_member(db, member_id)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="team_member.removed",
        target_type="flan_team_member",
        target_id=str(member_id),
        detail=f"Team member removed: {member_id} ({cleared} assignment(s) cleared)",
    )


# ---------------------------------------------------------------------------
# Assignment — full-replacement assignee set (FLAN-01.5)
# ---------------------------------------------------------------------------


@router.put("/flan/tasks/{task_id}/assignees", response_model=AssigneeSet)
async def set_task_assignees_endpoint(
    task_id: str,
    data: AssigneeSet,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> AssigneeSet:
    """
    Replace a task's assignee set (FLAN-01.5).

    A PUT, not a PATCH: `member_ids` is the COMPLETE list the task carries
    afterwards, and `[]` is valid — that is how assignments are cleared. Every
    id must name an ACTIVE member of the task's OWN project (422 naming the
    offending one), which is what makes "assignees drawn from the project
    roster" enforced rather than conventional. Re-sending the same list is
    idempotent, and no roster member row is ever touched — clearing an
    assignment must never delete a member.

    Answers with the ids read back after the commit, in the same shape the
    payload takes, so the response equals a subsequent GET. Rejects a missing
    task (404) and an archived project (422). Requires flan:write. Writes a
    task.assignees_set audit row after the replacement commits.
    """
    member_ids = await set_task_assignees(db, task_id, data.member_ids)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="task.assignees_set",
        target_type="flan_task",
        target_id=str(task_id),
        detail=f"Task assignees set: {task_id} now has {len(member_ids)} assignee(s)",
    )
    return AssigneeSet(member_ids=member_ids)


@router.put("/flan/phases/{phase_id}/assignees", response_model=AssigneeSet)
async def set_phase_assignees_endpoint(
    phase_id: str,
    data: AssigneeSet,
    current_user=Depends(require_permission("flan:write")),
    db: AsyncSession = Depends(get_db),
) -> AssigneeSet:
    """
    Replace a phase's assignee set (FLAN-01.5).

    Identical contract to the task route, against `flan_phase_assignee`: full
    replacement, `[]` clears, the repeat write is idempotent, and every id must
    be an ACTIVE member of the phase's own project (422 naming it). A phase
    carries assignees in its OWN right — a phase lead is not derived from the
    assignees of its tasks, unlike the phase's dates and % complete (D-V5-1),
    and this route reads and writes no task.

    Rejects a missing phase (404) and an archived project (422). Requires
    flan:write. Writes a phase.assignees_set audit row after the replacement
    commits.
    """
    member_ids = await set_phase_assignees(db, phase_id, data.member_ids)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="phase.assignees_set",
        target_type="flan_phase",
        target_id=str(phase_id),
        detail=f"Phase assignees set: {phase_id} now has {len(member_ids)} assignee(s)",
    )
    return AssigneeSet(member_ids=member_ids)
