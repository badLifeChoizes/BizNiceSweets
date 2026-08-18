# ABOUTME: FLAN project CRUD and archive (FLAN-01.1, FLAN-01.6) — create, list,
# ABOUTME: read, patch and soft-archive a project, each carrying its opaque tag
# ABOUTME: set from flan_project_tag (D-V5P1-5). Holds the two project rules the
# ABOUTME: rest of the suite leans on: duplicate names are allowed, and
# ABOUTME: key_prefix is editable only until the project's first task exists.
"""FLAN projects service (business logic).

A project is FLAN's top-level scope: phases, tasks and the team roster all hang
off one, and no view mixes two projects' data (FLAN-01.6). This module owns the
project row itself.

Four rules are load-bearing here:

  * **Duplicate project names are allowed** (FLAN-01.1). `flan_project.name`
    carries no unique constraint and there is deliberately **no uniqueness
    pre-check** in `create_project` — two projects may share a name and are told
    apart by their ids.
  * **`key_prefix` is locked once the first task exists** (D-V5P1-2). It is
    derived from the name at create, freely editable while the project has no
    tasks, and refused with a 422 afterwards — task keys already issued under
    the old prefix would otherwise stop matching the generator's
    `^{prefix}-[0-9]+$` filter, and `PRJ-9` would sit in a project that claims
    to be `CRIS`. The v45 prototype's majority-inference of a prefix from the
    existing keys (`keyPrefix()`, schedule_gate-v45.html:3197-3207) is **not**
    ported: the platform stores the prefix.
  * **Archiving is a soft delete.** `archive_project` clears `active`; the row
    keeps every field and stays fully readable through `get_project` /
    `list_projects(include_archived=True)`. Only writes are refused, by
    `require_writable_project` (422) — and that guard covers every write *inside*
    the project too, not just writes to the project row.
  * **Tags round-trip** (D-V5P1-5). They live in the `flan_project_tag` join
    table, not in a column and not in an ORM relationship, so every function
    here attaches the loaded list to the returned instance as `.tags` — that is
    what `ProjectRead.tags` reads via `from_attributes`. A function that skipped
    it would make the API accept tags and silently drop them.

A Phase-1 tag is an **opaque string**: no `Facet:Value` parsing, no exclusivity,
no reserved facets (FLAN-04, next phase).

Audit events are written at the router layer after the service commits (house
idiom — gelato/router.py), never here. Models are imported lazily inside each
function (house idiom — service/_common.py, crumb/service/leads.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import delete, literal, select

from app.modules.flan.service._common import (
    get_project_or_404,
    require_writable_project,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.flan.models import Project
    from app.modules.flan.schemas import ProjectCreate, ProjectUpdate


#: Prefix used when a project name yields no usable prefix at all — an empty
#: name-derived prefix, or one that does not begin with a letter (the schema's
#: KEY_PREFIX_PATTERN requires a leading letter so the prefix is safe to
#: interpolate into the key generator's regex).
DEFAULT_KEY_PREFIX = "PRJ"

#: Number of characters taken from the name when deriving a prefix — "Crisis
#: Simulator" → "CRIS".
KEY_PREFIX_LENGTH = 4

#: Project columns that are NOT NULL: a PATCH carrying an explicit null for one
#: of these is ignored rather than being sent to the database as a constraint
#: violation. Every other project field is nullable, so an explicit null there
#: legitimately clears it.
_NOT_NULL_FIELDS = frozenset({"name", "key_prefix", "currency"})


# ---------------------------------------------------------------------------
# key_prefix derivation (D-V5P1-2)
# ---------------------------------------------------------------------------


def derive_key_prefix(name: str) -> str:
    """
    Derive a project's task-key prefix from its name (D-V5P1-2).

    The first four alphanumeric characters of the name, uppercased: "Crisis
    Simulator" → "CRIS", "R&D 2026" → "RD20". Falls back to `PRJ` when the name
    yields nothing usable — either no alphanumerics at all ("!!!" → "PRJ") or a
    result that does not start with a letter ("3M Widgets" → "3MWI" → "PRJ").

    That second fallback is not cosmetic: the schema validates key_prefix
    against `^[A-Za-z][A-Za-z0-9]{0,9}$` precisely so the key generator can
    interpolate it into a `^{prefix}-[0-9]+$` regex, and a derived prefix must
    honour the same shape a client-supplied one does.

    Pure (no DB) so it is unit-testable in isolation, and used only when the
    client omits key_prefix — a supplied one is stored verbatim.
    """
    derived = "".join(ch for ch in name if ch.isalnum())[:KEY_PREFIX_LENGTH].upper()
    if not derived or not derived[0].isalpha():
        return DEFAULT_KEY_PREFIX
    return derived


# ---------------------------------------------------------------------------
# Tags — the flan_project_tag join table (D-V5P1-5)
# ---------------------------------------------------------------------------


async def _load_tags(db: AsyncSession, project_ids: Sequence[str]) -> dict[str, list[str]]:
    """
    Load the tag sets for a batch of projects in ONE query.

    Returns a dict keyed by project id; **every requested id is present**, an id
    with no tag rows mapping to an empty list, so a caller can index it without
    a fallback. Tags come back sorted, since a join table has no inherent order
    and a stable list makes the API response deterministic.
    """
    from app.modules.flan.models import ProjectTag

    tags: dict[str, list[str]] = {project_id: [] for project_id in project_ids}
    if not tags:
        return tags

    result = await db.execute(
        select(ProjectTag.project_id, ProjectTag.tag)
        .where(ProjectTag.project_id.in_(list(tags)))
        .order_by(ProjectTag.tag)
    )
    for project_id, tag in result.all():
        tags[project_id].append(tag)
    return tags


async def _attach_tags(db: AsyncSession, projects: Sequence[Project]) -> None:
    """
    Attach each project's tag list to the ORM instance as a plain `.tags`
    attribute, in place.

    `flan_project_tag` is a join table with no ORM relationship behind it, so
    nothing populates `Project.tags` on its own — `ProjectRead` declares `tags`
    as a service-filled field and reads it off the instance through
    `from_attributes`. **Every function in this module that returns a project
    calls this**, so tags can never be accepted on the way in and silently
    dropped on the way out. The attribute is not mapped, so it survives
    `commit()`/`refresh()` untouched.
    """
    tags = await _load_tags(db, [project.id for project in projects])
    for project in projects:
        project.tags = tags[project.id]  # type: ignore[attr-defined]


async def _replace_tags(db: AsyncSession, project_id: str, tags: Iterable[str]) -> None:
    """
    Replace a project's whole tag set (D-V5P1-5) — flushed, not committed.

    Full-replacement semantics: the supplied list is the project's complete tag
    set after the call, so the existing rows are deleted first. An empty list is
    valid and clears every tag. The caller decides whether the change commits,
    so tag writes ride in the same transaction as the project write that carried
    them.

    Tags arrive already stripped, non-blank and de-duplicated from the schema
    (`_normalize_tags`), which is what keeps the composite PK `(project_id, tag)`
    from colliding on a payload naming the same tag twice.
    """
    from app.modules.flan.models import ProjectTag

    await db.execute(delete(ProjectTag).where(ProjectTag.project_id == project_id))
    for tag in tags:
        db.add(ProjectTag(project_id=project_id, tag=tag))
    await db.flush()


# ---------------------------------------------------------------------------
# CRUD (FLAN-01.1, FLAN-01.6)
# ---------------------------------------------------------------------------


async def list_projects(db: AsyncSession, include_archived: bool = False) -> list[Project]:
    """
    Return the projects the module lists in its switcher (FLAN-01.6), each with
    its tag list attached.

    Excludes archived (`active=False`) projects unless `include_archived` is
    True — an archived project is retained and readable, it is simply not part
    of the day-to-day list. Ordered by name, then by creation time: duplicate
    names are allowed (FLAN-01.1), so the timestamp is the tiebreak that keeps
    the order stable between reads.
    """
    from app.modules.flan.models import Project

    stmt = select(Project)
    if not include_archived:
        stmt = stmt.where(Project.active.is_(True))
    stmt = stmt.order_by(Project.name.asc(), Project.created_at.asc())

    result = await db.execute(stmt)
    projects = list(result.scalars().all())
    await _attach_tags(db, projects)
    return projects


async def get_project(db: AsyncSession, project_id: str) -> Project:
    """
    Load one project by id, with its tags attached. Raises HTTP 404 if it does
    not exist.

    This is the read path, so it deliberately does **not** care whether the
    project is archived: archiving is a soft delete and an archived project
    keeps all its data and stays readable (FLAN-01.1). Only writes are refused,
    by `require_writable_project`.
    """
    project = await get_project_or_404(db, project_id)
    await _attach_tags(db, [project])
    return project


async def create_project(db: AsyncSession, data: ProjectCreate) -> Project:
    """
    Create a project (FLAN-01.1) and its tag rows, and return it.

    `key_prefix` is taken verbatim when supplied and otherwise derived from the
    name (`derive_key_prefix` — "Crisis Simulator" → "CRIS", "!!!" → "PRJ"),
    per D-V5P1-2.

    **There is no name-uniqueness pre-check, deliberately.** Duplicate project
    names are allowed (FLAN-01.1) — two projects called "Crisis Simulator" are
    two projects, distinguished by their ids — and `flan_project` carries no
    unique constraint on `name` to enforce otherwise.

    The project row and its tag rows are written in ONE transaction: the tags
    are flushed against the project's id before the single commit, so a project
    can never land tagless because a tag insert failed.
    """
    from app.modules.flan.models import Project

    project = Project(
        name=data.name,
        key_prefix=data.key_prefix or derive_key_prefix(data.name),
        category=data.category,
        description=data.description,
        currency=data.currency,
        start_date=data.start_date,
        gate_date=data.gate_date,
    )
    db.add(project)
    await db.flush()

    await _replace_tags(db, project.id, data.tags)

    await db.commit()
    await db.refresh(project)
    await _attach_tags(db, [project])
    return project


async def update_project(db: AsyncSession, project_id: str, data: ProjectUpdate) -> Project:
    """
    Apply a partial update to a project (PATCH semantics) and return it.

    Calls `require_writable_project` first: a 404 if the project is gone, a 422
    if it is archived — an archived project rejects writes (FLAN-01.1).

    `id` cannot be changed: `ProjectUpdate` carries no `id` field at all, so the
    immutability of the project id (FLAN-01.1) is structural rather than a check
    that could be forgotten. `active` is absent for the same reason — archiving
    is its own endpoint.

    **`key_prefix` is refused with a 422 once the project has any task**
    (D-V5P1-2): keys already issued under the old prefix would no longer match
    the project's prefix, leaving `PRJ-9` inside a project that claims `CRIS`.
    It is freely editable while the project is still task-free.

    Only the fields the payload actually SET are written (`exclude_unset`), so
    an omitted field is untouched and an explicit null clears a nullable one; an
    explicit null aimed at a NOT NULL column is ignored rather than turned into
    a database error. Supplying `tags` REPLACES the project's whole tag set;
    omitting them (or sending null) leaves the existing set alone.
    """
    project = await require_writable_project(db, project_id)

    patch = data.model_dump(exclude_unset=True)
    tags = patch.pop("tags", None)

    if "key_prefix" in patch and patch["key_prefix"] is not None:
        if patch["key_prefix"] != project.key_prefix and await _project_has_tasks(db, project_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Project {project_id} already has tasks, so its key prefix "
                    f"({project.key_prefix}) can no longer be changed."
                ),
            )

    for field, value in patch.items():
        if value is None and field in _NOT_NULL_FIELDS:
            continue
        setattr(project, field, value)

    if tags is not None:
        await _replace_tags(db, project_id, tags)

    await db.commit()
    await db.refresh(project)
    await _attach_tags(db, [project])
    return project


async def archive_project(db: AsyncSession, project_id: str) -> Project:
    """
    Archive a project — a SOFT delete (FLAN-01.1). Returns the project.

    Clears `active`; the row keeps every field and stays fully readable through
    `get_project` and `list_projects(include_archived=True)`. What changes is
    that every write inside the project is refused from now on, by
    `require_writable_project` (422) — phase, task, roster and assignment writes
    included, not just writes to the project row.

    **Idempotent**: archiving an already-archived project is a no-op that
    returns the row, so it deliberately does NOT go through
    `require_writable_project` — that guard would 422 the second call, which is
    the one case where refusing a write to an archived project would be wrong.
    Raises HTTP 404 if the project does not exist.
    """
    project = await get_project_or_404(db, project_id)
    project.active = False
    await db.commit()
    await db.refresh(project)
    await _attach_tags(db, [project])
    return project


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _project_has_tasks(db: AsyncSession, project_id: str) -> bool:
    """
    Return whether the project owns at least one task — the D-V5P1-2 key_prefix
    lock.

    `SELECT 1 FROM flan_task WHERE project_id = :id LIMIT 1`: existence only, so
    it stops at the first row instead of counting a project's whole backlog to
    answer a yes/no question.
    """
    from app.modules.flan.models import Task

    result = await db.execute(
        select(literal(1)).where(Task.project_id == project_id).limit(1)
    )
    return result.first() is not None
