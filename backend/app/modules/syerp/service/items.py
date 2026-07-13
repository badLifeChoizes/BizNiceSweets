"""SYERP service — inventory item CRUD and code generation."""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, NamedTuple

from fastapi import HTTPException, status
from sqlalchemy import Integer, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.modules.syerp.models import (
        Bill,
        BillLine,
        GLAccount,
        InventoryItem,
        JournalEntry,
        JournalLine,
        Partner,
        PurchaseOrder,
        PurchaseOrderLine,
        StockLocation,
    )
    from app.modules.syerp.schemas import (
        AccountRegisterRead,
        ApAgingReport,
        BalanceSheetReport,
        BillLineCreate,
        BillRead,
        InventoryItemCreate,
        InventoryItemUpdate,
        ItemOnHandRead,
        JournalEntryRead,
        PartnerCreate,
        PartnerUpdate,
        POCreate,
        POLineCreate,
        POLineRead,
        POLineUpdate,
        PORead,
        ProfitLossReport,
        StockLocationCreate,
        StockLocationUpdate,
        TransactionRead,
        TrialBalanceReport,
        UnbilledReceiptRead,
    )


# ---------------------------------------------------------------------------
# Inventory item code generation (Phase 8, Decision 2)
# ---------------------------------------------------------------------------

_ITEM_CODE_RE = re.compile(r"^ITEM-[0-9]+$")


def _next_item_code(existing_codes: "Iterable[str]") -> str:
    """
    Compute the next ITEM-#### code from the set of existing item codes.

    Pure (no DB) so the digit-boundary guarantee is unit-testable in isolation.
    Considers only strictly-numeric ITEM-series codes (matching ``^ITEM-[0-9]+$``),
    selects the *numerically* highest suffix, and returns that value + 1 zero-padded
    to 4 digits. Returns "ITEM-0001" when no ITEM-series codes exist yet.

    The selection is numeric, never lexicographic: given {"ITEM-9", "ITEM-10"} it
    picks 10 (not the lexicographically-larger "ITEM-9") and returns "ITEM-0011".
    A lexicographic MAX would return "ITEM-9" as the max and re-issue "ITEM-0010",
    colliding once the suffix crosses a digit-width boundary — the Phase-7 partner
    defect this generator exists to avoid.
    """
    suffixes = [
        int(code.split("-", 1)[1]) for code in existing_codes if _ITEM_CODE_RE.match(code)
    ]
    if not suffixes:
        return "ITEM-0001"
    return f"ITEM-{max(suffixes) + 1:04d}"


async def generate_item_code(db: AsyncSession) -> str:
    """
    Generate the next inventory item code in the ITEM-#### series (Decision 2).

    Finds the current highest *numeric* suffix among strictly-numeric ITEM-series
    codes (matching ``^ITEM-[0-9]+$``) by casting the digits after "ITEM-" to an
    integer and ordering numerically, then delegates the increment to the pure
    _next_item_code helper. Returns "ITEM-0001" when no ITEM-series codes exist.

    The regex filter MUST precede the cast: a bare cast over ``LIKE 'ITEM-%'``
    would throw on any non-numeric code. ``func.substring(code, 6)`` skips the
    5-character "ITEM-" prefix (Postgres substring is 1-indexed, so position 6
    is the first digit).

    The DB unique constraint on syerp_inventory_item.code is the authoritative
    guard; this function is a best-effort generator. The caller must handle
    IntegrityError on collision (RESEARCH.md Pattern 3).
    """
    from app.modules.syerp.models import InventoryItem

    result = await db.execute(
        select(InventoryItem.code)
        .where(InventoryItem.code.op("~")(r"^ITEM-[0-9]+$"))
        .order_by(cast(func.substring(InventoryItem.code, 6), Integer).desc())
        .limit(1)
    )
    max_code: str | None = result.scalar()

    return _next_item_code([max_code] if max_code is not None else [])


# ---------------------------------------------------------------------------
# Inventory item CRUD (Phase 8)
# ---------------------------------------------------------------------------


def _build_item_kwargs(code: str, data: "InventoryItemCreate") -> dict:
    """Build the InventoryItem constructor kwargs from an InventoryItemCreate schema."""
    return {
        "code": code,
        "name": data.name,
        "unit_of_measure": data.unit_of_measure,
        "plum_part_id": data.plum_part_id,
    }


async def _validate_plum_part(db: AsyncSession, plum_part_id: str | None) -> None:
    """
    Reject a non-existent PLUM part link with a clean 422 (D-P8-2: the PLUM link
    is advisory and must degrade gracefully — never surface as an unhandled FK
    IntegrityError/HTTP 500). A None id (no link) is always valid; the plum_part
    table exists even when the PLUM module is toggled off, so the lookup is safe.
    """
    if plum_part_id is None:
        return

    from app.modules.plum.models import PlumPart

    exists = await db.execute(select(PlumPart.id).where(PlumPart.id == plum_part_id))
    if exists.scalar() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"PLUM part {plum_part_id} does not exist.",
        )


async def create_item(db: AsyncSession, data: "InventoryItemCreate") -> "InventoryItem":
    """
    Insert a new inventory item row.

    If data.code is not supplied, auto-generates one via generate_item_code.
    On a unique-constraint IntegrityError:
      - If the caller explicitly supplied a code → 409 Conflict (duplicate code).
      - If the code was auto-generated (race condition) → retry ONCE with a fresh
        code (RESEARCH.md Pattern 3).

    moving_avg_cost is NOT set here — a new item starts at the model default 0
    and is only recomputed by costed receipts (Task 5).

    Returns the refreshed InventoryItem ORM instance.
    """
    import sqlalchemy.exc

    from app.modules.syerp.models import InventoryItem

    await _validate_plum_part(db, data.plum_part_id)

    user_supplied_code = bool(data.code)
    code = data.code or await generate_item_code(db)

    item = InventoryItem(**_build_item_kwargs(code, data))
    db.add(item)

    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()

        if user_supplied_code:
            # Caller provided an explicit code that already exists → 409 Conflict
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Inventory item code '{code}' already exists.",
            )

        # Auto-generated code collision — retry once with a fresh code
        code = await generate_item_code(db)
        item = InventoryItem(**_build_item_kwargs(code, data))
        db.add(item)
        await db.flush()

    await db.commit()
    await db.refresh(item)
    return item


async def list_items(
    db: AsyncSession,
    q: str | None = None,
    include_archived: bool = False,
) -> list["InventoryItem"]:
    """
    Return inventory items matching the given filters.

    Args:
        q: Case-insensitive substring search across code and name. Uses
           parameterized .ilike() — never raw-SQL interpolation.
        include_archived: When False (default), excludes active=False rows so
            archived items do not surface in default pickers.

    Returns list ordered by InventoryItem.code ascending.
    """
    from app.modules.syerp.models import InventoryItem

    stmt = select(InventoryItem)

    if not include_archived:
        stmt = stmt.where(InventoryItem.active == True)  # noqa: E712

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                InventoryItem.code.ilike(like),
                InventoryItem.name.ilike(like),
            )
        )

    stmt = stmt.order_by(InventoryItem.code)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_item(db: AsyncSession, item_id: str) -> "InventoryItem":
    """
    Load an inventory item by id.

    Raises HTTP 404 if no item with the given id exists.
    """
    from app.modules.syerp.models import InventoryItem

    result = await db.execute(select(InventoryItem).where(InventoryItem.id == item_id))
    item = result.scalars().first()

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item {item_id} not found",
        )

    return item


async def update_item(
    db: AsyncSession,
    item_id: str,
    data: "InventoryItemUpdate",
) -> "InventoryItem":
    """
    Apply a partial update to an inventory item (PATCH semantics).

    Only non-None fields from data are written. Raises HTTP 404 if the item
    does not exist.

    Note: archive (active=False) flows through this same PATCH path. The router
    detects the active True→False transition and selects the correct audit
    action string ("item.archived" vs "item.updated").
    """
    item = await get_item(db, item_id)

    update_data = data.model_dump(exclude_unset=True)
    if "plum_part_id" in update_data:
        await _validate_plum_part(db, update_data["plum_part_id"])
    for field, value in update_data.items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return item
