"""
SYERP service layer (business logic).

Phase 4: Partner CRUD, search/filter, soft-delete, auto-generated partner codes,
and GL account list helper.

Partner code generation (D-04):
  Codes follow the series "P-0001", "P-0002", … using a DB MAX query.
  The unique DB constraint on syerp_partner.code is the real guard against
  duplicates (not application-level locking). On an IntegrityError collision,
  the function retries once with a freshly generated code (RESEARCH.md Pattern 3).

Soft-delete (D-05):
  Partners are never hard-deleted. Setting active=False hides a partner from
  the default list endpoint. This preserves FK integrity for downstream
  modules (PLUM AVL, MOUSSE POs) that reference partners by id.

Server-side search (D-07):
  list_partners uses parameterized SQLAlchemy .ilike() — never raw-SQL
  interpolation — to satisfy T-04-04 (ilike search threat mitigation).

The default list excludes archived rows so Phase 6 AVL pickers do not surface
archived vendors (Pitfall 5 from RESEARCH.md).
"""
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
        StockLocationCreate,
        StockLocationUpdate,
        TransactionRead,
    )


# ---------------------------------------------------------------------------
# Partner code generation (D-04)
# ---------------------------------------------------------------------------


async def generate_partner_code(db: AsyncSession) -> str:
    """
    Generate the next partner code in the P-#### series.

    Queries MAX(code) WHERE code LIKE 'P-%' to find the current highest
    numeric suffix, then returns the next value zero-padded to 4 digits.
    Returns "P-0001" when no P-series codes exist yet.

    The DB unique constraint on syerp_partner.code is the authoritative guard;
    this function is a best-effort generator. The caller must handle
    IntegrityError on collision (RESEARCH.md Pattern 3).
    """
    from sqlalchemy import func

    from app.modules.syerp.models import Partner

    result = await db.execute(
        select(func.max(Partner.code)).where(Partner.code.like("P-%"))
    )
    max_code: str | None = result.scalar()

    if max_code is None:
        return "P-0001"

    # Parse the numeric suffix after "P-"
    try:
        suffix = int(max_code.split("-", 1)[1])
    except (IndexError, ValueError):
        suffix = 0

    return f"P-{suffix + 1:04d}"


# ---------------------------------------------------------------------------
# Partner CRUD
# ---------------------------------------------------------------------------


def _build_partner_kwargs(code: str, data: "PartnerCreate") -> dict:
    """Build the Partner constructor kwargs from a PartnerCreate schema."""
    return {
        "code": code,
        "name": data.name,
        "is_vendor": data.is_vendor,
        "is_customer": data.is_customer,
        "addr_line1": data.addr_line1,
        "addr_line2": data.addr_line2,
        "addr_city": data.addr_city,
        "addr_state": data.addr_state,
        "addr_postal": data.addr_postal,
        "addr_country": data.addr_country,
        "contact_name": data.contact_name,
        "contact_email": data.contact_email,
        "contact_phone": data.contact_phone,
        "payment_terms": data.payment_terms,
        "tax_id": data.tax_id,
        "currency": data.currency,
        "country_of_origin": data.country_of_origin,
        "notes": data.notes,
    }


async def create_partner(db: AsyncSession, data: "PartnerCreate") -> "Partner":
    """
    Insert a new partner row.

    If data.code is not supplied, auto-generates one via generate_partner_code.
    On a unique-constraint IntegrityError:
      - If the caller explicitly supplied a code → 409 Conflict (duplicate code).
      - If the code was auto-generated (race condition) → retry ONCE with a fresh
        code (RESEARCH.md Pattern 3).

    Returns the refreshed Partner ORM instance.
    """
    import sqlalchemy.exc

    from app.modules.syerp.models import Partner

    user_supplied_code = bool(data.code)
    code = data.code or await generate_partner_code(db)

    partner = Partner(**_build_partner_kwargs(code, data))
    db.add(partner)

    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()

        if user_supplied_code:
            # Caller provided an explicit code that already exists → 409 Conflict
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Partner code '{code}' already exists.",
            )

        # Auto-generated code collision — retry once with a fresh code
        code = await generate_partner_code(db)
        partner = Partner(**_build_partner_kwargs(code, data))
        db.add(partner)
        await db.flush()

    await db.commit()
    await db.refresh(partner)
    return partner


async def list_partners(
    db: AsyncSession,
    role: str | None = None,
    q: str | None = None,
    include_archived: bool = False,
) -> list["Partner"]:
    """
    Return partners matching the given filters.

    Args:
        role: "vendor" → is_vendor=True only; "customer" → is_customer=True only.
        q: Case-insensitive substring search across name, code, contact_name.
           Uses parameterized .ilike() — never raw-SQL interpolation (T-04-04).
        include_archived: When False (default), excludes active=False rows.
            This is intentional — downstream pickers (Phase 6 AVL) must not
            surface archived vendors (Pitfall 5 in RESEARCH.md).

    Returns list ordered by Partner.name ascending.
    """
    from app.modules.syerp.models import Partner

    stmt = select(Partner)

    if not include_archived:
        stmt = stmt.where(Partner.active == True)  # noqa: E712

    if role == "vendor":
        stmt = stmt.where(Partner.is_vendor == True)  # noqa: E712
    elif role == "customer":
        stmt = stmt.where(Partner.is_customer == True)  # noqa: E712

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Partner.name.ilike(like),
                Partner.code.ilike(like),
                Partner.contact_name.ilike(like),
            )
        )

    stmt = stmt.order_by(Partner.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_partner(db: AsyncSession, partner_id: str) -> "Partner":
    """
    Load a partner by id.

    Raises HTTP 404 if no partner with the given id exists (mirrors auth service).
    """
    from app.modules.syerp.models import Partner

    result = await db.execute(select(Partner).where(Partner.id == partner_id))
    partner = result.scalars().first()

    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partner {partner_id} not found",
        )

    return partner


async def update_partner(
    db: AsyncSession,
    partner_id: str,
    data: "PartnerUpdate",
) -> "Partner":
    """
    Apply a partial update to a partner (PATCH semantics).

    Only non-None fields from data are written. Raises HTTP 404 if the
    partner does not exist.

    Note: archive action (active=False) flows through this same PATCH endpoint
    (RESEARCH.md Pattern 4). The router detects the active True→False transition
    and selects the correct audit action string ("partner.archived" vs
    "partner.updated").
    """
    partner = await get_partner(db, partner_id)

    # Apply only the provided (non-None) fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(partner, field, value)

    await db.commit()
    await db.refresh(partner)
    return partner


async def archive_partner(db: AsyncSession, partner_id: str) -> "Partner":
    """
    Set a partner's active flag to False (soft-delete / archive).

    Convenience alias used when the router detects an explicit archive intent.
    Raises HTTP 404 if the partner does not exist.
    """
    partner = await get_partner(db, partner_id)
    partner.active = False
    await db.commit()
    await db.refresh(partner)
    return partner


# ---------------------------------------------------------------------------
# Stock location CRUD (Phase 8)
# ---------------------------------------------------------------------------


async def create_location(db: AsyncSession, data: "StockLocationCreate") -> "StockLocation":
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
) -> list["StockLocation"]:
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


async def get_location(db: AsyncSession, location_id: int) -> "StockLocation":
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
    data: "StockLocationUpdate",
) -> "StockLocation":
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


# ---------------------------------------------------------------------------
# GL account list
# ---------------------------------------------------------------------------


async def list_gl_accounts(db: AsyncSession) -> list["GLAccount"]:
    """
    Return all GL accounts ordered by code.

    Read-only in Phase 4 (D-11 scope guard). Seeded at startup by
    app.modules.syerp.coa_seed.seed_gl_accounts().
    """
    from app.modules.syerp.models import GLAccount

    result = await db.execute(select(GLAccount).order_by(GLAccount.code))
    return list(result.scalars().all())


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


# ---------------------------------------------------------------------------
# On-hand & valuation reads (Phase 8, Task 4)
# ---------------------------------------------------------------------------
#
# On-hand is a DERIVED aggregate (AC10-3): it is ALWAYS computed as the signed
# SUM(InventoryTxn.quantity) grouped by location — there is no stored quantity
# column to read. Value uses the item's moving_avg_cost (AC10-5). All arithmetic
# is Decimal (fixed-point), never float (D-11).
#
# Zero-net policy (documented choice): a location whose signed transactions net
# to exactly zero is OMITTED from the per-location rows and does not contribute
# to the grand total. Only locations currently holding stock (nonzero net) are
# returned. This keeps the on-hand view a picture of *where stock actually is*.


def _derive_onhand(
    location_rows: "Iterable[tuple[int, str, Decimal]]",
    moving_avg_cost: Decimal,
) -> "tuple[list[tuple[int, str, Decimal]], Decimal, Decimal]":
    """
    Pure valuation core for on-hand derivation (no DB — unit-testable).

    Given per-location (location_id, location_name, net_quantity) rows and an
    item's moving-average unit cost, returns:
      - the subset of rows with a NONZERO net quantity (zero-net locations
        omitted — documented policy above),
      - the grand-total quantity summed across those nonzero rows,
      - the on-hand value = grand_total_qty * moving_avg_cost.

    All sums/products are Decimal so there is no float drift: e.g. summing
    Decimal("0.1") three times yields exactly Decimal("0.3"). The grand total
    seeds from Decimal("0") so an item with no movements returns Decimal("0"),
    not an int.
    """
    nonzero = [(lid, name, qty) for lid, name, qty in location_rows if qty != 0]
    total_qty = sum((qty for _, _, qty in nonzero), Decimal("0"))
    value = total_qty * moving_avg_cost
    return nonzero, total_qty, value


async def get_item_onhand(db: AsyncSession, item_id: str) -> "ItemOnHandRead":
    """
    Return the derived on-hand-by-location + valuation for an inventory item.

    On-hand is derived, never stored (AC10-3):
      select(txn.location_id, StockLocation.name, func.sum(txn.quantity))
        .join(StockLocation).where(item_id==).group_by(location_id, name)

    The per-location rows carry the signed SUM of every InventoryTxn.quantity
    for the item at that location (positive receipts + negative issues). Value
    is grand_total_qty * item.moving_avg_cost (AC10-5), computed in Decimal.

    Zero-net locations are omitted (see module note above). Raises HTTP 404 if
    the item does not exist (mirrors get_item).
    """
    from app.modules.syerp.models import InventoryTxn, StockLocation
    from app.modules.syerp.schemas import ItemOnHandRead, OnHandByLocation

    item = await get_item(db, item_id)

    stmt = (
        select(
            InventoryTxn.location_id,
            StockLocation.name,
            func.sum(InventoryTxn.quantity),
        )
        .join(StockLocation, StockLocation.id == InventoryTxn.location_id)
        .where(InventoryTxn.item_id == item_id)
        .group_by(InventoryTxn.location_id, StockLocation.name)
        .order_by(StockLocation.name)
    )
    result = await db.execute(stmt)
    location_rows = [(lid, name, qty) for lid, name, qty in result.all()]

    nonzero, total_qty, value = _derive_onhand(location_rows, item.moving_avg_cost)

    return ItemOnHandRead(
        item_id=item.id,
        moving_avg_cost=item.moving_avg_cost,
        locations=[
            OnHandByLocation(location_id=lid, location_name=name, quantity=qty)
            for lid, name, qty in nonzero
        ],
        total_quantity=total_qty,
        onhand_value=value,
    )


async def list_item_transactions(db: AsyncSession, item_id: str) -> "list[TransactionRead]":
    """
    Return an item's inventory-ledger rows, newest-first (Task 11 read half).

    Thin read-only projection over the append-only InventoryTxn ledger (AC10-4):
    each row is joined to its StockLocation for the human-readable location name.
    Ordered by created_at DESC, then id DESC for a stable tie-break (a transfer
    posts two rows sharing a timestamp).

    Raises HTTP 404 if the item does not exist (mirrors get_item).
    """
    from app.modules.syerp.models import InventoryTxn, StockLocation
    from app.modules.syerp.schemas import TransactionRead

    await get_item(db, item_id)

    stmt = (
        select(InventoryTxn, StockLocation.name)
        .join(StockLocation, StockLocation.id == InventoryTxn.location_id)
        .where(InventoryTxn.item_id == item_id)
        .order_by(InventoryTxn.created_at.desc(), InventoryTxn.id.desc())
    )
    result = await db.execute(stmt)

    return [
        TransactionRead(
            id=txn.id,
            item_id=txn.item_id,
            location_id=txn.location_id,
            location_name=name,
            txn_type=txn.txn_type,
            quantity=txn.quantity,
            unit_cost=txn.unit_cost,
            reason=txn.reason,
            created_at=txn.created_at,
        )
        for txn, name in result.all()
    ]


# ---------------------------------------------------------------------------
# Costed receipts + moving-average recompute (Phase 8, Task 5, AC10-5)
# ---------------------------------------------------------------------------
#
# The moving average is ITEM-LEVEL, not per-location (D-11): the cost of a unit
# does not depend on which shelf it sits on. So a receipt weights the NEW unit
# cost against the item's TOTAL on-hand across ALL locations.
#
# All arithmetic is Decimal (fixed-point), never float. A non-terminating
# quotient (e.g. dividing by 3) is quantized to scale 6 with ROUND_HALF_UP so
# the result is deterministic and matches the moving_avg_cost Numeric(18,6)
# column exactly — drift here is the phase's earliest failure sign.

# Scale-6 quantum matching moving_avg_cost / unit_cost Numeric(18,6).
_COST_QUANTUM = Decimal("0.000001")


def compute_new_moving_avg(
    qty_before: Decimal,
    avg_before: Decimal,
    qty_recv: Decimal,
    unit_cost: Decimal,
) -> Decimal:
    """
    Recompute the item-level moving-average unit cost after a costed receipt.

    PURE (no DB, no float) so the valuation core is unit-testable in isolation.

    Weighted formula (AC10-5, D-11):
        avg_new = (qty_before * avg_before + qty_recv * unit_cost)
                  / (qty_before + qty_recv)

    First receipt (qty_before == 0) short-circuits to `unit_cost` — there is no
    prior stock to weight against, and this avoids any division-by-zero edge.
    (The general formula also collapses to unit_cost when qty_before is 0, since
    qty_recv is always > 0; the explicit guard just makes that intent obvious.)

    The quotient is quantized to scale 6 (Decimal("0.000001")) with ROUND_HALF_UP
    so non-terminating results (e.g. 20/15 → 1.333333) are deterministic and fit
    the Numeric(18,6) column with no float drift.
    """
    if qty_before == 0:
        new_avg = unit_cost
    else:
        new_avg = (qty_before * avg_before + qty_recv * unit_cost) / (qty_before + qty_recv)
    return new_avg.quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Journal-entry balance helpers (Phase 9a — GL posting engine, SYERP-12)
# ---------------------------------------------------------------------------
#
# Double-entry invariant (D-P9a): a journal entry posts only when its debits
# equal its credits. These helpers are PURE (no DB, no float, no FastAPI) so the
# balance core is unit-testable in isolation; the service layer raises HTTP 422
# on top of `_je_is_balanced`. All money is Decimal quantized to scale 6 to match
# the Numeric(18,6) amount columns exactly (D-11) — a float sum could drift a
# cent off a "balanced" entry and silently corrupt the ledger.
#
# Lines are duck-typed: each may be a mapping ({"debit": ..., "credit": ...}) or
# any object exposing `.debit`/`.credit`. Exactly one side is set per line; the
# other is None (or 0). Amounts are quantized to `_COST_QUANTUM` before summing.


def _je_side(line: "object", side: str) -> Decimal:
    """
    Read one side (``"debit"`` or ``"credit"``) off a journal line.

    Accepts both a mapping (``line["debit"]``) and an attribute-bearing object
    (``line.debit``). A missing / ``None`` value means "not this side" and reads
    as ``Decimal("0")``. The raw value is coerced through ``str`` before
    ``Decimal`` so an accidental float can never seed float drift into the sum.
    """
    if isinstance(line, Mapping):
        value = line.get(side)
    else:
        value = getattr(line, side, None)
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP)


def _je_totals(lines: "Iterable[object]") -> tuple[Decimal, Decimal]:
    """
    Sum (Σdebits, Σcredits) across journal lines, quantized to scale 6 (D-11).

    PURE (no DB, no float). Each line contributes its debit to the first total
    and its credit to the second; an unset side contributes zero.
    """
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for line in lines:
        total_debit += _je_side(line, "debit")
        total_credit += _je_side(line, "credit")
    return (
        total_debit.quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP),
        total_credit.quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP),
    )


def _je_is_balanced(lines: "Iterable[object]") -> bool:
    """
    Return whether a journal entry is a valid, balanced double-entry (D-P9a).

    Balanced means ALL of:
      * at least two lines (a single-sided entry cannot balance),
      * every line sets EXACTLY ONE of debit/credit (the other None/absent),
      * every set amount is >= 0 (no negative sides — a negative debit is a
        credit and must be expressed as one), and
      * Σdebits == Σcredits (quantized to scale 6).

    PURE (no DB, no float, no FastAPI). The service layer maps a ``False`` here
    to HTTP 422; this helper only decides truth.
    """
    line_list = list(lines)
    if len(line_list) < 2:
        return False
    for line in line_list:
        debit = _je_side(line, "debit")
        credit = _je_side(line, "credit")
        if debit < 0 or credit < 0:
            return False
        # Exactly one side must be non-zero (XOR): never both, never neither.
        if (debit != 0) == (credit != 0):
            return False
    total_debit, total_credit = _je_totals(line_list)
    return total_debit == total_credit


def _reverse_lines(lines: "Iterable[object]") -> list[dict]:
    """
    Reverse a set of journal lines by swapping debit <-> credit (D-P9a).

    Returns new line dicts (``{"debit": ..., "credit": ...}``) — the source lines
    are never mutated. A reversal of a balanced entry is itself balanced (the two
    column sums merely trade places), which is the property the audit-safe void /
    correction path relies on. Amounts are quantized to scale 6 (D-11).
    """
    reversed_lines: list[dict] = []
    for line in lines:
        reversed_lines.append(
            {
                "debit": _je_side(line, "credit"),
                "credit": _je_side(line, "debit"),
            }
        )
    return reversed_lines


async def post_receipt(
    db: AsyncSession,
    item_id: str,
    location_id: int,
    qty: Decimal,
    unit_cost: Decimal,
    actor_id: str,
    source_type: str | None = None,
    source_id: str | None = None,
    commit: bool = True,
) -> "TransactionRead":
    """
    Post a costed receipt: append one ledger row and recompute the moving average.

    In a single transaction (AC10-4,5,7,8):
      1. Derive `qty_before` = the item's TOTAL on-hand across ALL locations
         (SUM of every InventoryTxn.quantity for the item) — the moving average
         is item-level, not per-location.
      2. Compute the new item-level moving average via compute_new_moving_avg.
      3. Append ONE immutable `receipt` InventoryTxn (positive signed quantity,
         unit_cost set, actor + optional source link).
      4. Update item.moving_avg_cost to the recomputed value.

    Rejects qty <= 0 or unit_cost < 0 with 422 (mirrors the ReceiptCreate schema
    guard; defends the service against non-HTTP callers too). Raises 404 if the
    item or location does not exist (via get_item / get_location).

    `commit` (default True) controls whether this function commits the unit of
    work itself. Standalone receipt posting commits (True). PO-driven receiving
    (Task 17, receive_line) passes commit=False so the receipt row, the
    moving-average update, the line's qty_received increment, and the PO status
    roll-up all land in ONE atomic transaction — the shared write is flushed (so
    the row + PK/timestamp exist for the refresh) but the single commit is owned
    by receive_line. This is the "one commit at the end" refactor that guarantees
    a receipt can never be persisted without its accumulator bump.

    Returns the created row as a TransactionRead (joined location name), mirroring
    list_item_transactions. The router writes the inventory.receipt audit row.
    """
    from app.modules.syerp.models import InventoryTxn
    from app.modules.syerp.schemas import TransactionRead

    if qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Receipt quantity must be greater than zero.",
        )
    if unit_cost < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Receipt unit cost must not be negative.",
        )

    # 404s if either does not exist (mirrors get_item / get_location).
    item = await get_item(db, item_id)
    location = await get_location(db, location_id)

    # qty_before = total on-hand across ALL locations (item-level average).
    result = await db.execute(
        select(func.sum(InventoryTxn.quantity)).where(InventoryTxn.item_id == item_id)
    )
    qty_before: Decimal = result.scalar() or Decimal("0")

    avg_new = compute_new_moving_avg(qty_before, item.moving_avg_cost, qty, unit_cost)

    txn = InventoryTxn(
        item_id=item_id,
        location_id=location_id,
        txn_type="receipt",
        quantity=qty,
        unit_cost=unit_cost,
        actor_id=actor_id,
        source_type=source_type,
        source_id=source_id,
    )
    db.add(txn)
    item.moving_avg_cost = avg_new

    # commit=True: standalone receipt owns the commit. commit=False: caller
    # (receive_line) owns a single atomic commit; flush so the row + PK/timestamp
    # exist for the refresh below without ending the transaction.
    if commit:
        await db.commit()
    else:
        await db.flush()
    await db.refresh(txn)

    return TransactionRead(
        id=txn.id,
        item_id=txn.item_id,
        location_id=txn.location_id,
        location_name=location.name,
        txn_type=txn.txn_type,
        quantity=txn.quantity,
        unit_cost=txn.unit_cost,
        reason=txn.reason,
        created_at=txn.created_at,
    )


# ---------------------------------------------------------------------------
# Stock adjustments (Phase 8, Task 6, AC10-6, D-P8-7)
# ---------------------------------------------------------------------------
#
# An adjustment corrects an item's on-hand at ONE location by a SIGNED delta.
# A negative delta covers the manual write-off / "issue" case in v2.0 — the
# `issue` txn_type stays RESERVED for MOUSSE, so manual stock-out is posted as
# a negative `adjustment` here.
#
# Negative-stock guard is PER-LOCATION (D-P8-7): a delta may not drive that
# location's on-hand below zero. On-hand is derived (AC10-3), so the guard sums
# the item's signed txn quantities AT the given location and checks
# current_loc_onhand + qty_delta >= 0. Adjustments NEVER move moving_avg_cost —
# only receipts do (AC10-5); positive adjustments add stock at the current
# average, leaving the average unchanged.


def _adjustment_violates_floor(current_loc_onhand: Decimal, qty_delta: Decimal) -> bool:
    """
    Pure per-location negative-stock predicate (no DB — unit-testable).

    Returns True when applying `qty_delta` to the current location on-hand would
    drive it below zero (`current_loc_onhand + qty_delta < 0`), i.e. the
    adjustment must be REJECTED (AC10-6, D-P8-7). A delta that lands exactly on
    zero is allowed (it empties the location, which is valid). All arithmetic is
    Decimal so the boundary is exact with no float drift.
    """
    return current_loc_onhand + qty_delta < 0


async def post_adjustment(
    db: AsyncSession,
    item_id: str,
    location_id: int,
    qty_delta: Decimal,
    reason: str,
    actor_id: str,
) -> "TransactionRead":
    """
    Post a stock adjustment: append one signed `adjustment` ledger row.

    In a single transaction (AC10-4,6; D-P8-7):
      1. Derive `current_loc_onhand` = the item's on-hand AT `location_id`
         (SUM of that item's InventoryTxn.quantity WHERE location_id matches).
      2. Reject with 422 if the resulting location on-hand
         (`current_loc_onhand + qty_delta`) would be < 0 — NO row is appended
         (per-location negative-stock guard, _adjustment_violates_floor).
      3. Append ONE immutable `adjustment` InventoryTxn with the SIGNED
         `qty_delta`, no unit_cost, the `reason`, and the actor.

    The item's moving_avg_cost is deliberately left UNTOUCHED — only costed
    receipts move the average (AC10-5); a positive adjustment adds quantity at
    the current average. Raises 404 if the item or location does not exist (via
    get_item / get_location). The 422 status mirrors the receipt guard.

    Returns the created row as a TransactionRead (joined location name). The
    router writes the inventory.adjustment audit row.
    """
    from app.modules.syerp.models import InventoryTxn
    from app.modules.syerp.schemas import TransactionRead

    # 404s if either does not exist (mirrors get_item / get_location).
    item = await get_item(db, item_id)  # noqa: F841 — loaded to 404 on missing item
    location = await get_location(db, location_id)

    # Per-location on-hand: signed SUM of this item's txns AT this location.
    result = await db.execute(
        select(func.sum(InventoryTxn.quantity)).where(
            InventoryTxn.item_id == item_id,
            InventoryTxn.location_id == location_id,
        )
    )
    current_loc_onhand: Decimal = result.scalar() or Decimal("0")

    if _adjustment_violates_floor(current_loc_onhand, qty_delta):
        # Reject BEFORE any mutation — no row is appended on rejection.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Adjustment of {qty_delta} would drive location {location_id} "
                f"on-hand below zero (current {current_loc_onhand})."
            ),
        )

    txn = InventoryTxn(
        item_id=item_id,
        location_id=location_id,
        txn_type="adjustment",
        quantity=qty_delta,
        unit_cost=None,
        actor_id=actor_id,
        reason=reason,
    )
    db.add(txn)
    # moving_avg_cost is intentionally NOT touched — only receipts move it (AC10-5).

    await db.commit()
    await db.refresh(txn)

    return TransactionRead(
        id=txn.id,
        item_id=txn.item_id,
        location_id=txn.location_id,
        location_name=location.name,
        txn_type=txn.txn_type,
        quantity=txn.quantity,
        unit_cost=txn.unit_cost,
        reason=txn.reason,
        created_at=txn.created_at,
    )


# ---------------------------------------------------------------------------
# Stock transfers (Phase 8, Task 7, AC10-6)
# ---------------------------------------------------------------------------
#
# A transfer moves quantity between two locations WITHOUT changing the item's
# total on-hand or its moving-average cost (transfers never move the average —
# only receipts do, AC10-5). It is recorded as TWO paired InventoryTxn legs that
# share a freshly-generated transfer_group_id (AC10-4): a `-qty` leg at the source
# location and a `+qty` leg at the destination, both txn_type='transfer', both
# valued at the item's CURRENT moving_avg_cost. The signed pair nets to exactly
# zero, so total item on-hand is unchanged and per-location on-hand shifts.
#
# The source-underflow guard is the SAME per-location floor as adjustments: the
# `-qty` leg must not drive the source location's on-hand below zero. That is
# exactly _adjustment_violates_floor(current_from_onhand, -qty) — the source leg
# IS a negative adjustment of the source location (current_from_onhand - qty < 0
# ⟺ current_from_onhand < qty). Reusing the predicate keeps the floor semantics
# identical to Task 6 (D-P8-7).


async def post_transfer(
    db: AsyncSession,
    item_id: str,
    from_location_id: int,
    to_location_id: int,
    qty: Decimal,
    actor_id: str,
) -> "list[TransactionRead]":
    """
    Post a stock transfer: append the two paired `transfer` ledger legs.

    In a single transaction (AC10-4,6; D-P8-7):
      1. Reject with 422 if from_location_id == to_location_id (a self-transfer is
         a no-op) or qty <= 0 (a transfer is a positive movement) — NO rows.
      2. Derive `current_from_onhand` = the item's on-hand AT from_location_id
         (SUM of that item's InventoryTxn.quantity WHERE location_id matches).
      3. Reject with 422 if the `-qty` leg would drive the source location on-hand
         below zero (over-draw, _adjustment_violates_floor(from_onhand, -qty)) —
         NO rows are appended.
      4. Append EXACTLY TWO immutable `transfer` InventoryTxn rows sharing a fresh
         transfer_group_id: `-qty` at from_location_id, `+qty` at to_location_id,
         both valued at the item's CURRENT moving_avg_cost.

    The signed pair nets to zero, so total item on-hand is unchanged; the item's
    moving_avg_cost is deliberately left UNTOUCHED (only receipts move it, AC10-5).
    Raises 404 if the item or either location does not exist (via get_item /
    get_location). The 422 status mirrors the receipt/adjustment guards.

    Returns the two created rows as TransactionRead (joined location names), out
    leg first then in leg. The router writes the inventory.transfer audit row.
    """
    import uuid

    from app.modules.syerp.models import InventoryTxn
    from app.modules.syerp.schemas import TransactionRead

    if from_location_id == to_location_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transfer source and destination locations must differ.",
        )
    if qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transfer quantity must be greater than zero.",
        )

    # 404s if the item or either location does not exist.
    item = await get_item(db, item_id)
    from_location = await get_location(db, from_location_id)
    to_location = await get_location(db, to_location_id)

    # Per-location source on-hand: signed SUM of this item's txns AT the source.
    result = await db.execute(
        select(func.sum(InventoryTxn.quantity)).where(
            InventoryTxn.item_id == item_id,
            InventoryTxn.location_id == from_location_id,
        )
    )
    current_from_onhand: Decimal = result.scalar() or Decimal("0")

    # The `-qty` source leg is a negative adjustment of the source location, so the
    # over-draw guard is the same per-location floor (current_from_onhand - qty < 0
    # ⟺ current_from_onhand < qty). Reject BEFORE any mutation — no rows on reject.
    if _adjustment_violates_floor(current_from_onhand, -qty):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Transfer of {qty} exceeds location {from_location_id} on-hand "
                f"(current {current_from_onhand})."
            ),
        )

    # Both legs share one freshly-generated group id and the CURRENT average cost.
    transfer_group_id = str(uuid.uuid4())
    unit_cost = item.moving_avg_cost

    out_leg = InventoryTxn(
        item_id=item_id,
        location_id=from_location_id,
        txn_type="transfer",
        quantity=-qty,
        unit_cost=unit_cost,
        actor_id=actor_id,
        transfer_group_id=transfer_group_id,
    )
    in_leg = InventoryTxn(
        item_id=item_id,
        location_id=to_location_id,
        txn_type="transfer",
        quantity=qty,
        unit_cost=unit_cost,
        actor_id=actor_id,
        transfer_group_id=transfer_group_id,
    )
    db.add(out_leg)
    db.add(in_leg)
    # moving_avg_cost is intentionally NOT touched — only receipts move it (AC10-5).

    await db.commit()
    await db.refresh(out_leg)
    await db.refresh(in_leg)

    return [
        TransactionRead(
            id=out_leg.id,
            item_id=out_leg.item_id,
            location_id=out_leg.location_id,
            location_name=from_location.name,
            txn_type=out_leg.txn_type,
            quantity=out_leg.quantity,
            unit_cost=out_leg.unit_cost,
            reason=out_leg.reason,
            created_at=out_leg.created_at,
        ),
        TransactionRead(
            id=in_leg.id,
            item_id=in_leg.item_id,
            location_id=in_leg.location_id,
            location_name=to_location.name,
            txn_type=in_leg.txn_type,
            quantity=in_leg.quantity,
            unit_cost=in_leg.unit_cost,
            reason=in_leg.reason,
            created_at=in_leg.created_at,
        ),
    ]


# ---------------------------------------------------------------------------
# Purchase-order number generation (Phase 8, Task 15)
# ---------------------------------------------------------------------------
#
# PO numbers follow the numeric-safe PO-#### series, exactly mirroring the ITEM-
# generator above (Decision 2): the pure _next_po_number helper is unit-testable
# with NO DB so the digit-boundary guarantee (PO-9 -> PO-0010, numeric-not-
# lexicographic) is pinned in isolation, and generate_po_number is the DB half
# that casts the digits after "PO-" to an integer and orders numerically.

_PO_NUMBER_RE = re.compile(r"^PO-[0-9]+$")


def _next_po_number(existing_numbers: "Iterable[str]") -> str:
    """
    Compute the next PO-#### number from the set of existing PO numbers.

    Pure (no DB) so the digit-boundary guarantee is unit-testable in isolation.
    Considers only strictly-numeric PO-series numbers (matching ``^PO-[0-9]+$``),
    selects the *numerically* highest suffix, and returns that value + 1 zero-padded
    to 4 digits. Returns "PO-0001" when no PO-series numbers exist yet.

    The selection is numeric, never lexicographic: given {"PO-9", "PO-10"} it picks
    10 (not the lexicographically-larger "PO-9") and returns "PO-0011". A
    lexicographic MAX would return "PO-9" as the max and re-issue "PO-0010",
    colliding once the suffix crosses a digit-width boundary — the same Phase-7
    partner defect the numeric generator exists to avoid.
    """
    suffixes = [
        int(number.split("-", 1)[1])
        for number in existing_numbers
        if _PO_NUMBER_RE.match(number)
    ]
    if not suffixes:
        return "PO-0001"
    return f"PO-{max(suffixes) + 1:04d}"


async def generate_po_number(db: AsyncSession) -> str:
    """
    Generate the next purchase-order number in the PO-#### series (Task 15).

    Finds the current highest *numeric* suffix among strictly-numeric PO-series
    numbers (matching ``^PO-[0-9]+$``) by casting the digits after "PO-" to an
    integer and ordering numerically, then delegates the increment to the pure
    _next_po_number helper. Returns "PO-0001" when no PO-series numbers exist.

    The regex filter MUST precede the cast: a bare cast over ``LIKE 'PO-%'`` would
    throw on any non-numeric number. ``func.substring(po_number, 4)`` skips the
    3-character "PO-" prefix (Postgres substring is 1-indexed, so position 4 is
    the first digit).

    The DB unique constraint on syerp_purchase_order.po_number is the authoritative
    guard; this function is a best-effort generator. The caller must handle
    IntegrityError on collision (RESEARCH.md Pattern 3).
    """
    from app.modules.syerp.models import PurchaseOrder

    result = await db.execute(
        select(PurchaseOrder.po_number)
        .where(PurchaseOrder.po_number.op("~")(r"^PO-[0-9]+$"))
        .order_by(cast(func.substring(PurchaseOrder.po_number, 4), Integer).desc())
        .limit(1)
    )
    max_number: str | None = result.scalar()

    return _next_po_number([max_number] if max_number is not None else [])


# ---------------------------------------------------------------------------
# Purchase-order CRUD (Phase 8, Task 15)
# ---------------------------------------------------------------------------
#
# PORead nests its lines (assembled here, not via a lazy ORM relationship, to
# avoid MissingGreenlet in the async context — RESEARCH.md Pitfall 2). Line
# mutations (add/edit/remove) are permitted ONLY while status == 'draft'
# (AC11-1); the _require_draft guard rejects otherwise with 422 (matching the
# inventory guards). create_po requires a vendor_id whose Partner has
# is_vendor==True (AC11-3).


class _POAggregates(NamedTuple):
    """Per-PO Decimal roll-ups derived from its lines (AC11-3 / AC11-5)."""

    total: Decimal
    total_ordered_qty: Decimal
    total_received_qty: Decimal
    outstanding_qty: Decimal


def _po_aggregates(
    lines: "Iterable[tuple[Decimal, Decimal, Decimal]]",
) -> _POAggregates:
    """
    Pure per-PO aggregate helper (no DB — unit-testable).

    Given (qty_ordered, unit_cost, qty_received) for EVERY line of a PO, returns:
      - `total` = SUM(qty_ordered * unit_cost) — the PO's ordered value (AC11-3);
      - `total_ordered_qty` / `total_received_qty` = SUM of each quantity;
      - `outstanding_qty` = ordered − received.
    All arithmetic is Decimal so the sums are exact (no float drift, no rounding);
    these numbers feed the vendor status table (AC11-5).
    """
    total = Decimal("0")
    total_ordered = Decimal("0")
    total_received = Decimal("0")
    for qty_ordered, unit_cost, qty_received in lines:
        total += qty_ordered * unit_cost
        total_ordered += qty_ordered
        total_received += qty_received
    return _POAggregates(
        total=total,
        total_ordered_qty=total_ordered,
        total_received_qty=total_received,
        outstanding_qty=total_ordered - total_received,
    )


def _po_to_read(po: "PurchaseOrder", lines: "Iterable[PurchaseOrderLine]") -> "PORead":
    """Assemble a PORead schema from a PurchaseOrder ORM row and its lines."""
    from app.modules.syerp.schemas import POLineRead, PORead

    lines = list(lines)
    agg = _po_aggregates(
        (line.qty_ordered, line.unit_cost, line.qty_received) for line in lines
    )
    return PORead(
        id=po.id,
        po_number=po.po_number,
        vendor_id=po.vendor_id,
        status=po.status,
        notes=po.notes,
        approved_at=po.approved_at,
        approved_by=po.approved_by,
        created_at=po.created_at,
        updated_at=po.updated_at,
        total=agg.total,
        total_ordered_qty=agg.total_ordered_qty,
        total_received_qty=agg.total_received_qty,
        outstanding_qty=agg.outstanding_qty,
        lines=[POLineRead.model_validate(line) for line in lines],
    )


async def _load_po_lines(db: AsyncSession, po_id: str) -> "list[PurchaseOrderLine]":
    """Return a PO's lines ordered by line_no (helper for PORead assembly)."""
    from app.modules.syerp.models import PurchaseOrderLine

    result = await db.execute(
        select(PurchaseOrderLine)
        .where(PurchaseOrderLine.po_id == po_id)
        .order_by(PurchaseOrderLine.line_no)
    )
    return list(result.scalars().all())


async def _get_po_row(db: AsyncSession, po_id: str) -> "PurchaseOrder":
    """
    Load a PurchaseOrder ORM row by id (internal helper).

    Raises HTTP 404 if no PO with the given id exists (mirrors get_item).
    """
    from app.modules.syerp.models import PurchaseOrder

    result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id))
    po = result.scalars().first()

    if po is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase order {po_id} not found",
        )

    return po


def _require_draft(po: "PurchaseOrder") -> None:
    """
    Guard: reject a line mutation when the PO is not in Draft (AC11-1).

    Raises 422 (matching the inventory guards) if po.status != 'draft'. Line
    add/edit/remove are only valid while the order is still a draft; once it is
    approved or receiving has begun the lines are frozen.
    """
    if po.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Purchase order lines can only be modified while the PO is in "
                f"Draft (current status: {po.status})."
            ),
        )


async def create_po(db: AsyncSession, data: "POCreate") -> "PORead":
    """
    Insert a new purchase-order header (Draft, empty of lines).

    Requires data.vendor_id to reference an existing Partner with is_vendor==True;
    a missing partner or a non-vendor partner is rejected with 422 (AC11-3),
    matching the inventory guards. Auto-generates a numeric-safe PO-#### number
    (generate_po_number). On a unique-constraint IntegrityError (auto-generated
    number race) retries ONCE with a fresh number (RESEARCH.md Pattern 3) — the
    number is always server-generated, so there is no user-supplied 409 branch.

    Returns the created order as a PORead (with an empty lines list). The router
    writes the po.created audit row.
    """
    import sqlalchemy.exc

    from app.modules.syerp.models import Partner, PurchaseOrder

    # Vendor gate (AC11-3): the partner must exist AND be a vendor.
    result = await db.execute(select(Partner).where(Partner.id == data.vendor_id))
    vendor = result.scalars().first()
    if vendor is None or not vendor.is_vendor:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Partner {data.vendor_id} is not a vendor (is_vendor must be True).",
        )

    po_number = await generate_po_number(db)
    po = PurchaseOrder(po_number=po_number, vendor_id=data.vendor_id, notes=data.notes)
    db.add(po)

    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        # Auto-generated number collision — retry once with a fresh number.
        po_number = await generate_po_number(db)
        po = PurchaseOrder(po_number=po_number, vendor_id=data.vendor_id, notes=data.notes)
        db.add(po)
        await db.flush()

    await db.commit()
    await db.refresh(po)
    return _po_to_read(po, [])


async def list_pos(db: AsyncSession, vendor_id: str | None = None) -> "list[PORead]":
    """
    Return purchase orders (newest-first), optionally filtered by vendor.

    Args:
        vendor_id: when supplied, restricts the list to POs for that vendor.

    Each PO is returned as a PORead with its lines nested. Lines are fetched in a
    single query over all returned PO ids and grouped in memory (no per-PO N+1).
    Ordered by created_at DESC, then po_number DESC for a stable tie-break.
    """
    from app.modules.syerp.models import PurchaseOrder, PurchaseOrderLine

    stmt = select(PurchaseOrder)
    if vendor_id is not None:
        stmt = stmt.where(PurchaseOrder.vendor_id == vendor_id)
    stmt = stmt.order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.po_number.desc())

    result = await db.execute(stmt)
    pos = list(result.scalars().all())

    if not pos:
        return []

    po_ids = [po.id for po in pos]
    lines_result = await db.execute(
        select(PurchaseOrderLine)
        .where(PurchaseOrderLine.po_id.in_(po_ids))
        .order_by(PurchaseOrderLine.line_no)
    )
    lines_by_po: dict[str, list["PurchaseOrderLine"]] = {po_id: [] for po_id in po_ids}
    for line in lines_result.scalars().all():
        lines_by_po[line.po_id].append(line)

    return [_po_to_read(po, lines_by_po[po.id]) for po in pos]


async def get_po(db: AsyncSession, po_id: str) -> "PORead":
    """
    Load a purchase order (header + nested lines) by id.

    Raises HTTP 404 if no PO with the given id exists (mirrors get_item).
    """
    po = await _get_po_row(db, po_id)
    lines = await _load_po_lines(db, po_id)
    return _po_to_read(po, lines)


async def _next_line_no(db: AsyncSession, po_id: str) -> int:
    """Return the next sequential line_no for a PO (max(line_no)+1, else 1)."""
    from app.modules.syerp.models import PurchaseOrderLine

    result = await db.execute(
        select(func.max(PurchaseOrderLine.line_no)).where(PurchaseOrderLine.po_id == po_id)
    )
    current_max: int | None = result.scalar()
    return (current_max or 0) + 1


async def add_line(db: AsyncSession, po_id: str, data: "POLineCreate") -> "POLineRead":
    """
    Append a line to a purchase order (Draft-only, AC11-1).

    Rejects with 404 if the PO or the referenced item does not exist, and with
    422 if the PO is not in Draft (line mutations are frozen after Draft). The
    new line's line_no is auto-assigned sequentially (max(line_no)+1). qty_received
    starts at 0 (only receiving moves it, Decision 5).

    Returns the created line as a POLineRead. The router writes the po.line_added
    audit row.
    """
    from app.modules.syerp.models import PurchaseOrderLine
    from app.modules.syerp.schemas import POLineRead

    po = await _get_po_row(db, po_id)
    _require_draft(po)
    # 404 if the item does not exist (mirrors the receipt/adjustment guards).
    await get_item(db, data.item_id)

    line = PurchaseOrderLine(
        po_id=po_id,
        item_id=data.item_id,
        line_no=await _next_line_no(db, po_id),
        qty_ordered=data.qty_ordered,
        unit_cost=data.unit_cost,
        need_by_date=data.need_by_date,
    )
    db.add(line)

    await db.commit()
    await db.refresh(line)
    return POLineRead.model_validate(line)


async def _get_line_row(
    db: AsyncSession, po_id: str, line_id: str
) -> "PurchaseOrderLine":
    """
    Load a PO line by id, scoped to its parent PO (internal helper).

    Raises HTTP 404 if no line with the given id exists on that PO.
    """
    from app.modules.syerp.models import PurchaseOrderLine

    result = await db.execute(
        select(PurchaseOrderLine).where(
            PurchaseOrderLine.id == line_id,
            PurchaseOrderLine.po_id == po_id,
        )
    )
    line = result.scalars().first()

    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase order line {line_id} not found on PO {po_id}",
        )

    return line


async def update_line(
    db: AsyncSession, po_id: str, line_id: str, data: "POLineUpdate"
) -> "POLineRead":
    """
    Apply a partial update to a PO line (PATCH semantics, Draft-only, AC11-1).

    Only provided (non-None) fields are written. Rejects with 404 if the PO or the
    line does not exist, and with 422 if the PO is not in Draft. If item_id is
    changed, the new item must exist (404 otherwise). qty_received / line_no are
    not editable here.

    Returns the updated line as a POLineRead. The router writes the po.line_updated
    audit row.
    """
    from app.modules.syerp.schemas import POLineRead

    po = await _get_po_row(db, po_id)
    _require_draft(po)
    line = await _get_line_row(db, po_id, line_id)

    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("item_id") is not None:
        # 404 if the reassigned item does not exist.
        await get_item(db, update_data["item_id"])

    for field, value in update_data.items():
        setattr(line, field, value)

    await db.commit()
    await db.refresh(line)
    return POLineRead.model_validate(line)


async def remove_line(db: AsyncSession, po_id: str, line_id: str) -> None:
    """
    Remove a line from a purchase order (Draft-only, AC11-1).

    Rejects with 404 if the PO or the line does not exist, and with 422 if the PO
    is not in Draft. The router writes the po.line_removed audit row (with the
    line_id from the path).
    """
    po = await _get_po_row(db, po_id)
    _require_draft(po)
    line = await _get_line_row(db, po_id, line_id)

    await db.delete(line)
    await db.commit()


# ---------------------------------------------------------------------------
# Purchase-order FSM transitions (Phase 8, Task 16)
# ---------------------------------------------------------------------------
#
# PO_TRANSITIONS mirrors PLUM's VALID_TRANSITIONS shape (a mapping from each
# status to the set of allowed successor states). advance_po_status validates a
# requested transition against this table and rejects an illegal one with 422
# (AC11-1). The approve/close endpoints call it directly; receiving (Task 17)
# reuses it (or sets status directly) to roll the header forward to
# partially_received / received. Approving additionally stamps approved_at /
# approved_by (D-P8-10).

PO_TRANSITIONS: dict[str, set[str]] = {
    "draft":              {"approved"},
    "approved":           {"partially_received", "received", "closed"},
    "partially_received": {"received", "closed"},
    "received":           {"closed"},
    "closed":             set(),  # terminal — no outgoing transitions
}


async def advance_po_status(
    db: AsyncSession, po_id: str, target: str, actor_id: str
) -> "PORead":
    """
    Advance a purchase order through the FSM (Phase 8, Task 16).

    Validates:
      - PO exists (404 if not).
      - target is an allowed successor of the current status per PO_TRANSITIONS
        (422 if not — AC11-1).

    On target == "approved", additionally stamps approved_at (tz-aware UTC now)
    and approved_by = actor_id (D-P8-10). Commits in one transaction and returns
    the updated order as a PORead (header + nested lines).

    Reusable by receiving (Task 17): any transition present in PO_TRANSITIONS is
    accepted, so the approved → partially_received / received roll-up can call
    this helper. The approve/close endpoints wire only the "approved" and
    "closed" targets. The router writes the target-specific audit event
    (po.approved / po.closed).
    """
    po = await _get_po_row(db, po_id)

    allowed = PO_TRANSITIONS.get(po.status, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition purchase order from '{po.status}' to '{target}'. "
                f"Allowed transitions: {sorted(allowed)}"
            ),
        )

    po.status = target
    if target == "approved":
        po.approved_at = datetime.now(timezone.utc)
        po.approved_by = actor_id

    await db.commit()
    await db.refresh(po)

    lines = await _load_po_lines(db, po_id)
    return _po_to_read(po, lines)


# ---------------------------------------------------------------------------
# PO receiving → inventory receipt (Phase 8, Task 17, AC11-4/5, D-P8-7)
# ---------------------------------------------------------------------------
#
# Receiving is the phase crux: it posts a REAL costed inventory receipt through
# the Task-5 post_receipt (the single source of truth for on-hand + moving-avg),
# accumulates against the line's qty_received (Decision 5), rolls the header
# status forward, and rejects over-receipt — all in ONE atomic transaction.
#
# The two decisions the pure helpers pin (no DB, unit-testable):
#   - over-receipt: qty_received + qty > qty_ordered is REJECTED; the boundary
#     qty_received + qty == qty_ordered is ALLOWED (a line may be fully received
#     in one shot). Decimal comparison — exact, no float drift (D-11).
#   - status roll-up: the PO is `received` iff EVERY line is fully received
#     (qty_received >= qty_ordered), otherwise `partially_received` (AC11-5).


def _is_over_receipt(qty_received: Decimal, qty: Decimal, qty_ordered: Decimal) -> bool:
    """
    Pure over-receipt predicate (no DB — unit-testable).

    Returns True when receiving `qty` more would push the line's cumulative
    received quantity PAST what was ordered (`qty_received + qty > qty_ordered`),
    i.e. the receipt must be REJECTED (AC11-4, D-P8-7). The exact boundary —
    `qty_received + qty == qty_ordered` — is ALLOWED (it fully receives the line).
    All arithmetic is Decimal so the boundary is exact with no float drift.
    """
    return qty_received + qty > qty_ordered


def _po_rollup_status(line_qtys: "Iterable[tuple[Decimal, Decimal]]") -> str:
    """
    Pure PO status roll-up predicate (no DB — unit-testable).

    Given (qty_ordered, qty_received) pairs for EVERY line of a PO, returns the
    receiving-driven header status: `received` when every line is fully received
    (qty_received >= qty_ordered), otherwise `partially_received` (AC11-5). All
    comparisons are Decimal (exact). Called only after a successful receipt, so at
    least one line has moved — the result is never `approved`.
    """
    if all(received >= ordered for ordered, received in line_qtys):
        return "received"
    return "partially_received"


async def receive_line(
    db: AsyncSession,
    po_id: str,
    line_id: str,
    location_id: int,
    qty: Decimal,
    actor_id: str,
) -> "PORead":
    """
    Receive `qty` of a PO line into stock (Phase 8, Task 17, AC11-4/5).

    Guard order — every rejection is 422 with NO mutation:
      1. The PO must be `approved` or `partially_received` (receiving is illegal on
         a draft, a fully-received, or a closed order).
      2. `qty` must be > 0.
      3. Over-receipt is rejected: `qty_received + qty > qty_ordered`
         (_is_over_receipt); the exact boundary (== qty_ordered) is allowed.
    The line is loaded scoped to `po_id` (404 if it does not exist on that PO).

    On success, in ONE atomic transaction (the phase crux):
      - Post a REAL costed inventory receipt via the Task-5 post_receipt at the
        line's unit_cost, source-linked to this line (source_type='po_receipt',
        source_id=line.id) — feeding SYERP-10 on-hand + moving-average (AC11-4).
        post_receipt is the single source of truth for the ledger + valuation; it
        is NOT reimplemented here. It runs with commit=False so the receipt row,
        the qty_received increment, and the status roll-up share one commit —
        a receipt can never be persisted without its accumulator bump.
      - Increment line.qty_received by qty (Decision 5 accumulator).
      - Recompute the header status across ALL lines (_po_rollup_status): `received`
        when every line is fully received, else `partially_received` (AC11-5).

    Status roll-up sets po.status DIRECTLY rather than routing through
    advance_po_status. This is deliberate: a second partial receipt while the PO is
    already `partially_received` is a legitimate re-affirmation, but
    partially_received → partially_received is NOT in PO_TRANSITIONS (the FSM guard
    would 422 it). Receiving owns this roll-up, so it bypasses the transition guard
    for the computed value; the FSM guard still governs the operator-driven
    approve/close endpoints (Task 16).

    Returns the updated order as a PORead (header + nested lines). The router
    writes the po.received audit row (with qty + location detail).
    """
    po = await _get_po_row(db, po_id)

    # Guard 1: receiving is only valid on an open, approved order.
    if po.status not in ("approved", "partially_received"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Purchase order lines can only be received while the PO is "
                f"'approved' or 'partially_received' (current status: {po.status})."
            ),
        )

    line = await _get_line_row(db, po_id, line_id)

    # Guard 2: a receipt is stock IN — zero/negative is not a receipt.
    if qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Receive quantity must be greater than zero.",
        )

    # Guard 3: over-receipt (== boundary allowed). Reject BEFORE any mutation.
    if _is_over_receipt(line.qty_received, qty, line.qty_ordered):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot receive {qty}: line already received {line.qty_received} "
                f"of {line.qty_ordered} ordered (over-receipt)."
            ),
        )

    # Post the REAL costed receipt through the single source of truth, commit=False
    # so the receipt + accumulator bump + status roll-up commit atomically together.
    await post_receipt(
        db,
        item_id=line.item_id,
        location_id=location_id,
        qty=qty,
        unit_cost=line.unit_cost,
        actor_id=actor_id,
        source_type="po_receipt",
        source_id=line.id,
        commit=False,
    )
    line.qty_received += qty

    # Roll the header status forward across ALL lines (autoflush surfaces the
    # qty_received increment above to this query).
    lines = await _load_po_lines(db, po_id)
    po.status = _po_rollup_status([(ln.qty_ordered, ln.qty_received) for ln in lines])

    await db.commit()
    await db.refresh(po)

    lines = await _load_po_lines(db, po_id)
    return _po_to_read(po, lines)


# ---------------------------------------------------------------------------
# GL posting engine — journal entries, reversals, register (Phase 9a, SYERP-12)
# ---------------------------------------------------------------------------
#
# Double-entry postings (D-P9a): an entry posts only when it is balanced
# (Σdebit == Σcredit, >= 2 lines, exactly one non-negative side per line). The
# pure _je_is_balanced helper decides truth; the service maps a False to HTTP
# 422. Entries and their lines are APPEND-ONLY (mirrors InventoryTxn) — never
# edited or deleted. A correction is a reversing entry (reverse_journal_entry)
# that swaps every debit/credit and links back via reversal_of_id, leaving the
# original untouched (immutability).
#
# Balances are DERIVED, never stored (D-P8-4): an account's balance is the SUM
# of its lines' debits minus credits (derive_account_balance / the register's
# running balance), mirroring the on-hand derivation (service.py post_receipt).
# All money is Decimal (D-11). The models declare NO ORM relationships (async
# MissingGreenlet avoidance), so child lines are loaded with explicit ordered
# SELECTs, exactly like the PurchaseOrder line loaders above.


def _je_account_id(line: "object") -> int:
    """Read `account_id` off a journal line (mapping or attribute-bearing object)."""
    if isinstance(line, Mapping):
        return line.get("account_id")
    return getattr(line, "account_id", None)


async def _require_gl_account(db: AsyncSession, account_id: int) -> "GLAccount":
    """
    Load a GL account by id, raising HTTP 404 if it does not exist.

    Called for every posting line before any write so an unknown account fails
    the whole entry (no partial posting) with a clean 404 (mirrors get_item).
    """
    from app.modules.syerp.models import GLAccount

    result = await db.execute(select(GLAccount).where(GLAccount.id == account_id))
    account = result.scalars().first()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GL account {account_id} not found.",
        )
    return account


async def _get_journal_entry_row(db: AsyncSession, entry_id: str) -> "JournalEntry":
    """Load a JournalEntry ORM row by id, raising HTTP 404 if missing."""
    from app.modules.syerp.models import JournalEntry

    result = await db.execute(select(JournalEntry).where(JournalEntry.id == entry_id))
    entry = result.scalars().first()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Journal entry {entry_id} not found.",
        )
    return entry


async def _load_journal_lines(db: AsyncSession, entry_id: str) -> "list[JournalLine]":
    """Return an entry's lines ordered by line_no (no ORM relationship — Pitfall 2)."""
    from app.modules.syerp.models import JournalLine

    result = await db.execute(
        select(JournalLine)
        .where(JournalLine.entry_id == entry_id)
        .order_by(JournalLine.line_no)
    )
    return list(result.scalars().all())


def _je_to_read(
    entry: "JournalEntry", lines: "Iterable[JournalLine]"
) -> "JournalEntryRead":
    """Assemble a JournalEntryRead from a JournalEntry ORM row and its lines."""
    from app.modules.syerp.schemas import JournalEntryRead, JournalLineRead

    return JournalEntryRead(
        id=entry.id,
        entry_date=entry.entry_date,
        memo=entry.memo,
        source_type=entry.source_type,
        source_id=entry.source_id,
        reversal_of_id=entry.reversal_of_id,
        actor_id=entry.actor_id,
        created_at=entry.created_at,
        lines=[JournalLineRead.model_validate(line) for line in lines],
    )


async def post_journal_entry(
    db: AsyncSession,
    *,
    entry_date: date,
    memo: str | None,
    lines: "Iterable[object]",
    actor_id: str,
    source_type: str | None = None,
    source_id: str | None = None,
    reversal_of_id: str | None = None,
    commit: bool = True,
) -> "JournalEntryRead":
    """
    Post a balanced double-entry journal entry (Phase 9a, SYERP-12 AC1).

    Validates the payload with the PURE _je_is_balanced helper (>= 2 lines,
    exactly one non-negative side per line, Σdebit == Σcredit at scale 6 — D-11)
    and rejects an unbalanced / single-line / bad-line entry with HTTP 422. Every
    line's `account_id` is resolved against syerp_gl_account BEFORE any write; an
    unknown account fails the whole entry with 404 (no partial posting). Lines are
    persisted in input order with `line_no` starting at 1; the unset side of each
    line is stored NULL (exactly one column is non-null per line).

    `commit` (default True) follows the post_receipt flush-vs-commit pattern: a
    standalone posting owns its commit (True); the receipt auto-post path (Task 8)
    passes commit=False so the entry + lines share the receipt's single atomic
    transaction — flushed (so the PK/timestamp exist) but committed by the caller.

    `source_type` / `source_id` are the soft polymorphic link back to the
    originating document; `reversal_of_id` is set by reverse_journal_entry. The
    entry and its lines are APPEND-ONLY thereafter (D-P9a) — corrections are
    reversing entries, never edits. Returns the posted entry as a JournalEntryRead
    with its lines nested.
    """
    from app.modules.syerp.models import JournalEntry, JournalLine

    line_list = list(lines)

    # Balance guard (D-P9a): the pure helper decides truth, the service maps to 422.
    if not _je_is_balanced(line_list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Journal entry is not a balanced double-entry: it needs at least "
                "two lines, each setting exactly one non-negative debit or credit, "
                "with total debits equal to total credits."
            ),
        )

    # Resolve every account (404 on unknown) BEFORE any write — no partial posting.
    for line in line_list:
        await _require_gl_account(db, _je_account_id(line))

    entry = JournalEntry(
        entry_date=entry_date,
        memo=memo,
        source_type=source_type,
        source_id=source_id,
        reversal_of_id=reversal_of_id,
        actor_id=actor_id,
    )
    db.add(entry)
    await db.flush()  # materialize entry.id for the child lines' FK.

    for line_no, line in enumerate(line_list, start=1):
        debit = _je_side(line, "debit")
        credit = _je_side(line, "credit")
        db.add(
            JournalLine(
                entry_id=entry.id,
                account_id=_je_account_id(line),
                line_no=line_no,
                # Exactly one side is non-zero (enforced above); store the other NULL.
                debit=debit if debit != 0 else None,
                credit=credit if credit != 0 else None,
            )
        )

    # commit=True: standalone posting owns the commit. commit=False: the caller
    # (receipt auto-post) owns one atomic commit; flush so rows/PKs exist for the
    # read-back below without ending the transaction (post_receipt pattern).
    if commit:
        await db.commit()
    else:
        await db.flush()

    entry_lines = await _load_journal_lines(db, entry.id)
    return _je_to_read(entry, entry_lines)


async def reverse_journal_entry(
    db: AsyncSession,
    entry_id: str,
    actor_id: str,
    memo: str | None = None,
) -> "JournalEntryRead":
    """
    Reverse an existing journal entry by posting its mirror image (AC2, D-P9a).

    Loads the original (404 if missing) and posts a NEW entry whose lines swap
    every debit/credit (via the pure _je_side amount swap that _reverse_lines
    performs), preserving each line's account, dated today, and linked back with
    `reversal_of_id = entry_id`. The reversal of a balanced entry is itself
    balanced, so it re-uses post_journal_entry (same 422 / 404 guards).

    The original entry is NEVER edited or deleted — immutability is the audit
    guarantee (a correction is a reversing entry, not a mutation). `memo` overrides
    the reversing entry's memo; when omitted a default derived from the original id
    is used. Returns the new reversing entry as a JournalEntryRead.
    """
    await _get_journal_entry_row(db, entry_id)  # 404 if the original is missing.
    original_lines = await _load_journal_lines(db, entry_id)

    # _reverse_lines swaps debit<->credit (pure amount swap, no account_id); zip the
    # swapped amounts back onto each original line's account to rebuild the legs.
    swapped = _reverse_lines(original_lines)
    reversed_lines = [
        {"account_id": line.account_id, **amounts}
        for line, amounts in zip(original_lines, swapped)
    ]

    return await post_journal_entry(
        db,
        entry_date=date.today(),
        memo=memo or f"Reversal of journal entry {entry_id}",
        lines=reversed_lines,
        actor_id=actor_id,
        reversal_of_id=entry_id,
        commit=True,
    )


async def list_journal_entries(
    db: AsyncSession,
    source_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> "list[JournalEntryRead]":
    """
    Return journal entries (newest-first), optionally filtered (AC1 query side).

    Filters (all optional): `source_type` restricts to auto-posted entries of a
    given kind (e.g. inventory receipts); `date_from` / `date_to` bound the
    entry_date range (inclusive). Ordered by entry_date DESC then created_at DESC
    for a stable tie-break. Lines are fetched in ONE query over all returned entry
    ids and grouped in memory (no per-entry N+1), mirroring list_pos.
    """
    from app.modules.syerp.models import JournalEntry, JournalLine

    stmt = select(JournalEntry)
    if source_type is not None:
        stmt = stmt.where(JournalEntry.source_type == source_type)
    if date_from is not None:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    stmt = stmt.order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())

    result = await db.execute(stmt)
    entries = list(result.scalars().all())
    if not entries:
        return []

    entry_ids = [entry.id for entry in entries]
    lines_result = await db.execute(
        select(JournalLine)
        .where(JournalLine.entry_id.in_(entry_ids))
        .order_by(JournalLine.line_no)
    )
    lines_by_entry: dict[str, list["JournalLine"]] = {eid: [] for eid in entry_ids}
    for line in lines_result.scalars().all():
        lines_by_entry[line.entry_id].append(line)

    return [_je_to_read(entry, lines_by_entry[entry.id]) for entry in entries]


async def get_journal_entry(db: AsyncSession, entry_id: str) -> "JournalEntryRead":
    """
    Load a journal entry (header + nested lines) by id (404 if missing).
    """
    entry = await _get_journal_entry_row(db, entry_id)
    lines = await _load_journal_lines(db, entry_id)
    return _je_to_read(entry, lines)


async def derive_account_balance(db: AsyncSession, account_id: int) -> Decimal:
    """
    Derive a GL account's balance as Σdebit − Σcredit (D-P8-4 — never stored).

    A single aggregate scalar over all of the account's lines (no date filter),
    mirroring the on-hand derivation pattern (func.sum ... scalar() or 0). An
    account with no postings has no rows, so both sums are NULL and the difference
    is NULL → coalesced to Decimal("0"). Exact fixed-point (never float — D-11).
    """
    from app.modules.syerp.models import JournalLine

    result = await db.execute(
        select(func.sum(JournalLine.debit) - func.sum(JournalLine.credit)).where(
            JournalLine.account_id == account_id
        )
    )
    return result.scalar() or Decimal("0")


async def get_account_register(
    db: AsyncSession,
    account_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
) -> "AccountRegisterRead":
    """
    Build an account register for one GL account over a date range (AC1).

    404s if the account is unknown. `opening_balance` is the derived Σdebit −
    Σcredit of every posting BEFORE `date_from` (D-P8-4 — nothing is stored); the
    ordered `rows` are that account's postings within [date_from, date_to]
    (inclusive), each carrying a Python-computed running balance
    (opening + Σ(debit − credit) up to and including that row); `closing_balance`
    is the final running balance. When a bound is None it is simply not applied
    (open-ended period). All arithmetic is Decimal — exact, never float (D-11).
    """
    from app.modules.syerp.models import JournalEntry, JournalLine

    account = await _require_gl_account(db, account_id)  # 404 if unknown.

    # opening_balance = derived Σdebit − Σcredit of postings strictly BEFORE the
    # window (D-P8-4). NULL (no prior postings) coalesces to zero.
    if date_from is not None:
        opening_stmt = (
            select(func.sum(JournalLine.debit) - func.sum(JournalLine.credit))
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
            .where(
                JournalLine.account_id == account_id,
                JournalEntry.entry_date < date_from,
            )
        )
        opening_balance: Decimal = (await db.execute(opening_stmt)).scalar() or Decimal("0")
    else:
        opening_balance = Decimal("0")

    rows_stmt = (
        select(
            JournalEntry.entry_date,
            JournalEntry.id,
            JournalEntry.memo,
            JournalLine.debit,
            JournalLine.credit,
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(JournalLine.account_id == account_id)
        .order_by(
            JournalEntry.entry_date,
            JournalEntry.created_at,
            JournalLine.line_no,
        )
    )
    if date_from is not None:
        rows_stmt = rows_stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        rows_stmt = rows_stmt.where(JournalEntry.entry_date <= date_to)

    from app.modules.syerp.schemas import AccountRegisterRead, AccountRegisterRow

    result = await db.execute(rows_stmt)
    running_balance = opening_balance
    rows: list["AccountRegisterRow"] = []
    for entry_date_, entry_id_, memo_, debit_, credit_ in result:
        running_balance = running_balance + (debit_ or Decimal("0")) - (credit_ or Decimal("0"))
        rows.append(
            AccountRegisterRow(
                entry_date=entry_date_,
                entry_id=entry_id_,
                memo=memo_,
                debit=debit_,
                credit=credit_,
                running_balance=running_balance,
            )
        )

    return AccountRegisterRead(
        account_id=account.id,
        account_code=account.code,
        account_name=account.name,
        opening_balance=opening_balance,
        closing_balance=running_balance,
        rows=rows,
    )
