"""
PLUM service layer (business logic).

Phase 5: Part CRUD, revision FSM, search/filter, auto-generated part numbers,
and revision label generation.

Part number generation (D-06):
  Numbers follow the series "P00001", "P00002", … using a DB MAX query.
  The unique DB constraint on plum_part.part_number is the real guard against
  duplicates (not application-level locking). On an IntegrityError collision,
  the function retries once with a freshly generated number (RESEARCH Pattern 7).

Revision labels (D-04/D-05):
  ASME scheme: A, B, C, ... (skipping I, O, Q, S, X, Z per ASME Y14.35).
  SemVer scheme: 0.1.0 → 1.0.0 on release; new Draft minor-bumps (1.0.0 → 1.1.0).
  Read from the global plum.revision_scheme setting; defaults to "asme".

Revision FSM (D-07):
  VALID_TRANSITIONS maps each status to the list of allowed target statuses.
  advance_revision_status validates and applies the transition; on →released,
  the prior released revision is auto-obsoleted in the same transaction (D-08).
  Pitfall 3: flush() between the obsolete update and the release update to
  avoid the partial unique index seeing two released rows simultaneously.

Soft-delete (D-11):
  Parts are never hard-deleted. Setting active=False hides from default lists.

Immutability (D-07):
  Released revisions are frozen. update_part raises 422 if revision-controlled
  fields are changed while the current revision is "released".

Server-side search (D-15/PLUM-02):
  list_parts uses parameterized SQLAlchemy .ilike() — never raw-SQL
  interpolation — to satisfy T-05-06 (search threat mitigation).

No ORM relationship access anywhere in this module (MissingGreenlet pitfall).
All queries use explicit select(...) calls.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.modules.plum.models import PlumPart, PlumPartRevision, PlumPartTag
    from app.modules.plum.schemas import PartCreate, PartUpdate, RevisionCreate


# ---------------------------------------------------------------------------
# ASME revision letter constants (D-04)
# ---------------------------------------------------------------------------

ASME_SKIP: set[str] = {"I", "O", "Q", "S", "X", "Z"}
ASME_LETTERS: list[str] = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in ASME_SKIP]

# ---------------------------------------------------------------------------
# Revision FSM transition table (D-07)
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft":     ["in_review"],
    "in_review": ["released", "draft"],
    "released":  ["obsolete"],  # internal only — triggered by supersede (D-08)
    "obsolete":  [],            # terminal — no outgoing transitions
}


# ---------------------------------------------------------------------------
# Part number generation (D-06)
# ---------------------------------------------------------------------------


async def generate_part_number(db: AsyncSession) -> str:
    """
    Generate the next part number in the P##### series.

    Queries MAX(part_number) WHERE part_number LIKE 'P%' to find the current
    highest numeric suffix, then returns the next value zero-padded to 5 digits.
    Returns "P00001" when no P-series part numbers exist yet.

    The DB unique constraint on plum_part.part_number is the authoritative guard;
    this function is a best-effort generator. The caller must handle
    IntegrityError on collision (RESEARCH Pattern 7).
    """
    from app.modules.plum.models import PlumPart

    result = await db.execute(
        select(func.max(PlumPart.part_number)).where(PlumPart.part_number.like("P%"))
    )
    max_pn: str | None = result.scalar()

    if max_pn is None:
        return "P00001"

    # Parse the numeric suffix after "P"
    try:
        suffix = int(max_pn[1:])
    except (IndexError, ValueError):
        suffix = 0

    return f"P{suffix + 1:05d}"


# ---------------------------------------------------------------------------
# Revision scheme helpers (D-04/D-05)
# ---------------------------------------------------------------------------


async def _get_revision_scheme(db: AsyncSession) -> str:
    """
    Read the plum.revision_scheme setting from the global settings table.

    Returns "asme" if the setting is absent (safe default — ASME is the
    initial seed value in seed_plum_data).
    """
    from app.core.settings_model import Setting

    result = await db.execute(
        select(Setting.value).where(Setting.key == "plum.revision_scheme")
    )
    value: str | None = result.scalar()
    return value or "asme"


def _first_revision_label(scheme: str) -> str:
    """
    Return the label for the first revision under the given scheme (D-04).

    ASME: "A" (first letter in the valid alphabet).
    SemVer: "0.1.0" (pre-release initial draft).
    """
    if scheme == "semver":
        return "0.1.0"
    # Default: ASME
    return ASME_LETTERS[0]  # "A"


def _next_draft_label(scheme: str, source_label: str) -> str:
    """
    Return the label for a new Draft revision copied from source_label (D-05).

    ASME: advance to the next letter (skipping ASME_SKIP letters).
      After the last single letter "Y", wraps to "AA", "AB", ...
    SemVer: minor-bump the source label.
      - If source is a release (e.g. "1.0.0"), next draft minor-bumps: "1.1.0".
      - If source is already a draft (e.g. "0.1.0"), minor-bumps: "0.2.0".
      - Patch is reset to 0 on each new draft.
    """
    if scheme == "semver":
        return _semver_minor_bump(source_label)
    # ASME scheme
    return _asme_next_letter(source_label)


def _release_label(scheme: str, current_label: str) -> str:
    """
    Return the label to apply on release of a draft (D-05).

    ASME: label is set at creation; no change on release — return unchanged.
    SemVer: major-bump (zeros rest): "0.1.0" → "1.0.0", "1.1.0" → "2.0.0".
    """
    if scheme == "semver":
        return _semver_major_bump(current_label)
    # ASME: label is set at creation time; unchanged on release
    return current_label


def _asme_next_letter(current_label: str) -> str:
    """Advance to the next ASME letter, wrapping to double-letter after 'Y'."""
    upper = current_label.upper()
    # Simple single-letter case
    if len(upper) == 1:
        if upper in ASME_LETTERS:
            idx = ASME_LETTERS.index(upper)
            if idx + 1 < len(ASME_LETTERS):
                return ASME_LETTERS[idx + 1]
            # Exhausted single letters — wrap to "AA"
            return "AA"
    # Multi-letter — increment last character
    if len(upper) == 2:
        prefix = upper[0]
        last = upper[1]
        if last in ASME_LETTERS:
            idx = ASME_LETTERS.index(last)
            if idx + 1 < len(ASME_LETTERS):
                return prefix + ASME_LETTERS[idx + 1]
            # Advance prefix letter
            if prefix in ASME_LETTERS:
                pidx = ASME_LETTERS.index(prefix)
                if pidx + 1 < len(ASME_LETTERS):
                    return ASME_LETTERS[pidx + 1] + ASME_LETTERS[0]
    # Fallback: append a marker to signal exhaustion (extremely unlikely in v1)
    return upper + ASME_LETTERS[0]


def _semver_minor_bump(label: str) -> str:
    """Minor-bump a SemVer label (zeroes patch)."""
    try:
        parts = label.split(".")
        major = int(parts[0])
        minor = int(parts[1])
        return f"{major}.{minor + 1}.0"
    except (IndexError, ValueError):
        return "0.2.0"


def _semver_major_bump(label: str) -> str:
    """Major-bump a SemVer label (zeroes minor and patch)."""
    try:
        parts = label.split(".")
        major = int(parts[0])
        return f"{major + 1}.0.0"
    except (IndexError, ValueError):
        return "1.0.0"


# ---------------------------------------------------------------------------
# Part CRUD
# ---------------------------------------------------------------------------


async def create_part(db: AsyncSession, data: "PartCreate") -> "PlumPart":
    """
    Insert a new part + auto-create its first Draft revision (D-03).

    If data.part_number is not supplied, auto-generates one via generate_part_number.
    On a unique-constraint IntegrityError:
      - If the caller explicitly supplied a part_number → 409 Conflict.
      - If the part_number was auto-generated (race condition) → retry ONCE.

    First revision is always created in "draft" status with revision_number=1
    and a label derived from the plum.revision_scheme setting. Description and
    other revision-controlled fields are seeded from data (D-03).

    Returns the refreshed PlumPart ORM instance (no revision attached — caller
    must call get_part_with_revisions for the full object, or use the ORM instance
    for list serialization with current_revision_* fields populated separately).
    """
    import sqlalchemy.exc

    from app.modules.plum.models import PlumPart, PlumPartRevision, PlumPartTag

    user_supplied_pn = bool(data.part_number)
    part_number = data.part_number or await generate_part_number(db)

    # Read the revision scheme before any write (avoid extra round-trip after flush)
    scheme = await _get_revision_scheme(db)
    first_label = _first_revision_label(scheme)

    part = PlumPart(
        id=str(uuid.uuid4()),
        part_number=part_number,
        active=True,
    )
    db.add(part)

    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()

        if user_supplied_pn:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Part number '{part_number}' already exists.",
            )

        # Auto-generated collision — retry once with a fresh number
        part_number = await generate_part_number(db)
        part = PlumPart(
            id=str(uuid.uuid4()),
            part_number=part_number,
            active=True,
        )
        db.add(part)
        await db.flush()

    # Auto-create first Draft revision (D-03)
    revision = PlumPartRevision(
        id=str(uuid.uuid4()),
        part_id=part.id,
        revision_number=1,
        revision_label=first_label,
        status="draft",
        description=data.description,
        category=data.category,
        unit_of_measure=data.unit_of_measure,
        notes=data.notes,
        reason_for_revision=data.reason_for_revision,
    )
    db.add(revision)

    # Insert classification tag join rows (D-12)
    for tag_id in data.tag_ids:
        db.add(PlumPartTag(part_id=part.id, tag_id=tag_id))

    await db.commit()
    await db.refresh(part)
    return part


async def list_parts(
    db: AsyncSession,
    q: str | None = None,
    status_filter: str | None = None,
    include_archived: bool = False,
) -> list[dict]:
    """
    Return parts matching the given filters, with current-revision summary fields.

    Args:
        q: Case-insensitive substring search across part_number OR current
           revision description. Uses parameterized .ilike() (T-05-06).
        status_filter: Filter parts whose current (latest by revision_number)
           revision has this status. Implemented as a MAX-based correlated
           subquery (RESEARCH Pattern 4 / PLUM-02).
        include_archived: When False (default), excludes active=False parts.

    Returns a list of dicts shaped for PartRead serialization, including
    current_revision_label, current_revision_status, and tag name list.
    """
    from app.modules.plum.models import PlumClassificationTag, PlumPart, PlumPartRevision, PlumPartTag

    # Subquery: max revision_number per part_id (latest revision)
    latest_rev_sq = (
        select(
            PlumPartRevision.part_id.label("part_id"),
            func.max(PlumPartRevision.revision_number).label("max_rev_num"),
        )
        .group_by(PlumPartRevision.part_id)
        .subquery()
    )

    # Join PlumPart → latest revision
    stmt = (
        select(PlumPart, PlumPartRevision)
        .join(
            latest_rev_sq,
            latest_rev_sq.c.part_id == PlumPart.id,
            isouter=True,
        )
        .join(
            PlumPartRevision,
            (PlumPartRevision.part_id == PlumPart.id)
            & (PlumPartRevision.revision_number == latest_rev_sq.c.max_rev_num),
            isouter=True,
        )
    )

    if not include_archived:
        stmt = stmt.where(PlumPart.active == True)  # noqa: E712

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                PlumPart.part_number.ilike(like),
                PlumPartRevision.description.ilike(like),
            )
        )

    if status_filter:
        stmt = stmt.where(PlumPartRevision.status == status_filter)

    stmt = stmt.order_by(PlumPart.part_number)

    result = await db.execute(stmt)
    rows = result.all()

    # For each part, fetch tag names
    part_ids = [row[0].id for row in rows]
    tag_map: dict[str, list[str]] = {pid: [] for pid in part_ids}

    if part_ids:
        tag_stmt = (
            select(PlumPartTag.part_id, PlumClassificationTag.name)
            .join(PlumClassificationTag, PlumClassificationTag.id == PlumPartTag.tag_id)
            .where(PlumPartTag.part_id.in_(part_ids))
        )
        tag_result = await db.execute(tag_stmt)
        for part_id, tag_name in tag_result.all():
            tag_map[part_id].append(tag_name)

    # Shape results for PartRead serialization (current_revision_* are not ORM cols)
    parts_out = []
    for part, revision in rows:
        parts_out.append(
            {
                "id": part.id,
                "part_number": part.part_number,
                "active": part.active,
                "created_at": part.created_at,
                "updated_at": part.updated_at,
                "current_revision_label": revision.revision_label if revision else None,
                "current_revision_status": revision.status if revision else None,
                "tags": tag_map.get(part.id, []),
            }
        )

    return parts_out


async def get_part(db: AsyncSession, part_id: str) -> "PlumPart":
    """
    Load a part by id.

    Raises HTTP 404 if no part with the given id exists.
    """
    from app.modules.plum.models import PlumPart

    result = await db.execute(select(PlumPart).where(PlumPart.id == part_id))
    part = result.scalars().first()

    if part is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part {part_id} not found",
        )

    return part


async def get_part_with_revisions(db: AsyncSession, part_id: str) -> dict:
    """
    Return the part plus all its revisions ordered newest-first (D-14).

    Shaped for PartDetailRead serialization. Raises 404 if part not found.
    """
    from app.modules.plum.models import PlumClassificationTag, PlumPart, PlumPartRevision, PlumPartTag

    # Load the part (raises 404 if missing)
    part = await get_part(db, part_id)

    # Load all revisions for this part, newest-first (highest revision_number first)
    rev_result = await db.execute(
        select(PlumPartRevision)
        .where(PlumPartRevision.part_id == part_id)
        .order_by(PlumPartRevision.revision_number.desc())
    )
    revisions = list(rev_result.scalars().all())

    # Load tag names for this part
    tag_stmt = (
        select(PlumClassificationTag.name)
        .join(PlumPartTag, PlumPartTag.tag_id == PlumClassificationTag.id)
        .where(PlumPartTag.part_id == part_id)
    )
    tag_result = await db.execute(tag_stmt)
    tag_names = [row[0] for row in tag_result.all()]

    return {
        "id": part.id,
        "part_number": part.part_number,
        "active": part.active,
        "created_at": part.created_at,
        "updated_at": part.updated_at,
        "tags": tag_names,
        "revisions": revisions,
    }


async def update_part(
    db: AsyncSession,
    part_id: str,
    data: "PartUpdate",
) -> dict:
    """
    Apply a partial update to a part (PATCH semantics).

    Part-level fields (part_number, active, tag_ids) are applied to PlumPart /
    PlumPartTag. Revision-controlled fields (description, category, unit_of_measure,
    notes) are applied to the current Draft revision.

    Raises HTTP 422 if revision-controlled fields are supplied and the current
    revision status is "released" (D-07 immutability, T-05-07).
    Raises HTTP 404 if the part does not exist.

    Returns a dict shaped for PartRead (with current_revision_* fields populated).
    """
    from app.modules.plum.models import PlumClassificationTag, PlumPart, PlumPartRevision, PlumPartTag

    part = await get_part(db, part_id)
    update_data = data.model_dump(exclude_unset=True)

    # Separate part-level from revision-controlled fields
    revision_fields = {"description", "category", "unit_of_measure", "notes"}
    part_level_fields = {"part_number", "active"}
    tag_field = "tag_ids"

    rev_updates = {k: v for k, v in update_data.items() if k in revision_fields}

    if rev_updates:
        # Load current (latest) revision to check immutability
        rev_result = await db.execute(
            select(PlumPartRevision)
            .where(PlumPartRevision.part_id == part_id)
            .order_by(PlumPartRevision.revision_number.desc())
        )
        current_rev = rev_result.scalars().first()

        if current_rev and current_rev.status == "released":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot edit revision-controlled fields on a Released revision (D-07).",
            )

        # Apply revision-controlled updates to current Draft revision
        if current_rev:
            for field, value in rev_updates.items():
                setattr(current_rev, field, value)

    # Apply part-level fields
    for field in part_level_fields:
        if field in update_data:
            setattr(part, field, update_data[field])

    # Update tags if provided: replace join-table rows
    if tag_field in update_data:
        # Delete existing tag rows for this part
        existing_tags_result = await db.execute(
            select(PlumPartTag).where(PlumPartTag.part_id == part_id)
        )
        for tag_row in existing_tags_result.scalars().all():
            await db.delete(tag_row)
        # Insert new tag rows
        for tag_id in update_data[tag_field]:
            db.add(PlumPartTag(part_id=part_id, tag_id=tag_id))

    await db.commit()
    await db.refresh(part)

    # Fetch current revision info for PartRead response
    rev_result2 = await db.execute(
        select(PlumPartRevision)
        .where(PlumPartRevision.part_id == part_id)
        .order_by(PlumPartRevision.revision_number.desc())
    )
    current_rev2 = rev_result2.scalars().first()

    # Fetch tag names
    tag_stmt = (
        select(PlumClassificationTag.name)
        .join(PlumPartTag, PlumPartTag.tag_id == PlumClassificationTag.id)
        .where(PlumPartTag.part_id == part_id)
    )
    tag_result = await db.execute(tag_stmt)
    tag_names = [row[0] for row in tag_result.all()]

    return {
        "id": part.id,
        "part_number": part.part_number,
        "active": part.active,
        "created_at": part.created_at,
        "updated_at": part.updated_at,
        "current_revision_label": current_rev2.revision_label if current_rev2 else None,
        "current_revision_status": current_rev2.status if current_rev2 else None,
        "tags": tag_names,
    }


# ---------------------------------------------------------------------------
# Revision service
# ---------------------------------------------------------------------------


async def get_revision(db: AsyncSession, revision_id: str) -> "PlumPartRevision":
    """
    Load a revision by id.

    Raises HTTP 404 if no revision with the given id exists.
    """
    from app.modules.plum.models import PlumPartRevision

    result = await db.execute(
        select(PlumPartRevision).where(PlumPartRevision.id == revision_id)
    )
    revision = result.scalars().first()

    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Revision {revision_id} not found",
        )

    return revision


async def get_released_revision(
    db: AsyncSession, part_id: str
) -> "PlumPartRevision | None":
    """
    Return the currently Released revision for a part, or None if none exists.

    Used in the supersede flow (D-08): when a new revision is released, this
    function finds the prior released revision to obsolete.
    """
    from app.modules.plum.models import PlumPartRevision

    result = await db.execute(
        select(PlumPartRevision).where(
            PlumPartRevision.part_id == part_id,
            PlumPartRevision.status == "released",
        )
    )
    return result.scalars().first()


async def create_revision(
    db: AsyncSession,
    part_id: str,
    data: "RevisionCreate",
    actor_id: str,
) -> "PlumPartRevision":
    """
    Create a new Draft revision for a part (D-03 copy-forward).

    Source resolution order (D-03):
      1. data.source_revision_id if explicitly provided.
      2. Latest Released revision for the part.
      3. Latest overall revision (by revision_number) if no released one exists.

    Copies description, category, unit_of_measure, notes from the source.
    If RevisionCreate provides overrides, they take precedence over the copy.

    revision_number = MAX(existing revision_number for this part) + 1.
    revision_label  = _next_draft_label(scheme, source_label).
    status          = "draft".

    Writes a "revision.created" audit event.
    Returns the new PlumPartRevision ORM instance.
    """
    from app.modules.auth.service import write_audit
    from app.modules.plum.models import PlumPartRevision

    # Verify part exists (raises 404 if not)
    await get_part(db, part_id)

    scheme = await _get_revision_scheme(db)

    # Resolve source revision
    if data.source_revision_id:
        source = await get_revision(db, data.source_revision_id)
        if source.part_id != part_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Revision {data.source_revision_id} does not belong to part {part_id}",
            )
    else:
        # Default: latest Released, fallback to latest overall
        source = await get_released_revision(db, part_id)
        if source is None:
            # No released revision — use latest by revision_number
            latest_result = await db.execute(
                select(PlumPartRevision)
                .where(PlumPartRevision.part_id == part_id)
                .order_by(PlumPartRevision.revision_number.desc())
            )
            source = latest_result.scalars().first()

    # Determine next revision_number
    max_num_result = await db.execute(
        select(func.max(PlumPartRevision.revision_number)).where(
            PlumPartRevision.part_id == part_id
        )
    )
    max_num: int = max_num_result.scalar() or 0
    next_number = max_num + 1

    # Compute next draft label
    source_label = source.revision_label if source else _first_revision_label(scheme)
    next_label = _next_draft_label(scheme, source_label)

    # Copy-forward attributes from source; RevisionCreate fields override if provided
    new_revision = PlumPartRevision(
        id=str(uuid.uuid4()),
        part_id=part_id,
        revision_number=next_number,
        revision_label=next_label,
        status="draft",
        description=data.description if data.description is not None else (source.description if source else ""),
        category=data.category if data.category is not None else (source.category if source else None),
        unit_of_measure=data.unit_of_measure if data.unit_of_measure is not None else (source.unit_of_measure if source else None),
        notes=data.notes if data.notes is not None else (source.notes if source else None),
        reason_for_revision=data.reason_for_revision,
    )
    db.add(new_revision)
    await db.commit()
    await db.refresh(new_revision)

    await write_audit(
        db,
        actor_id=actor_id,
        action="revision.created",
        target_type="revision",
        target_id=str(new_revision.id),
        detail=f"Revision {new_revision.revision_label} created for part {part_id}",
    )

    return new_revision


async def advance_revision_status(
    db: AsyncSession,
    part_id: str,
    revision_id: str,
    target_status: str,
    actor_id: str,
) -> "PlumPartRevision":
    """
    Advance a revision through the FSM (D-07/D-08).

    Validates:
      - Part exists (404 if not).
      - Revision belongs to the part (404 if not).
      - Transition is valid per VALID_TRANSITIONS (422 if not).

    On target_status == "released" (D-08 supersede):
      1. Load prior Released revision (if any).
      2. Set it to "obsolete" + obsoleted_at.
      3. await db.flush() between the two updates (Pitfall 3 — partial unique
         index uq_plum_part_one_released would see two "released" rows without flush).
      4. Write revision.obsoleted audit event for the prior revision.
      5. Set this revision to "released" + released_at.

    Commits the transaction; writes the target-specific audit event.
    Returns the updated PlumPartRevision ORM instance.

    Audit actions per target:
      - "in_review" → "revision.submitted"
      - "released"  → "revision.released"
      - "draft"     → "revision.rejected"  (in_review → draft rejection)
      - "obsolete"  → not exposed via API directly (supersede-only path)
    """
    from app.modules.auth.service import write_audit
    from app.modules.plum.models import PlumPartRevision

    # Verify part exists
    await get_part(db, part_id)

    # Load revision + verify ownership
    revision = await get_revision(db, revision_id)
    if revision.part_id != part_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Revision {revision_id} does not belong to part {part_id}",
        )

    # Validate FSM transition
    allowed = VALID_TRANSITIONS.get(revision.status, [])
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition revision from '{revision.status}' to '{target_status}'. "
                f"Allowed transitions: {allowed}"
            ),
        )

    # Supersede on release (D-08)
    if target_status == "released":
        prior_released = await get_released_revision(db, part_id)
        if prior_released and prior_released.id != revision_id:
            prior_released.status = "obsolete"
            prior_released.obsoleted_at = datetime.now(timezone.utc)
            # Flush before the second update to avoid violating the partial unique
            # index uq_plum_part_one_released (Pitfall 3 from RESEARCH.md)
            await db.flush()
            await write_audit(
                db,
                actor_id=actor_id,
                action="revision.obsoleted",
                target_type="revision",
                target_id=str(prior_released.id),
                detail=f"Superseded by revision {revision.revision_label}",
            )

        # On release, update the label for SemVer scheme (major bump)
        scheme = await _get_revision_scheme(db)
        new_label = _release_label(scheme, revision.revision_label)
        revision.revision_label = new_label
        revision.released_at = datetime.now(timezone.utc)

    # Apply the transition
    revision.status = target_status

    await db.commit()
    await db.refresh(revision)

    # Write the target-specific audit event
    audit_action_map = {
        "in_review": "revision.submitted",
        "released":  "revision.released",
        "draft":     "revision.rejected",
        "obsolete":  "revision.obsoleted",
    }
    audit_action = audit_action_map.get(target_status, f"revision.{target_status}")
    await write_audit(
        db,
        actor_id=actor_id,
        action=audit_action,
        target_type="revision",
        target_id=str(revision_id),
        detail=f"Revision {revision.revision_label} advanced to {target_status}",
    )

    return revision
