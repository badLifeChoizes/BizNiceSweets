# ABOUTME: Shared FLAN service surface — the project loader, the archived-project
# ABOUTME: write guard every mutating FLAN call goes through, and the phase/task
# ABOUTME: resolvers that hand back the row together with its owning project id
# ABOUTME: so one lookup feeds the guard (FLAN-01.1).
"""Shared FLAN service helpers.

Split into cohesive submodules like syerp/service and crumb/service (D-P10-6 —
keep new suites' service layers thin and per-entity). This module holds the
surface every entity module depends on: the project loader, the archived-project
write guard, and the two resolvers that turn a phase or task id into its row plus
its owning project id.

**The archive guard is the point of this module.** A project's `active` flag is a
soft delete that retains all data, and "an archived project rejects writes" means
*every* write inside it — phase, task, roster and assignment mutations included,
not just writes to the project row. Every mutating function in this module's
package therefore calls `require_writable_project` first, and gets the same 422
with the same wording; the status mirrors the archived-bin precedent in
gelato/service/putaway.py (archived-target writes are 422, not 404 or 409).

FLAN primary keys are String(36) uuid strings (see flan/models.py), so all ids
here are `str`, never `int`.

Models are imported lazily inside each function (house idiom — mirrors
crumb/service/_common.py and gelato/service/bins.py) so importing this module
never drags in the ORM layer at import time.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.flan.models import Phase, Project, Task


# ---------------------------------------------------------------------------
# Project loader + the archived-project write guard (FLAN-01.1)
# ---------------------------------------------------------------------------


async def get_project_or_404(db: AsyncSession, project_id: str) -> Project:
    """
    Load a project by id. Raises HTTP 404 if no project with that id exists
    (mirrors syerp/service.get_partner and gelato/service.get_bin).

    This is the read path: it does NOT care whether the project is archived, so
    an archived project remains fully readable. Writes must go through
    `require_writable_project` instead.
    """
    from app.modules.flan.models import Project

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )
    return project


async def require_writable_project(db: AsyncSession, project_id: str) -> Project:
    """
    Load a project and assert it accepts writes; return the loaded row.

    Raises HTTP 404 if the project does not exist, and HTTP 422 if it exists but
    is archived (`active is False`) — the archived-target status the platform
    already uses for a write aimed at an archived row
    (gelato/service/putaway.py:175, "Destination bin ... is archived.").

    Call this FIRST in every mutating FLAN service function, including ones that
    write a phase, task, roster or assignment row rather than the project itself:
    archiving a project freezes everything inside it. Returning the row means the
    caller gets the project (for `key_prefix`, `currency`, a subsequent
    `SELECT ... FOR UPDATE`, ...) without a second `db.get`.
    """
    project = await get_project_or_404(db, project_id)
    if not project.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Project {project_id} is archived and rejects writes.",
        )
    return project


# ---------------------------------------------------------------------------
# Phase / task resolvers — row + owning project id (FLAN-01.2, FLAN-01.3)
# ---------------------------------------------------------------------------


async def resolve_phase(db: AsyncSession, phase_id: str) -> tuple[Phase, str]:
    """
    Load a phase by id and return `(phase, project_id)`. Raises HTTP 404 if no
    phase with that id exists.

    The owning project id is returned alongside the row so a mutation can do one
    lookup and then hand the id straight to `require_writable_project` — phase
    routes are addressed by phase id alone (PATCH/DELETE /flan/phases/{id}), so
    the project scope has to come from the row.
    """
    from app.modules.flan.models import Phase

    phase = await db.get(Phase, phase_id)
    if phase is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Phase {phase_id} not found",
        )
    return phase, phase.project_id


async def resolve_task(db: AsyncSession, task_id: str) -> tuple[Task, str]:
    """
    Load a task by id and return `(task, project_id)`. Raises HTTP 404 if no task
    with that id exists.

    `Task.project_id` is denormalized from the phase (it backs
    uq_flan_task_project_key), so the owning project is read straight off the row
    — no join through flan_phase — and can be passed to
    `require_writable_project` immediately.
    """
    from app.modules.flan.models import Task

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return task, task.project_id
