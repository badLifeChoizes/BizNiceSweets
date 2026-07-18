# ABOUTME: GELATO bins service — CRUD for storage bins that subdivide a SYERP
# ABOUTME: stock location (GELATO-01). Thin entity module: 404 on missing
# ABOUTME: location, 422 dup-code pre-check, soft archive (active=False), and a
# ABOUTME: list that hides archived bins by default (Partner precedent).
"""GELATO bins service (business logic).

A Bin is a named sub-location inside a SYERP stock location that inventory can be
directed into (putaway). This module owns bin CRUD:

  * create_bin — 404 if the location is missing, 422 dup-code pre-check on the
    (location_id, code) pair (the DB UNIQUE is the backstop), else insert active.
  * update_bin / archive_bin — PATCH description/active; archive is active=False.
  * get_bin — 404 if missing.
  * list_bins — filtered by location, hides archived rows unless asked (mirrors
    syerp/service.list_partners; downstream putaway pickers must not surface
    archived bins).

Per D-V3-9 / D-P10-6 this mirrors syerp/service: a thin entity module with lazy
imports inside functions (SYERP is the hub — never import its model/service layer
at module import time) and one commit per operation. get_location is REUSED from
the SYERP hub, never re-implemented here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.modules.gelato.models import Bin
    from app.modules.gelato.schemas import BinCreate, BinUpdate


# ---------------------------------------------------------------------------
# Bin CRUD (GELATO-01)
# ---------------------------------------------------------------------------


async def create_bin(db: AsyncSession, data: "BinCreate") -> "Bin":
    """
    Insert a new storage bin inside a SYERP stock location.

    Raises HTTP 404 if data.location_id does not name a stock location. Then a
    422 dup-code PRE-CHECK: if a bin with the same (location_id, code) already
    exists this returns a clean 422 rather than surfacing a raw IntegrityError
    (the uq_gelato_bin_location_code UNIQUE is the authoritative backstop —
    mirrors the Partner dup-code guard).

    Returns the refreshed Bin ORM instance (active=True).
    """
    from app.modules.gelato.models import Bin
    from app.modules.syerp.service import get_location

    # 404 if the location this bin would subdivide does not exist.
    await get_location(db, data.location_id)

    # 422 pre-check: a bin with this (location, code) already exists.
    existing = await db.execute(
        select(Bin.id).where(
            Bin.location_id == data.location_id,
            Bin.code == data.code,
        )
    )
    if existing.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Bin code '{data.code}' already exists in location "
                f"{data.location_id}."
            ),
        )

    bin_ = Bin(
        location_id=data.location_id,
        code=data.code,
        description=data.description,
        active=True,
    )
    db.add(bin_)
    await db.commit()
    await db.refresh(bin_)
    return bin_


async def get_bin(db: AsyncSession, bin_id: int) -> "Bin":
    """
    Load a bin by id. Raises HTTP 404 if no bin with the given id exists
    (mirrors syerp/service.get_partner).
    """
    from app.modules.gelato.models import Bin

    bin_ = await db.get(Bin, bin_id)
    if bin_ is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bin {bin_id} not found",
        )
    return bin_


async def update_bin(db: AsyncSession, bin_id: int, data: "BinUpdate") -> "Bin":
    """
    Apply a partial update to a bin (PATCH semantics).

    Only the supplied (set) fields — description and/or active — are written;
    location_id and code are immutable identity. Setting active=False here is the
    same soft-archive as archive_bin. Raises HTTP 404 if the bin does not exist.
    """
    bin_ = await get_bin(db, bin_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(bin_, field, value)

    await db.commit()
    await db.refresh(bin_)
    return bin_


async def archive_bin(db: AsyncSession, bin_id: int) -> "Bin":
    """
    Set a bin's active flag to False (soft-delete / archive) — toggles it out of
    putaway rotation without deleting it. Raises HTTP 404 if the bin does not
    exist (mirrors syerp/service.archive_partner).
    """
    bin_ = await get_bin(db, bin_id)
    bin_.active = False
    await db.commit()
    await db.refresh(bin_)
    return bin_


async def list_bins(
    db: AsyncSession,
    location_id: int,
    include_archived: bool = False,
) -> list["Bin"]:
    """
    Return the bins in one stock location, ordered by code.

    When include_archived is False (default) archived (active=False) bins are
    excluded — downstream putaway pickers must not surface archived bins (mirrors
    syerp/service.list_partners, Pitfall 5).
    """
    from app.modules.gelato.models import Bin

    stmt = select(Bin).where(Bin.location_id == location_id)
    if not include_archived:
        stmt = stmt.where(Bin.active == True)  # noqa: E712
    stmt = stmt.order_by(Bin.code)

    result = await db.execute(stmt)
    return list(result.scalars().all())
