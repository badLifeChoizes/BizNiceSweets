# ABOUTME: FLAN team-roster CRUD (FLAN-01.4) — list, create, patch and
# ABOUTME: soft-remove the members a project is staffed from, each optionally
# ABOUTME: linked to a platform user. Removal is a SOFT remove (D-V5P1-6): the
# ABOUTME: row stays, `active` clears, and the member's task/phase assignment
# ABOUTME: rows are deleted BY member_id in the same transaction — never by
# ABOUTME: task_id, and touching no task row.
"""FLAN team roster service (business logic).

A roster is per-project by design (FLAN-01.4): the same person working on two
projects is two rows, so a member belongs to exactly one project for its whole
life and is addressed by its own id once created
(PATCH/DELETE /flan/team/{member_id}).

Four rules are load-bearing here:

  * **Removal is a SOFT remove** (D-V5P1-6). `remove_member` sets `active=False`
    and deletes the member's `flan_task_assignee` / `flan_phase_assignee` rows
    in the SAME transaction. That is what makes FLAN-01.4's "removing a roster
    member clears their assignments but leaves the tasks intact" true by
    construction: the row survives, so every past reference to the member stays
    resolvable for FLAN-05/06/10 (risks, notes, comments, the activity log),
    and it matches the archive-not-delete precedent the rest of the platform
    follows (`crumb_lead.active`, `gelato_bin.active`, `syerp_partner.active`).
  * **The assignment deletes are scoped by `member_id`, NEVER by `task_id`.**
    Scoping by task would clear *other* members' assignments on the same task —
    a task with two people on it would lose both when one of them leaves. "Leaves
    the tasks intact" is meant literally: `remove_member` writes to
    `flan_team_member` and the two join tables only, so no task row is loaded,
    dirtied or re-saved and every task's `updated_at` is byte-identical
    afterwards.
  * **A member with NO `user_id` is a full collaborator.** The link is optional
    and normally absent (FLAN-01.4); an unlinked member is listed, assignable
    and indistinguishable from a linked one everywhere except the link itself.
    Postgres permits many NULLs under `uq_flan_member_project_user`, so a
    project can hold any number of unlinked members.
  * **Deleting or deactivating a platform user must not touch the roster.**
    `flan_team_member.user_id` is `ondelete="SET NULL"` (models.py, migration
    0018) so a deleted user leaves an unlinked roster row rather than taking the
    project's history with it, and auth's own path is deactivation
    (`users.is_active`, auth/router.py), which touches nothing here. That is why
    `_require_linkable_user` checks only that the user EXISTS — a deactivated
    user's roster row and link both stay valid.

`hourly_rate` is **stored and read by nothing in v5.0** (D-V5-2 / D-M5-2). The
column exists so the rate a shop already knows is captured now; no rollup,
report or endpoint in this release derives a cost from it, and nothing in this
module reads it back except to return it verbatim. Do not add a cost
calculation here.

**There is deliberately no reactivation path** (owner decision at plan review).
A soft-removed member stays removed in v5.0: there is no `reactivate_member`,
and `TeamMemberUpdate` carries no `active` field, so a PATCH cannot flip the
flag on its own — that would resurrect a member whose assignment rows are gone
and, worse, would let a member be un-removed without the assignment bookkeeping
the removal did. FLAN-01.4 does not ask for reactivation, and because the row
and its history survive, a later phase can add one additively.

Every mutation calls `require_writable_project` first: archiving a project
freezes everything inside it, roster writes included (422).

Audit events are written at the router layer after the service commits (house
idiom — gelato/router.py), never here. Models are imported lazily inside each
function (house idiom — service/_common.py, crumb/service/leads.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import delete, select

from app.modules.flan.service._common import require_writable_project

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.flan.models import TeamMember
    from app.modules.flan.schemas import TeamMemberCreate, TeamMemberUpdate


#: Team-member columns that are NOT NULL: a PATCH carrying an explicit null for
#: one of these is ignored rather than being sent to the database as a
#: constraint violation. `role`, `email`, `color`, `hourly_rate` and `user_id`
#: are all nullable, so an explicit null there legitimately clears them — that
#: is how a member is un-linked from a platform user. Mirrors
#: projects.py::_NOT_NULL_FIELDS.
_NOT_NULL_FIELDS = frozenset({"name"})


# ---------------------------------------------------------------------------
# Resolver + the platform-user link check (FLAN-01.4)
# ---------------------------------------------------------------------------


async def _resolve_member(db: AsyncSession, member_id: str) -> tuple[TeamMember, str]:
    """
    Load a roster member by id and return `(member, project_id)`. Raises HTTP
    404 if no member with that id exists.

    The owning project id is returned alongside the row for the same reason
    `_common.resolve_phase` returns it: member routes are addressed by member id
    alone (PATCH/DELETE /flan/team/{member_id}), so the project scope has to
    come off the row before `require_writable_project` can be called.

    Private to this module — `_common.py` owns the resolvers the whole package
    shares, and nothing outside the roster resolves a member today. Promote it
    there if a second caller appears.
    """
    from app.modules.flan.models import TeamMember

    member = await db.get(TeamMember, member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Team member {member_id} not found",
        )
    return member, member.project_id


async def _require_linkable_user(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    exclude_member_id: str | None = None,
) -> None:
    """
    Assert `user_id` names an existing platform user that this project's roster
    can still link (FLAN-01.4).

    Two failures, two statuses:

      * **404** — no row in `users` has that id. The link is an FK, so an
        unknown id would otherwise surface as an opaque integrity error at
        flush time.
      * **422** — another member of THIS project already links that user. The
        roster is per-project, so the same user may of course be linked in a
        *different* project (that is the two-projects-one-person case
        FLAN-01.4 describes); what is refused is the same user appearing twice
        on one project's roster, which `uq_flan_member_project_user` backs at
        the database level.

    Only the **existence** of the user is checked, never `users.is_active`:
    deactivating a platform user must not touch the roster row or its history
    (FLAN-01.4), so a deactivated user stays linked and stays linkable.

    A soft-removed member still holds its link, and the 422 says so explicitly.
    `uq_flan_member_project_user` constrains `(project_id, user_id)` regardless
    of `active` — Postgres has no partial-unique-index here — so re-linking a
    user whose earlier member row was removed would violate the constraint at
    flush time and 500. Refusing it in the service turns that into an honest
    4xx with a message naming the row in the way; since there is no
    reactivation path in v5.0 (see the module docstring), the same-project
    re-link case cannot be resolved by un-removing the old row either.

    `exclude_member_id` skips the member being patched, so re-sending a member's
    own `user_id` in a PATCH is not a self-conflict.
    """
    from app.modules.auth.models import User
    from app.modules.flan.models import TeamMember

    exists = await db.execute(select(User.id).where(User.id == user_id).limit(1))
    if exists.first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    stmt = select(TeamMember.id, TeamMember.name, TeamMember.active).where(
        TeamMember.project_id == project_id,
        TeamMember.user_id == user_id,
    )
    if exclude_member_id is not None:
        stmt = stmt.where(TeamMember.id != exclude_member_id)

    result = await db.execute(stmt)
    for other_id, other_name, other_active in result.all():
        if other_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"User {user_id} is already linked to member {other_name} "
                    f"({other_id}) on project {project_id}."
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"User {user_id} is still linked to removed member {other_name} "
                f"({other_id}) on project {project_id}; a removed member keeps "
                f"its user link."
            ),
        )


# ---------------------------------------------------------------------------
# CRUD (FLAN-01.4)
# ---------------------------------------------------------------------------


async def list_members(
    db: AsyncSession, project_id: str, include_removed: bool = False
) -> list[TeamMember]:
    """
    Return one project's roster (FLAN-01.4).

    **Excludes soft-removed (`active=False`) members unless `include_removed`
    is True** (D-V5P1-6) — a removed member is retained so historical
    references still resolve, but it is not part of the current team. Assignee
    pickers use the default, which is what keeps a removed member out of them
    without every caller remembering the filter; `include_removed=True` is for
    an admin view of who *was* on the project.

    Ordered by name, then by creation time: two people on one roster may share
    a name, so the timestamp is the tiebreak that keeps the order stable
    between reads (mirrors `projects.py::list_projects`).

    This is a read, so it does not care whether the project is archived — an
    archived project retains all its data and stays fully readable
    (FLAN-01.1).
    """
    from app.modules.flan.models import TeamMember

    stmt = select(TeamMember).where(TeamMember.project_id == project_id)
    if not include_removed:
        stmt = stmt.where(TeamMember.active.is_(True))
    stmt = stmt.order_by(TeamMember.name.asc(), TeamMember.created_at.asc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_member(
    db: AsyncSession, project_id: str, data: TeamMemberCreate
) -> TeamMember:
    """
    Add a member to a project's roster (FLAN-01.4) and return it.

    **`project_id` is an argument, not a payload field**: the route is
    `POST /flan/projects/{project_id}/team`, so the owning project comes from
    the path and `TeamMemberCreate` deliberately carries no `project_id` — a
    member cannot be pointed at a different roster than the one it was posted
    to.

    Calls `require_writable_project` first: 404 if the project is gone, 422 if
    it is archived. `user_id` is optional and normally absent; when supplied it
    is validated by `_require_linkable_user` (404 unknown user, 422 already
    linked on this project). A member created with **no** `user_id` is a full
    collaborator — listed, assignable, and unconstrained by
    `uq_flan_member_project_user`, which Postgres does not apply to NULLs.

    `hourly_rate` is stored verbatim and read by nothing in v5.0 (D-V5-2 /
    D-M5-2); no cost is derived from it here or anywhere else in this release.

    A member is always created **active**: `TeamMemberCreate` has no `active`
    field, because removal is its own endpoint and a soft-remove (D-V5P1-6).
    """
    from app.modules.flan.models import TeamMember

    await require_writable_project(db, project_id)
    if data.user_id is not None:
        await _require_linkable_user(db, project_id, data.user_id)

    member = TeamMember(
        project_id=project_id,
        name=data.name,
        role=data.role,
        email=data.email,
        color=data.color,
        hourly_rate=data.hourly_rate,
        user_id=data.user_id,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def update_member(
    db: AsyncSession, member_id: str, data: TeamMemberUpdate
) -> TeamMember:
    """
    Apply a partial update to a roster member (PATCH semantics) and return it.

    Resolves the member (404) and then requires its owning project to be
    writable (422 if archived).

    `project_id` cannot be changed and `active` cannot be set: `TeamMemberUpdate`
    carries neither field, so a member belongs to one roster for its whole life
    and removal stays the one endpoint that also clears assignments (D-V5P1-6).
    A PATCH able to flip `active` on its own would leave a removed member's
    assignment rows deleted but the member back on the team — or, in the other
    direction, remove them without clearing anything.

    A supplied `user_id` goes through `_require_linkable_user` (404 unknown
    user, 422 already linked on this project), with this member excluded from
    the conflict check so re-sending its own link is a no-op rather than a
    self-conflict. An explicit **null** clears the link, which is the supported
    way to un-link a member; `user_id` is nullable, so nothing is lost.

    Only the fields the payload actually SET are written (`exclude_unset`), so
    an omitted field is untouched and an explicit null clears a nullable one; an
    explicit null aimed at a NOT NULL column is ignored rather than turned into
    a database error (mirrors update_project). `hourly_rate` remains
    stored-and-unread (D-V5-2 / D-M5-2).
    """
    member, project_id = await _resolve_member(db, member_id)
    await require_writable_project(db, project_id)

    patch = data.model_dump(exclude_unset=True)

    if patch.get("user_id") is not None:
        await _require_linkable_user(
            db, project_id, patch["user_id"], exclude_member_id=member_id
        )

    for field, value in patch.items():
        if value is None and field in _NOT_NULL_FIELDS:
            continue
        setattr(member, field, value)

    await db.commit()
    await db.refresh(member)
    return member


async def remove_member(db: AsyncSession, member_id: str) -> int:
    """
    Remove a member from a project's roster — a SOFT remove (D-V5P1-6). Returns
    the number of assignments cleared.

    Two things happen in ONE transaction, and both are load-bearing:

      1. `active` is cleared. The row itself is **kept**, with its name, role,
         email, colour, rate and user link intact, so every past reference to
         the member stays resolvable (FLAN-01.4 — "leaves its history
         untouched") and later phases can render who *used* to own a task
         instead of finding a dangling id.
      2. The member's `flan_task_assignee` and `flan_phase_assignee` rows are
         deleted. Neither FK cascades on `member_id` (models.py::TaskAssignee)
         precisely so this happens here, explicitly and auditably, rather than
         silently in the database.

    **Both deletes are scoped by `member_id`, never by `task_id` or
    `phase_id`.** A task may carry several assignees; deleting by task would
    take the other members' assignments with it. Nothing here loads, dirties or
    re-saves a task or phase row either, so the tasks this member was on keep
    their `summary`, their dates and — the observable proof — their exact
    `updated_at`. "Clears their assignments but leaves the tasks intact" is
    meant literally.

    The count is read from the deletes' `rowcount` so the router (Task 18) can
    name it in the `team_member.removed` audit detail — the only record that
    removing one member detached them from N pieces of work.

    Resolves the member (404) and then requires its owning project to be
    writable (422 if archived): archiving a project freezes everything inside
    it, roster removals included.

    **Idempotent**: removing an already-removed member is a no-op that returns
    0, since its assignment rows are already gone (mirrors
    `projects.py::archive_project`). There is no reactivation path in v5.0 — see
    the module docstring.
    """
    from app.modules.flan.models import PhaseAssignee, TaskAssignee

    member, project_id = await _resolve_member(db, member_id)
    await require_writable_project(db, project_id)

    task_links = await db.execute(
        delete(TaskAssignee).where(TaskAssignee.member_id == member_id)
    )
    phase_links = await db.execute(
        delete(PhaseAssignee).where(PhaseAssignee.member_id == member_id)
    )
    cleared = int(task_links.rowcount or 0) + int(phase_links.rowcount or 0)

    member.active = False
    await db.commit()
    return cleared
