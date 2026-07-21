"""SYERP service — stock location CRUD."""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:

    from app.modules.syerp.models import (
        StockLocation,
    )
    from app.modules.syerp.schemas import (
        StockLocationCreate,
        StockLocationUpdate,
    )


# ---------------------------------------------------------------------------
# Stock location CRUD (Phase 8)
# ---------------------------------------------------------------------------


async def create_location(db: AsyncSession, data: StockLocationCreate) -> StockLocation:
    """
    Insert a new stock location row.

    `name` is the unique key (there is no generated code — StockLocation uses an
    Integer autoincrement PK). Because the name is always caller-supplied, a
    unique-constraint IntegrityError always maps to 409 Conflict (there is no
    auto-generated value to retry, unlike partners/items).

    Returns the refreshed StockLocation ORM instance.
    """
    import sqlalchemy.exc

    from app.modules.syerp.models import StockLocation

    location = StockLocation(name=data.name)
    db.add(location)

    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stock location '{data.name}' already exists.",
        )

    await db.commit()
    await db.refresh(location)
    return location


async def list_locations(
    db: AsyncSession,
    include_archived: bool = False,
) -> list[StockLocation]:
    """
    Return stock locations matching the given filter.

    Args:
        include_archived: When False (default), excludes active=False rows so
            archived locations do not surface in default pickers.

    Returns list ordered by StockLocation.name ascending.
    """
    from app.modules.syerp.models import StockLocation

    stmt = select(StockLocation)

    if not include_archived:
        stmt = stmt.where(StockLocation.active == True)  # noqa: E712

    stmt = stmt.order_by(StockLocation.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_location(db: AsyncSession, location_id: int) -> StockLocation:
    """
    Load a stock location by id.

    Raises HTTP 404 if no location with the given id exists.
    """
    from app.modules.syerp.models import StockLocation

    result = await db.execute(select(StockLocation).where(StockLocation.id == location_id))
    location = result.scalars().first()

    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock location {location_id} not found",
        )

    return location


async def update_location(
    db: AsyncSession,
    location_id: int,
    data: StockLocationUpdate,
) -> StockLocation:
    """
    Apply a partial update to a stock location (PATCH semantics).

    Only non-None fields from data are written. Raises HTTP 404 if the location
    does not exist. A rename that collides with an existing name maps to 409
    Conflict (unique constraint on name).

    Note: archive (active=False) flows through this same PATCH path. The router
    detects the active True→False transition and selects the correct audit
    action string ("location.archived" vs "location.updated").
    """
    import sqlalchemy.exc

    location = await get_location(db, location_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(location, field, value)

    try:
        await db.commit()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stock location '{data.name}' already exists.",
        )

    await db.refresh(location)
    return location
