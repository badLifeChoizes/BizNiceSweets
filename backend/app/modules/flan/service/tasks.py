# ABOUTME: FLAN task CRUD (FLAN-01.3) — list, read, create, patch and delete the
# ABOUTME: units of work inside a phase, each carrying its opaque tag set and its
# ABOUTME: roster assignees (D-V5P1-5, FLAN-01.5). Holds the three task rules:
# ABOUTME: the key is server-generated under a row lock with a NARROW, BOUNDED
# ABOUTME: retry, project_id comes from the phase, and due < start is refused
# ABOUTME: over the MERGED values of a PATCH, not just over the payload.
"""FLAN tasks service (business logic).

A task belongs to exactly one phase and therefore to exactly one project
(FLAN-01.3). It is addressed by its own id once created
(PATCH/DELETE /flan/tasks/{task_id}), so the owning project is read off the row
via `resolve_task` rather than taken from the caller.

Five rules are load-bearing here:

  * **`project_id` comes from the phase, never from the client.** `TaskCreate`
    has no `project_id` field at all and `create_task` sets it from
    `phase.project_id`, so a task can never claim a project its phase does not
    belong to — which is what makes `uq_flan_task_project_key` mean what it
    says. A move between phases of the SAME project is allowed; a cross-project
    move is 422 (`update_task`).
  * **The key-collision retry is NARROW and BOUNDED.** The insert is retried at
    most `_MAX_KEY_ATTEMPTS` times and only when the `IntegrityError` is
    provably a violation of `uq_flan_task_project_key`; every other integrity
    failure is re-raised untouched. A task insert also carries a `phase_id` FK
    (and its assignee links carry a `member_id` FK), so a broad
    `except IntegrityError → retry` here is precisely the Phase-13
    `create_invoice` defect: it copied a broad handler from an exemplar that had
    no FK, misread an FK failure as a number collision, and recursed until it
    500'd. A create against a deleted phase must 404 promptly — it does, before
    the loop is ever entered.
  * **`due < start` is re-checked over the MERGED values on PATCH.** The schema
    validator (`schemas.py::_check_date_order`) sees only what the payload
    carries, so a PATCH that moves *one* of the two dates passes it by
    construction. `update_task` merges the patch onto the stored row and checks
    the pair, which is the only place that case can be caught. `due == start` is
    a valid zero-duration milestone and passes everywhere.
  * **Tags and assignees round-trip** (D-V5P1-5, FLAN-01.5). Both live in join
    tables (`flan_task_tag`, `flan_task_assignee`), not in columns and not in ORM
    relationships, so every function here attaches the loaded lists to the
    returned instance as `.tags` / `.assignee_ids` — that is what `TaskRead`
    reads via `from_attributes`. `create_task` and `update_task` **apply** both,
    because a service that accepted them over the wire and silently dropped them
    would be green on the backend and dead through the UI. Mirrors
    `projects.py::_attach_tags`.
  * **Every assignee must be an ACTIVE member of the SAME project**
    (`require_project_members`, 422 naming the offending id). That guard is
    deliberately public: `assignments.py` (Task 16) sets task *and* phase
    assignee sets against the same rule and should import it rather than restate
    it. Promote it to `_common.py` if a third caller appears.

`list_tasks` orders on the **numeric suffix** of the key, never on the raw
string: keys are unpadded (D-V5P1-7), so a lexicographic sort puts `PRJ-10`
before `PRJ-9`. See `_key_number` — `keys.py` names this module as the owner of
that rule.

Every mutation calls `require_writable_project` first: archiving a project
freezes everything inside it, tasks included (422).

Audit events are written at the router layer after the service commits (house
idiom — gelato/router.py), never here. Models are imported lazily inside each
function (house idiom — service/_common.py, crumb/service/leads.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import Numeric, cast, delete, func, select

from app.modules.flan.service._common import (
    require_writable_project,
    resolve_phase,
    resolve_task,
)
from app.modules.flan.service.keys import generate_task_key

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement

    from app.modules.flan.models import Task
    from app.modules.flan.schemas import TaskCreate, TaskUpdate


#: The unique constraint that makes a task key unique within its project
#: (models.py::Task). The ONLY integrity failure `create_task` retries on.
TASK_KEY_CONSTRAINT = "uq_flan_task_project_key"

#: How many times `create_task` re-generates a key and re-inserts before giving
#: up with a 409. Bounded, not recursive: the lock plus the generator make even
#: one collision unlikely, and an unbounded retry on a mis-classified error is
#: the Phase-13 `create_invoice` 500.
_MAX_KEY_ATTEMPTS = 3

#: Task columns that are NOT NULL: a PATCH carrying an explicit null for one of
#: these is ignored rather than being sent to the database as a constraint
#: violation. `start_date`/`due_date` are the nullable ones, so an explicit null
#: there legitimately clears the date. Mirrors projects.py::_NOT_NULL_FIELDS.
_NOT_NULL_FIELDS = frozenset({"phase_id", "summary", "status", "risk_level", "pinned"})


# ---------------------------------------------------------------------------
# Key-collision detection — NARROW by construction
# ---------------------------------------------------------------------------


def _is_task_key_collision(exc: Exception) -> bool:
    """
    Is this IntegrityError provably a collision on `uq_flan_task_project_key`,
    and nothing else?

    SQLAlchemy's asyncpg dialect wraps the driver error twice, so the constraint
    name is read first from `exc.orig.__cause__.constraint_name` and only then
    from the message text; both paths require the constraint to be named
    explicitly, so no other integrity failure can be reported as a key
    collision. Mirrors `auth/service.py::_is_duplicate_email_violation`.

    This narrowing is the whole point of the retry loop below. `flan_task`
    carries a `phase_id` FK into `flan_phase` and a `project_id` FK into
    `flan_project`, and its assignee rows carry a `member_id` FK — a broad
    `except IntegrityError → retry` would keep re-issuing a create against a
    deleted phase until it exhausted its attempts (or, recursively, the stack:
    the Phase-13 `create_invoice` 500).
    """
    orig = getattr(exc, "orig", None)
    cause = getattr(orig, "__cause__", None)
    if getattr(cause, "constraint_name", None) == TASK_KEY_CONSTRAINT:
        return True
    return TASK_KEY_CONSTRAINT in str(orig)


# ---------------------------------------------------------------------------
# Date order — the check the schema structurally cannot make (FLAN-01.3)
# ---------------------------------------------------------------------------


def _require_date_order(start: date | None, due: date | None) -> None:
    """
    Refuse a task whose due date precedes its start date (422).

    `due == start` is a **valid zero-duration milestone** and passes; only
    `due < start` raises, and either date being None is fine.

    Callers pass the MERGED values — the stored row overlaid with the patch —
    which is why this exists alongside the identical schema validator: a PATCH
    that moves only `start_date` carries no `due_date` for the schema to compare
    it against, so `schemas.py::_check_date_order` passes it by construction.
    """
    if start is not None and due is not None and due < start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"due_date ({due}) must not precede start_date ({start}); "
                "due_date == start_date is a valid zero-duration milestone."
            ),
        )


# ---------------------------------------------------------------------------
# Roster membership — the assignee guard shared with assignments.py (FLAN-01.5)
# ---------------------------------------------------------------------------


async def require_project_members(
    db: AsyncSession, project_id: str, member_ids: Sequence[str]
) -> None:
    """
    Assert every id names an ACTIVE member of THIS project's roster (FLAN-01.5).

    Raises HTTP 422 naming the offending id when one is unknown, belongs to
    another project's roster, or has been soft-removed (`active=False`). An
    empty list is valid and checks nothing — zero assignees is a legitimate
    state.

    This is what makes "assignees drawn from the project roster" enforced rather
    than conventional: `flan_task_assignee.member_id` FKs into
    `flan_team_member` but the database cannot know the member must be on the
    *same* project as the task, nor that a removed member may not be assigned.

    **Public on purpose.** `assignments.py` (Task 16) applies the identical rule
    to `set_task_assignees` / `set_phase_assignees` and should import this
    rather than restate it — one rule, one message, one place to change. One
    query for the whole batch, never one per id.
    """
    from app.modules.flan.models import TeamMember

    if not member_ids:
        return

    result = await db.execute(
        select(TeamMember.id, TeamMember.project_id, TeamMember.active).where(
            TeamMember.id.in_(list(member_ids))
        )
    )
    found = {row[0]: (row[1], row[2]) for row in result.all()}

    for member_id in member_ids:
        row = found.get(member_id)
        if row is None or row[0] != project_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Member {member_id} is not on project {project_id}'s roster."
                ),
            )
        if not row[1]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Member {member_id} has been removed from project "
                    f"{project_id}'s roster and cannot be assigned."
                ),
            )


# ---------------------------------------------------------------------------
# Tags and assignees — the join tables (D-V5P1-5, FLAN-01.5)
# ---------------------------------------------------------------------------


async def _load_tags(db: AsyncSession, task_ids: Sequence[str]) -> dict[str, list[str]]:
    """
    Load the tag sets for a batch of tasks in ONE query.

    Returns a dict keyed by task id; **every requested id is present**, an id
    with no tag rows mapping to an empty list, so a caller can index it without
    a fallback. Tags come back sorted, since a join table has no inherent order
    and a stable list makes the API response deterministic. Mirrors
    `projects.py::_load_tags`.
    """
    from app.modules.flan.models import TaskTag

    tags: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    if not tags:
        return tags

    result = await db.execute(
        select(TaskTag.task_id, TaskTag.tag)
        .where(TaskTag.task_id.in_(list(tags)))
        .order_by(TaskTag.tag)
    )
    for task_id, tag in result.all():
        tags[task_id].append(tag)
    return tags


async def _load_assignees(db: AsyncSession, task_ids: Sequence[str]) -> dict[str, list[str]]:
    """
    Load the assignee sets for a batch of tasks in ONE query.

    Same contract as `_load_tags`: every requested id is a key of the result, an
    unassigned task mapping to an empty list. Ordered by member id so the list a
    caller sees is stable between reads — `flan_task_assignee` is a composite-PK
    join table with no inherent order.
    """
    from app.modules.flan.models import TaskAssignee

    assignees: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    if not assignees:
        return assignees

    result = await db.execute(
        select(TaskAssignee.task_id, TaskAssignee.member_id)
        .where(TaskAssignee.task_id.in_(list(assignees)))
        .order_by(TaskAssignee.member_id)
    )
    for task_id, member_id in result.all():
        assignees[task_id].append(member_id)
    return assignees


async def _attach_related(db: AsyncSession, tasks: Sequence[Task]) -> None:
    """
    Attach each task's tag list and assignee list to the ORM instance as plain
    `.tags` / `.assignee_ids` attributes, in place — two batched queries for the
    whole list, never one per task.

    Neither join table has an ORM relationship behind it, so nothing populates
    these on their own: `TaskRead` declares both as service-filled fields and
    reads them off the instance through `from_attributes`. **Every function in
    this module that returns a task calls this**, so tags and assignees can
    never be accepted on the way in and silently dropped on the way out — the
    guarantee `projects.py::_attach_tags` gives the project tag list. The
    attributes are not mapped, so they survive `commit()`/`refresh()` untouched.
    """
    task_ids = [task.id for task in tasks]
    tags = await _load_tags(db, task_ids)
    assignees = await _load_assignees(db, task_ids)
    for task in tasks:
        task.tags = tags[task.id]  # type: ignore[attr-defined]
        task.assignee_ids = assignees[task.id]  # type: ignore[attr-defined]


async def _replace_tags(db: AsyncSession, task_id: str, tags: Iterable[str]) -> None:
    """
    Replace a task's whole tag set (D-V5P1-5) — flushed, not committed.

    Full-replacement semantics: the supplied list is the task's complete tag set
    after the call, so the existing rows are deleted first, and an empty list
    clears every tag. The caller decides whether the change commits, so tag
    writes ride in the same transaction as the task write that carried them.

    Tags arrive already stripped, non-blank and de-duplicated from the schema
    (`_normalize_tags`), which is what keeps the composite PK `(task_id, tag)`
    from colliding on a payload naming the same tag twice.
    """
    from app.modules.flan.models import TaskTag

    await db.execute(delete(TaskTag).where(TaskTag.task_id == task_id))
    for tag in tags:
        db.add(TaskTag(task_id=task_id, tag=tag))
    await db.flush()


async def _replace_assignees(db: AsyncSession, task_id: str, member_ids: Iterable[str]) -> None:
    """
    Replace a task's whole assignee set (FLAN-01.5) — flushed, not committed.

    Same full-replacement semantics as `_replace_tags`: the supplied list is the
    task's complete assignee list afterwards and an empty list clears the
    assignment rows. Ids arrive de-duplicated from the schema
    (`_normalize_member_ids`), so the composite PK `(task_id, member_id)` cannot
    collide on a payload naming the same member twice.

    **Validate with `require_project_members` BEFORE calling this** — this
    function writes rows and does not judge them.
    """
    from app.modules.flan.models import TaskAssignee

    await db.execute(delete(TaskAssignee).where(TaskAssignee.task_id == task_id))
    for member_id in member_ids:
        db.add(TaskAssignee(task_id=task_id, member_id=member_id))
    await db.flush()


# ---------------------------------------------------------------------------
# Ordering — the numeric suffix, never the raw string (D-V5P1-7)
# ---------------------------------------------------------------------------


def _key_number() -> ColumnElement[object]:
    """
    The task key's trailing digits as a number, for ORDER BY.

    Task keys are **unpadded** (D-V5P1-7), so a plain string sort puts `PRJ-10`
    before `PRJ-9`; `keys.py` names `list_tasks` as the owner of ordering on the
    numeric suffix instead. `substring(key, '[0-9]+$')` returns NULL for a key
    with no trailing digits (a hand-edited `PRJ-DRAFT`) rather than throwing,
    and the cast target is **`Numeric`, never `Integer`** for the same reason it
    is in `keys.py`: `PRJ-9999999999` is a legal 20-character key whose suffix
    overflows `int4`, and an `Integer` cast would 500 every list in that project
    permanently (the PLUM-01 defect `7562a02`, D-P8-6).
    """
    from app.modules.flan.models import Task

    return cast(func.substring(Task.key, "[0-9]+$"), Numeric)


# ---------------------------------------------------------------------------
# CRUD (FLAN-01.3)
# ---------------------------------------------------------------------------


async def list_tasks(
    db: AsyncSession,
    project_id: str,
    phase_id: str | None = None,
    assignee_id: str | None = None,
) -> list[Task]:
    """
    Return one project's tasks, each with its tags and assignees attached.

    Scoped to a single project always (FLAN-01.6 — no view mixes two projects'
    data) and narrowed further by the two optional filters: `phase_id` for a
    single phase's list, and `assignee_id` for the board's filter-by-assignee
    (FLAN-01.5). The assignee filter is an `IN (SELECT ...)` over
    `flan_task_assignee` rather than a join, so a task cannot appear twice.

    **Ordered by the NUMERIC suffix of the key** (`_key_number`), with the raw
    key as a tiebreak for any hand-edited non-numeric key (which sorts last).
    Keys are unpadded (D-V5P1-7), so ordering on the string would list `PRJ-10`
    before `PRJ-9`.

    Three queries in total regardless of how many tasks come back: one for the
    rows, one batched tag load, one batched assignee load.

    This is a read, so it does not care whether the project is archived — an
    archived project retains all its data and stays fully readable (FLAN-01.1).
    """
    from app.modules.flan.models import Task, TaskAssignee

    stmt = select(Task).where(Task.project_id == project_id)
    if phase_id is not None:
        stmt = stmt.where(Task.phase_id == phase_id)
    if assignee_id is not None:
        stmt = stmt.where(
            Task.id.in_(
                select(TaskAssignee.task_id).where(TaskAssignee.member_id == assignee_id)
            )
        )
    stmt = stmt.order_by(_key_number().asc().nulls_last(), Task.key.asc())

    result = await db.execute(stmt)
    tasks = list(result.scalars().all())
    await _attach_related(db, tasks)
    return tasks


async def get_task(db: AsyncSession, task_id: str) -> Task:
    """
    Load one task by id, with its tags and assignees attached. Raises HTTP 404
    if it does not exist.

    This is the read path, so it deliberately does **not** care whether the
    owning project is archived: archiving is a soft delete and an archived
    project keeps all its data and stays readable (FLAN-01.1). Only writes are
    refused, by `require_writable_project`.
    """
    task, _project_id = await resolve_task(db, task_id)
    await _attach_related(db, [task])
    return task


async def create_task(
    db: AsyncSession, data: TaskCreate, project_id: str | None = None
) -> Task:
    """
    Create a task inside a phase (FLAN-01.3) and return it.

    **The owning project comes from the phase, never from the client.**
    `TaskCreate` carries no `project_id` field and `Task.project_id` is set from
    `phase.project_id`, so the denormalized column that backs
    `uq_flan_task_project_key` can never disagree with the tree. `project_id` is
    an optional *scope* argument for the route's path segment
    (`POST /flan/projects/{project_id}/tasks`): when supplied it must match the
    phase's owning project, and a mismatch is 422 rather than a task silently
    landing in the other project.

    Order of operations, each part load-bearing:

      1. resolve the phase (404 if it is gone — **before** any retry loop, so a
         create against a deleted phase fails immediately and cheaply);
      2. `require_writable_project` (404 / 422-if-archived);
      3. validate every assignee is an active member of that project (422);
      4. `SELECT ... FOR UPDATE` the project row, generate the key
         (`generate_task_key`, numeric-safe — D-P8-6) and insert, at most
         `_MAX_KEY_ATTEMPTS` times;
      5. write the tag and assignee rows, then ONE commit — so a task can never
         land tagless or unassigned because a join-table insert failed.

    **The retry is narrow and bounded.** It catches an `IntegrityError` only
    when `_is_task_key_collision` proves the violated constraint is
    `uq_flan_task_project_key`, and re-raises anything else untouched: this
    insert carries two FKs, and a broad handler here is the Phase-13
    `create_invoice` defect that misread an FK failure as a number collision and
    recursed to a 500. Exhausting the attempts is a 409, not a hang.

    `data.assignee_ids` and `data.tags` are APPLIED, not merely accepted — a
    service that took them over the wire and dropped them would be green in
    tests and dead through the UI.
    """
    import sqlalchemy.exc

    from app.modules.flan.models import Project, Task

    _phase, phase_project_id = await resolve_phase(db, data.phase_id)
    if project_id is not None and project_id != phase_project_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Phase {data.phase_id} belongs to project {phase_project_id}, "
                f"not to project {project_id}."
            ),
        )
    await require_writable_project(db, phase_project_id)
    await require_project_members(db, phase_project_id, data.assignee_ids)

    for attempt in range(1, _MAX_KEY_ATTEMPTS + 1):
        # Lock the project row for the read-generate-insert window, and read the
        # prefix off the locked row (never off a stale instance: a previous
        # attempt's rollback expired it).
        locked = await db.execute(
            select(Project).where(Project.id == phase_project_id).with_for_update()
        )
        key_prefix = locked.scalar_one().key_prefix
        key = await generate_task_key(db, phase_project_id, key_prefix)

        task = Task(
            phase_id=data.phase_id,
            project_id=phase_project_id,
            key=key,
            summary=data.summary,
            status=data.status,
            risk_level=data.risk_level,
            start_date=data.start_date,
            due_date=data.due_date,
            pinned=data.pinned,
        )
        db.add(task)
        try:
            await db.flush()
        except sqlalchemy.exc.IntegrityError as exc:
            # A failed flush poisons the session, so roll back before deciding
            # (mirrors auth.create_user). Then retry ONLY a proven key collision.
            await db.rollback()
            if not _is_task_key_collision(exc):
                raise
            if attempt == _MAX_KEY_ATTEMPTS:
                break
            continue

        await _replace_tags(db, task.id, data.tags)
        await _replace_assignees(db, task.id, data.assignee_ids)
        await db.commit()
        await db.refresh(task)
        await _attach_related(db, [task])
        return task

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Could not allocate a unique task key for project {phase_project_id} "
            f"after {_MAX_KEY_ATTEMPTS} attempts; please retry."
        ),
    )


async def update_task(db: AsyncSession, task_id: str, data: TaskUpdate) -> Task:
    """
    Apply a partial update to a task (PATCH semantics) and return it.

    Resolves the task (404) and then requires its owning project to be writable
    (422 if archived).

    **`key` and `project_id` are immutable**, and structurally so: `TaskUpdate`
    carries neither field, the key is issued once under the project's prefix
    (D-V5P1-2) and the project always follows the phase. `phase_id` IS writable
    — moving a task to another phase of the SAME project is ordinary work — but
    a move to a phase of a DIFFERENT project is 422: it would change the task's
    project, and with it the scope its key is unique in.

    **The date order is re-checked over the MERGED values** — the stored row
    overlaid with the patch — because a PATCH that moves only `start_date`
    carries no `due_date` for the schema validator to compare it against and
    passes it by construction. That merged check is the only place the
    move-one-date case can be caught, so it is load-bearing rather than
    belt-and-braces. `due == start` remains a valid milestone.

    Only the fields the payload actually SET are written (`exclude_unset`), so
    an omitted field is untouched and an explicit null clears a date; an
    explicit null aimed at a NOT NULL column is ignored rather than turned into
    a database error (mirrors update_project). Supplying `tags` or
    `assignee_ids` REPLACES that whole set; omitting them (or sending null)
    leaves the existing set alone.
    """
    task, project_id = await resolve_task(db, task_id)
    await require_writable_project(db, project_id)

    patch = data.model_dump(exclude_unset=True)
    tags = patch.pop("tags", None)
    assignee_ids = patch.pop("assignee_ids", None)

    new_phase_id = patch.get("phase_id")
    if new_phase_id is not None and new_phase_id != task.phase_id:
        _phase, target_project_id = await resolve_phase(db, new_phase_id)
        if target_project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Task {task_id} cannot be moved to phase {new_phase_id}: it "
                    f"belongs to project {target_project_id}, not to project "
                    f"{project_id}."
                ),
            )

    merged_start = patch["start_date"] if "start_date" in patch else task.start_date
    merged_due = patch["due_date"] if "due_date" in patch else task.due_date
    _require_date_order(merged_start, merged_due)

    if assignee_ids is not None:
        await require_project_members(db, project_id, assignee_ids)

    for field, value in patch.items():
        if value is None and field in _NOT_NULL_FIELDS:
            continue
        setattr(task, field, value)

    if tags is not None:
        await _replace_tags(db, task.id, tags)
    if assignee_ids is not None:
        await _replace_assignees(db, task.id, assignee_ids)

    await db.commit()
    await db.refresh(task)
    await _attach_related(db, [task])
    return task


async def delete_task(db: AsyncSession, task_id: str) -> None:
    """
    Delete a task (FLAN-01.3).

    The task's tag and assignee rows go with it in the DATABASE:
    `flan_task_tag.task_id` and `flan_task_assignee.task_id` are both
    `ondelete="CASCADE"` (models.py, migration 0018), so a single
    `DELETE FROM flan_task WHERE id = :id` leaves no orphans and no service-side
    bookkeeping that could be half-applied. The roster member on the other side
    of an assignment is untouched — only the assignment row goes (D-V5P1-6).

    Resolves the task (404) and then requires its owning project to be writable
    (422 if archived): archiving a project freezes everything inside it,
    deletions included.
    """
    from app.modules.flan.models import Task

    _task, project_id = await resolve_task(db, task_id)
    await require_writable_project(db, project_id)

    await db.execute(delete(Task).where(Task.id == task_id))
    await db.commit()
