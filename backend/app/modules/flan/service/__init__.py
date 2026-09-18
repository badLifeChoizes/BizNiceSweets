# ABOUTME: FLAN service layer package — re-exports the public surface so
# ABOUTME: `from app.modules.flan.service import X` and `service.X` work
# ABOUTME: unchanged. Holds the shared surface (project loader, archived-project
# ABOUTME: write guard, phase/task resolvers) now; the per-entity modules
# ABOUTME: (projects, rollup, phases, keys, tasks, roster, assignments) are
# ABOUTME: re-exported here as plan tasks 10-16 add them.
"""FLAN service layer (business logic).

Split into cohesive per-entity submodules like syerp/service and crumb/service
(D-P10-6 — keep new suites' service layers thin; FLAN-01 is the Project
Management suite). This package re-exports the full public surface so
`from app.modules.flan.service import X` and `service.X` work unchanged.

Adding a submodule: append one alphabetically-placed `from
app.modules.flan.service.<name> import (...)` block below and one
correspondingly-labelled group to `__all__`. Both lists are kept one-name-per-
line and grouped by submodule so two engineers appending different submodules
touch different lines.
"""
from __future__ import annotations

from app.modules.flan.service._common import (
    get_project_or_404,
    require_writable_project,
    resolve_phase,
    resolve_task,
)
from app.modules.flan.service.assignments import (
    set_phase_assignees,
    set_task_assignees,
)
from app.modules.flan.service.keys import (
    generate_task_key,
)
from app.modules.flan.service.phases import (
    create_phase,
    delete_phase,
    list_phases,
    update_phase,
)
from app.modules.flan.service.projects import (
    archive_project,
    create_project,
    derive_key_prefix,
    get_project,
    list_projects,
    update_project,
)
from app.modules.flan.service.rollup import (
    PhaseRollup,
    phase_rollups,
)
from app.modules.flan.service.roster import (
    create_member,
    list_members,
    remove_member,
    update_member,
)
from app.modules.flan.service.tasks import (
    create_task,
    delete_task,
    get_task,
    list_tasks,
    require_project_members,
    update_task,
)

__all__ = [
    # _common — shared loader, archive guard, resolvers
    "get_project_or_404",
    "require_writable_project",
    "resolve_phase",
    "resolve_task",
    # assignments — full-replacement assignee set/clear for tasks and phases,
    # validated against the project roster (FLAN-01.5)
    "set_phase_assignees",
    "set_task_assignees",
    # keys — numeric-safe task-key generation (FLAN-01.3, D-P8-6, D-V5P1-7)
    "generate_task_key",
    # phases — phase CRUD with the derived rollup attached (FLAN-01.2)
    "create_phase",
    "delete_phase",
    "list_phases",
    "update_phase",
    # projects — project CRUD, archive and tags (FLAN-01.1, FLAN-01.6)
    "archive_project",
    "create_project",
    "derive_key_prefix",
    "get_project",
    "list_projects",
    "update_project",
    # rollup — phase-derived dates and % complete (D-V5-1)
    "PhaseRollup",
    "phase_rollups",
    # roster — team-member CRUD and the soft-remove that clears assignments
    # (FLAN-01.4, D-V5P1-6)
    "create_member",
    "list_members",
    "remove_member",
    "update_member",
    # tasks — task CRUD (FLAN-01.3) + the shared roster-membership guard
    # every assignee write validates against (FLAN-01.5)
    "create_task",
    "delete_task",
    "get_task",
    "list_tasks",
    "require_project_members",
    "update_task",
]
