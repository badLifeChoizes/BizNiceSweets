# ABOUTME: FLAN assignment set/clear (FLAN-01.5) — replace the whole assignee
# ABOUTME: set of one task or one phase in a single call. Full-replacement, empty
# ABOUTME: list clears, idempotent. Every id is validated against the project's
# ABOUTME: roster by tasks.py::require_project_members — ONE implementation of
# ABOUTME: that rule, shared, never restated here.
"""FLAN assignments service (business logic).

Two functions, one shape: `set_task_assignees` and `set_phase_assignees` take
the COMPLETE assignee list a task or phase should have after the call and make
the database say exactly that (FLAN-01.5). They back the two PUT routes
(`PUT /flan/tasks/{task_id}/assignees`, `PUT /flan/phases/{phase_id}/assignees`)
and the `AssigneeSet` payload, which is a PUT rather than a PATCH for this
reason.

Four rules are load-bearing here:

  * **The roster rule has exactly ONE implementation.** Membership is checked by
    `tasks.py::require_project_members`, imported — not re-written. That guard
    was made public for this caller (see its docstring: promote it to
    `_common.py` if a third appears; this module is the second). Two divergent
    copies of "every assignee is an ACTIVE member of the SAME project" is how
    FLAN-01.5 quietly stops being enforced on one of the two paths while the
    other stays green.
  * **Full-replacement semantics.** The existing rows for the target are
    deleted and the supplied set is inserted, so the argument *is* the assignee
    list afterwards. An **empty list is valid** and is how an assignment is
    cleared — it is not an error and not a no-op.
  * **Idempotent.** Setting the same list twice leaves the same rows and the
    same count: the delete-then-insert makes a repeat write converge rather than
    collide on the composite PK `(task_id, member_id)` / `(phase_id, member_id)`.
    The schema (`schemas.py::AssigneeSet`) already strips, de-duplicates and
    rejects blank ids, but these functions are also called directly (services,
    scripts, tests), so the ids are de-duplicated here too — a payload naming the
    same member twice must never reach the composite PK.
  * **Clearing an assignment never touches the roster.** Only
    `flan_task_assignee` / `flan_phase_assignee` rows are written; the
    `flan_team_member` rows on the other side survive untouched, which is the
    mirror image of `roster.py::remove_member` scoping its deletes by
    `member_id` and touching no task. `member_id` carries **no** DB cascade
    (D-V5P1-6) precisely so assignment changes are explicit service actions, so
    nothing here may lean on a database cascade.

Both functions call `require_writable_project` first: archiving a project
freezes everything inside it, assignment writes included (422).

Audit events are written at the router layer after the service commits (house
idiom — gelato/router.py), never here. Models are imported lazily inside each
function (house idiom — service/_common.py, crumb/service/leads.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from app.modules.flan.service._common import (
    require_writable_project,
    resolve_phase,
    resolve_task,
)
from app.modules.flan.service.tasks import require_project_members

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.flan.models import PhaseAssignee, TaskAssignee


# ---------------------------------------------------------------------------
# The shared write — one join table, one target, full replacement (FLAN-01.5)
# ---------------------------------------------------------------------------


async def _replace_assignee_rows(
    db: AsyncSession,
    model: type[TaskAssignee] | type[PhaseAssignee],
    target_field: str,
    target_id: str,
    member_ids: Sequence[str],
) -> list[str]:
    """
    Replace one target's whole assignee set in its join table and return the set
    as it now stands, read back from the database.

    `model` is `TaskAssignee` or `PhaseAssignee` and `target_field` is the
    matching column name (`"task_id"` / `"phase_id"`); the two tables are the
    same table twice, so this is written once rather than per entity.

    Full replacement: the target's existing rows are deleted first, so the
    supplied list is the complete set afterwards and an empty list clears every
    assignment. Ids are de-duplicated (order-preserving) before the insert — the
    composite PK would otherwise raise on a caller that named the same member
    twice, and this function is reachable without the schema's normalization.

    **Validate with `require_project_members` BEFORE calling this** — like
    `tasks.py::_replace_assignees`, this writes rows and does not judge them.

    Commits, then re-reads ordered by `member_id` rather than echoing the
    argument: the caller (and the router's `AssigneeSet` response) gets what the
    database actually holds, in the same stable order `tasks.py::_load_assignees`
    returns, so a read-back after a write is byte-identical between the two
    paths.
    """
    target_column = getattr(model, target_field)

    await db.execute(delete(model).where(target_column == target_id))
    for member_id in dict.fromkeys(member_ids):
        db.add(model(**{target_field: target_id, "member_id": member_id}))
    await db.commit()

    result = await db.execute(
        select(model.member_id).where(target_column == target_id).order_by(model.member_id)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Set / clear (FLAN-01.5)
# ---------------------------------------------------------------------------


async def set_task_assignees(
    db: AsyncSession, task_id: str, member_ids: Sequence[str]
) -> list[str]:
    """
    Replace a task's assignee set (FLAN-01.5) and return the stored list.

    `member_ids` is the COMPLETE list the task carries afterwards, not an
    addition: existing rows go, the supplied set lands, and **`[]` is valid** —
    it clears the assignment rows and returns an empty list.

    Order of operations, each part load-bearing:

      1. `resolve_task` — 404 if the task is gone, and it hands back the owning
         project id, which is the scope both remaining checks need;
      2. `require_writable_project` — 422 if that project is archived, because
         archiving freezes everything inside it, assignment writes included;
      3. `require_project_members` — 422 naming the offending id when one is
         unknown, belongs to **another project's** roster, or has been
         soft-removed (`active=False`, D-V5P1-6). This is the same guard
         `create_task`/`update_task` use, imported rather than restated.

    Re-setting the same list is idempotent: the row count does not move and the
    composite PK is never hit. The task row itself is not loaded for writing,
    dirtied or re-saved, and no `flan_team_member` row is touched — clearing an
    assignment must never delete a member.
    """
    from app.modules.flan.models import TaskAssignee

    _task, project_id = await resolve_task(db, task_id)
    await require_writable_project(db, project_id)
    await require_project_members(db, project_id, member_ids)

    return await _replace_assignee_rows(db, TaskAssignee, "task_id", task_id, member_ids)


async def set_phase_assignees(
    db: AsyncSession, phase_id: str, member_ids: Sequence[str]
) -> list[str]:
    """
    Replace a phase's assignee set (FLAN-01.5) and return the stored list.

    Identical contract to `set_task_assignees`, against `flan_phase_assignee`
    and resolved through `resolve_phase` (404): full replacement, `[]` clears,
    the repeat write is idempotent, and every id must be an ACTIVE member of
    the phase's own project (422 naming it) via the shared
    `require_project_members`.

    A phase carries assignees in its own right — a phase lead is not implied by
    the assignees of its tasks and is not derived from them (unlike the phase's
    dates and % complete, D-V5-1). Nothing here reads or writes `flan_task`.
    """
    from app.modules.flan.models import PhaseAssignee

    _phase, project_id = await resolve_phase(db, phase_id)
    await require_writable_project(db, project_id)
    await require_project_members(db, project_id, member_ids)

    return await _replace_assignee_rows(db, PhaseAssignee, "phase_id", phase_id, member_ids)
