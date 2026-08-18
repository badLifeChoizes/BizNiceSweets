# ABOUTME: FLAN (Project Management) API router — projects, phases, tasks, team
# ABOUTME: roster and assignment. STUB as of Task 5: it carries the module's
# ABOUTME: endpoint-surface contract and an empty APIRouter so FLAN can register
# ABOUTME: and mount; the routes themselves land in Tasks 17-18, mirroring
# ABOUTME: gelato/router.py (thin endpoints delegating to flan/service, gated on
# ABOUTME: flan:read / flan:write, audit row written AFTER the service commit).
"""
FLAN API router — projects, phases, tasks, team & assignment (FLAN-01).

STUB — this module currently exposes an empty APIRouter. It exists so FLAN can
satisfy the Module Protocol (app/modules/flan/__init__.py imports `router` and
calls registry.register), which is all Task 5 delivers. The endpoints below are
the agreed surface; Tasks 17 (projects + phases) and 18 (tasks, roster,
assignment) implement them.

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
  DELETE /flan/phases/{phase_id}               — delete a phase, cascading to its tasks (flan:write)
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
own commit (write_audit self-commits, mirroring the SYERP/GELATO router order):
project.created / project.updated / project.archived, phase.created /
phase.updated / phase.deleted, task.created / task.updated / task.deleted,
team_member.created / team_member.updated / team_member.removed,
task.assignees_set and phase.assignees_set. GET routes are read-only and write
no audit row.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
