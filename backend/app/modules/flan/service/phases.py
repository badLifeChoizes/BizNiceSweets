# ABOUTME: FLAN phase CRUD (FLAN-01.2) — list, create, patch and delete the
# ABOUTME: ordered stages of a project. Every phase this module returns carries
# ABOUTME: the Task-11 rollup (derived dates and % complete, D-V5-1), attached
# ABOUTME: from ONE batched query; deleting a phase cascades to its tasks in the
# ABOUTME: database and reports how many went with it.
"""FLAN phases service (business logic).

A phase belongs to exactly one project for its whole life (FLAN-01.2) and is
addressed by its own id once created (PATCH/DELETE /flan/phases/{phase_id}), so
the owning project is read off the row via `resolve_phase` rather than taken
from the caller.

Three rules are load-bearing here:

  * **A phase's dates and % complete are DERIVED, never written** (D-V5-1).
    `flan_phase` has no `start_date`, `due_date` or `percent_complete` column and
    the write schemas have no such field, so there is no path by which this
    module could hand-set one. What it does instead is *attach* the rollup
    (service/rollup.py) to every phase instance it returns, which is what
    `PhaseRead` reads through `from_attributes` — the same
    service-fills-a-derived-field pattern `projects.py::_attach_tags` uses for
    the tag join table.
  * **The rollup is fetched in ONE batched call, never one per phase.**
    `phase_rollups` answers a whole list with a single grouped query;
    `list_phases` passes every phase id in one call. A call per phase is an N+1
    on the hottest read in the suite. Because `phase_rollups` guarantees that
    *every requested id is a key of the returned dict*, the call sites below
    index it directly — a `.get(id, default)` fallback here would silently mask
    the empty-phase branch, which is the case FLAN-01.2 names explicitly.
  * **Deleting a phase cascades to its tasks in the DATABASE** (FLAN-01.2).
    `flan_task.phase_id` is `ondelete="CASCADE"` (models.py::Task, migration
    0018), so a single `DELETE FROM flan_phase WHERE id = :id` takes the phase's
    tasks — and, transitively, their tag and assignee rows — with it. The task
    count is read *before* the delete so the router can name it in the audit
    detail.

Every mutation calls `require_writable_project` first: archiving a project
freezes everything inside it, phases included (422).

Audit events are written at the router layer after the service commits (house
idiom — gelato/router.py), never here. Models are imported lazily inside each
function (house idiom — service/_common.py, crumb/service/leads.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select

from app.modules.flan.service._common import (
    require_writable_project,
    resolve_phase,
)
from app.modules.flan.service.rollup import phase_rollups

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.flan.models import Phase
    from app.modules.flan.schemas import PhaseCreate, PhaseUpdate


#: Phase columns that are NOT NULL: a PATCH carrying an explicit null for one of
#: these is ignored rather than being sent to the database as a constraint
#: violation. `description` is the only nullable phase field, so an explicit null
#: there legitimately clears it. Mirrors projects.py::_NOT_NULL_FIELDS.
_NOT_NULL_FIELDS = frozenset({"name", "sort_order", "status"})


# ---------------------------------------------------------------------------
# The derived rollup — attached, never stored (D-V5-1)
# ---------------------------------------------------------------------------


async def _attach_rollups(db: AsyncSession, phases: Sequence[Phase]) -> None:
    """
    Attach each phase's derived dates, percentage and task counts to the ORM
    instance as plain attributes, in place — in ONE batched query.

    `flan_phase` has no column behind any of these five values (D-V5-1), so
    nothing populates them on their own: `PhaseRead` declares them as
    service-filled fields and reads them off the instance through
    `from_attributes`. **Every function in this module that returns a phase calls
    this**, so a phase can never reach a caller without its rollup — the same
    guarantee `projects.py::_attach_tags` gives the tag list.

    One `phase_rollups` call covers the whole batch (no N+1), and its contract
    that every requested id is present is why the dict is indexed directly
    below: a `.get(..., NO_TASKS)` fallback would hide the empty-phase branch
    instead of exercising it.

    The attributes are not mapped, so they survive `commit()`/`refresh()`
    untouched and are never written back to any column.
    """
    rollups = await phase_rollups(db, [phase.id for phase in phases])
    for phase in phases:
        rollup = rollups[phase.id]
        phase.derived_start_date = rollup.derived_start_date  # type: ignore[attr-defined]
        phase.derived_due_date = rollup.derived_due_date  # type: ignore[attr-defined]
        phase.percent_complete = rollup.percent_complete  # type: ignore[attr-defined]
        phase.task_count = rollup.task_count  # type: ignore[attr-defined]
        phase.done_count = rollup.done_count  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# CRUD (FLAN-01.2)
# ---------------------------------------------------------------------------


async def list_phases(db: AsyncSession, project_id: str) -> list[Phase]:
    """
    Return one project's phases, each with its derived rollup attached.

    Ordered by `sort_order`, then by `name` — `sort_order` is the display order
    the user controls and defaults to 0, so the name tiebreak is what keeps a
    freshly-created set of phases in a stable, readable order between reads
    rather than in insertion-hash order.

    Two queries in total regardless of how many phases come back: one for the
    rows, one batched `phase_rollups` for every phase's dates and percentage.

    This is a read, so it does not care whether the project is archived — an
    archived project retains all its data and stays fully readable (FLAN-01.1).
    """
    from app.modules.flan.models import Phase

    result = await db.execute(
        select(Phase)
        .where(Phase.project_id == project_id)
        .order_by(Phase.sort_order.asc(), Phase.name.asc())
    )
    phases = list(result.scalars().all())
    await _attach_rollups(db, phases)
    return phases


async def create_phase(db: AsyncSession, project_id: str, data: PhaseCreate) -> Phase:
    """
    Create a phase inside a project (FLAN-01.2) and return it.

    **`project_id` is an argument, not a payload field**: the route is
    `POST /flan/projects/{project_id}/phases`, so the owning project comes from
    the path and `PhaseCreate` deliberately carries no `project_id` — a phase
    cannot be pointed at a different project than the one it was posted to.

    Calls `require_writable_project` first: 404 if the project is gone, 422 if it
    is archived. The returned phase carries the rollup of a brand-new phase —
    no tasks, so no dates and "0.00" (FLAN-01.2).
    """
    from app.modules.flan.models import Phase

    await require_writable_project(db, project_id)

    phase = Phase(
        project_id=project_id,
        name=data.name,
        sort_order=data.sort_order,
        status=data.status,
        description=data.description,
    )
    db.add(phase)
    await db.commit()
    await db.refresh(phase)
    await _attach_rollups(db, [phase])
    return phase


async def update_phase(db: AsyncSession, phase_id: str, data: PhaseUpdate) -> Phase:
    """
    Apply a partial update to a phase (PATCH semantics) and return it.

    **Name, sort_order, status and description are the only writable fields**,
    and that is structural rather than a check: `PhaseUpdate` has no date and no
    percent field at all (D-V5-1), and `flan_phase` has no such column to write
    even if it did. A phase's dates and % complete are derived from its tasks on
    every read and can never be hand-set. `project_id` is absent for the same
    kind of reason — a phase belongs to exactly one project for its whole life.

    Resolves the phase (404) and then requires its owning project to be writable
    (422 if archived). Only the fields the payload actually SET are written
    (`exclude_unset`), so an omitted field is untouched and an explicit null
    clears `description`; an explicit null aimed at a NOT NULL column is ignored
    rather than turned into a database error (mirrors update_project).
    """
    phase, project_id = await resolve_phase(db, phase_id)
    await require_writable_project(db, project_id)

    patch = data.model_dump(exclude_unset=True)
    for field, value in patch.items():
        if value is None and field in _NOT_NULL_FIELDS:
            continue
        setattr(phase, field, value)

    await db.commit()
    await db.refresh(phase)
    await _attach_rollups(db, [phase])
    return phase


async def delete_phase(db: AsyncSession, phase_id: str) -> int:
    """
    Delete a phase and, with it, its tasks (FLAN-01.2). Returns the number of
    tasks that went with it.

    The cascade is the DATABASE's: `flan_task.phase_id` is declared
    `ondelete="CASCADE"` (models.py::Task, migration 0018), so the single
    `DELETE FROM flan_phase WHERE id = :id` below removes the phase's tasks —
    and, transitively, those tasks' tag and assignee rows, plus the phase's own
    assignee rows — in one statement. Nothing here deletes tasks by hand, so the
    cascade cannot be half-applied by a service that forgot a table. Only THIS
    phase's tasks go: `flan_task.phase_id` scopes the cascade, so a sibling
    phase's tasks in the same project are untouched.

    **The task count is read before the delete**, since afterwards there is
    nothing left to count — the router (Task 17) names it in the `phase.deleted`
    audit detail, which is the only record that a delete of one row took five
    others with it.

    Resolves the phase (404) and then requires its owning project to be writable
    (422 if archived): archiving a project freezes everything inside it,
    deletions included.
    """
    from app.modules.flan.models import Phase, Task

    _phase, project_id = await resolve_phase(db, phase_id)
    await require_writable_project(db, project_id)

    result = await db.execute(
        select(func.count()).select_from(Task).where(Task.phase_id == phase_id)
    )
    task_count = int(result.scalar_one())

    await db.execute(delete(Phase).where(Phase.id == phase_id))
    await db.commit()
    return task_count
