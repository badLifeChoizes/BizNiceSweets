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


async def _gl_account_id_by_code(db: AsyncSession, code: str) -> int:
    """
    Resolve a GL account id by its Chart-of-Accounts `code` (e.g. '1130').

    Used by the receipt auto-post to resolve the Inventory (1130) and GR/IR (2150)
    control accounts by their stable codes. These accounts are seeded at startup
    (coa_seed.py); a missing one is a server MISCONFIGURATION, not a client error —
    so it raises HTTP 500 rather than 404.
    """
    from app.modules.syerp.models import GLAccount

    result = await db.execute(select(GLAccount.id).where(GLAccount.code == code))
    account_id = result.scalars().first()
    if account_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GL account {code} not seeded.",
        )
    return account_id


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
      - Auto-post a balanced GL journal entry at receipt cost (Phase 9a, SYERP-12
        AC3): Dr 1130 Inventory / Cr 2150 GR/IR for qty×unit_cost, source-linked
        (source_type='po_receipt', source_id=line.id) via post_journal_entry with
        commit=False. The JE rides THIS transaction's single commit alongside the
        stock txn, the qty_received bump, and the status roll-up — a non-zero-cost
        receipt can never persist without its balanced GL entry, and if the JE
        raises nothing persists. A ZERO-cost receipt (amount == 0) skips the GL
        post entirely (an all-zero entry cannot balance) but still records the
        physical stock receipt (Phase 9a verify M1).

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

    # Auto-post the balanced GL journal entry for this receipt in the SAME unit of
    # work (D-P9a-5): Dr 1130 Inventory / Cr 2150 GR/IR at receipt cost. The amount
    # is qty×unit_cost quantized to scale 6 so the GL entry matches post_receipt's
    # stock valuation exactly. commit=False so the entry + its lines ride the single
    # commit below — if the JE raises (e.g. a control account is missing) the stock
    # txn and accumulator bump roll back too (no partial persist, SYERP-12 AC3).
    #
    # A ZERO-cost receipt (unit_cost == 0 → amount == 0: samples, warranty/RMA
    # replacements, consignment) carries no accounting value: an all-zero JE cannot
    # satisfy _je_is_balanced (every line would set neither a positive debit nor a
    # positive credit) and would 422 the whole receipt, regressing a flow that
    # worked before the GL hook (Phase 9a verify M1). Skip the GL post when the
    # amount rounds to zero — the stock ledger still records the physical receipt.
    amount = (qty * line.unit_cost).quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP)
    if amount != 0:
        inventory_account_id = await _gl_account_id_by_code(db, "1130")
        grir_account_id = await _gl_account_id_by_code(db, "2150")
        await post_journal_entry(
            db,
            entry_date=date.today(),
            memo=f"PO receipt {line.id}",
            lines=[
                {"account_id": inventory_account_id, "debit": amount},
                {"account_id": grir_account_id, "credit": amount},
            ],
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

    Double-reversal is REFUSED (HTTP 409, Phase 9a verify M2): a posted entry may
    be reversed at most once, and a reversal is not itself reversible. Reversing
    the same entry twice would apply its opposite swing twice, silently diverging
    the DERIVED GL control-account balance from the physical inventory / moving-
    average valuation it mirrors (e.g. a receipt's 1130/2150 legs would net to a
    phantom −qty×cost while stock is still on hand). A correction beyond one
    reversal must re-post a fresh entry, never reverse again.
    """
    from app.modules.syerp.models import JournalEntry

    original = await _get_journal_entry_row(db, entry_id)  # 404 if the original is missing.

    # Guard A: a reversal is not itself reversible.
    if original.reversal_of_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Journal entry {entry_id} is itself a reversal "
                f"(of {original.reversal_of_id}) and cannot be reversed again."
            ),
        )
    # Guard B: an entry may be reversed at most once.
    existing_reversal = (
        await db.execute(
            select(JournalEntry.id).where(JournalEntry.reversal_of_id == entry_id)
        )
    ).scalars().first()
    if existing_reversal is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Journal entry {entry_id} has already been reversed by "
                f"{existing_reversal}."
            ),
        )

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


async def latest_journal_entry_id_for_source(
    db: AsyncSession, source_type: str, source_id: str
) -> str | None:
    """
    Return the id of the MOST RECENT journal entry auto-posted for a source
    document, or None if none was posted (Phase 9a verify M5).

    The receipt path posts one JE per receipt, all source-linked to the same PO
    line (source_id == line.id); partial receipts therefore accumulate several.
    The audit row for the receipt just processed needs the entry this request
    posted — the newest by created_at. Returns None when the source posted no JE
    at all (a zero-cost receipt skips the GL post), so the caller omits the
    gl.journal_posted audit row rather than record a phantom, untraceable one.
    """
    from app.modules.syerp.models import JournalEntry

    result = await db.execute(
        select(JournalEntry.id)
        .where(
            JournalEntry.source_type == source_type,
            JournalEntry.source_id == source_id,
        )
        .order_by(JournalEntry.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def derive_account_balance(db: AsyncSession, account_id: int) -> Decimal:
    """
    Derive a GL account's balance as Σdebit − Σcredit (D-P8-4 — never stored).

    A single aggregate scalar over all of the account's lines (no date filter),
    mirroring the on-hand derivation pattern (func.sum ... scalar() or 0). Each
    side is COALESCEd to zero INDEPENDENTLY: an account posted on only one side
    (e.g. a control account that is only ever credited) has NULL for the empty
    side, and `Σdebit − NULL` would be NULL in SQL — coalescing each sum first
    keeps the balance correct (D-P8-4). An account with no postings coalesces to
    0 − 0 == 0. Exact fixed-point (never float — D-11).
    """
    from app.modules.syerp.models import JournalLine

    result = await db.execute(
        select(
            func.coalesce(func.sum(JournalLine.debit), 0)
            - func.coalesce(func.sum(JournalLine.credit), 0)
        ).where(JournalLine.account_id == account_id)
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
            select(
                func.coalesce(func.sum(JournalLine.debit), 0)
                - func.coalesce(func.sum(JournalLine.credit), 0)
            )
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


# ---------------------------------------------------------------------------
# Accounts-payable pure helpers (Phase 9b, SYERP-12)
# ---------------------------------------------------------------------------
#
# The AP core decisions are pinned in PURE helpers (no DB, no float, no
# FastAPI) so their boundaries are unit-testable in isolation, exactly as the
# PO number/receipt/FSM helpers above:
#   - Bill numbers follow the numeric-safe BILL-#### series, mirroring
#     _next_po_number (numeric-not-lexicographic — D-P9b-1).
#   - Overpayment is rejected when pay_amount > open_balance; the exact
#     boundary pay_amount == open_balance is ALLOWED (it fully pays). Decimal
#     comparison — exact, no float drift (D-11, D-P8-7).
#   - Three-way match is EXACT: a matched line auto-reconciles only when its
#     quantity AND unit cost equal the unbilled/PO figures to the cent — any
#     variance drops to manual review (D-P9b-2).
# BILL_TRANSITIONS mirrors PO_TRANSITIONS' shape (draft -> posted -> paid,
# paid terminal — D-P9b-5).

_BILL_NUMBER_RE = re.compile(r"^BILL-[0-9]+$")


def _next_bill_number(existing_numbers: "Iterable[str]") -> str:
    """
    Compute the next BILL-#### number from the set of existing bill numbers.

    Pure (no DB) so the digit-boundary guarantee is unit-testable in isolation.
    Considers only strictly-numeric BILL-series numbers (matching
    ``^BILL-[0-9]+$``), selects the *numerically* highest suffix, and returns
    that value + 1 zero-padded to 4 digits. Returns "BILL-0001" when no
    BILL-series numbers exist yet.

    The selection is numeric, never lexicographic: given {"BILL-9", "BILL-10"}
    it picks 10 (not the lexicographically-larger "BILL-9") and returns
    "BILL-0011". A lexicographic MAX would re-issue "BILL-0010" once the suffix
    crosses a digit-width boundary — mirroring _next_po_number exactly (D-P9b-1).
    """
    suffixes = [
        int(number.split("-", 1)[1])
        for number in existing_numbers
        if _BILL_NUMBER_RE.match(number)
    ]
    if not suffixes:
        return "BILL-0001"
    return f"BILL-{max(suffixes) + 1:04d}"


def _is_overpayment(open_balance: Decimal, pay_amount: Decimal) -> bool:
    """
    Pure overpayment predicate (no DB — unit-testable).

    Returns True when `pay_amount` exceeds the bill's `open_balance`
    (`pay_amount > open_balance`), i.e. the payment must be REJECTED. The exact
    boundary — `pay_amount == open_balance` — is ALLOWED (it fully pays the
    bill) and returns False. All arithmetic is Decimal so the boundary is exact
    with no float drift (D-11, D-P8-7).
    """
    return pay_amount > open_balance


def _unbilled_qty(qty_received: Decimal, already_billed: Decimal) -> Decimal:
    """
    Pure unbilled-quantity helper (no DB — unit-testable).

    Returns the quantity received but not yet billed
    (`qty_received - already_billed`) — the ceiling a new AP bill line may draw
    against a PO receipt. Decimal arithmetic (exact, no float drift — D-11).
    """
    return qty_received - already_billed


def _is_exact_match(
    matched_qty: Decimal,
    unit_cost: Decimal,
    unbilled_qty: Decimal,
    po_unit_cost: Decimal,
) -> bool:
    """
    Pure three-way-match predicate (no DB — unit-testable).

    Returns True only when a bill line matches its PO receipt EXACTLY — the
    matched quantity equals the unbilled quantity AND the unit cost equals the
    PO unit cost (both Decimal-exact). Any quantity or price variance returns
    False and drops the line to manual review (D-P9b-2).
    """
    return matched_qty == unbilled_qty and unit_cost == po_unit_cost


BILL_TRANSITIONS: dict[str, set[str]] = {
    "draft":  {"posted"},
    "posted": {"paid"},
    "paid":   set(),  # terminal — no outgoing transitions
}


def _bill_transition_allowed(current: str, target: str) -> bool:
    """
    Pure AP-bill FSM predicate (no DB — unit-testable).

    Returns True when `target` is an allowed successor of `current` per
    BILL_TRANSITIONS (draft -> posted -> paid, paid terminal). The service layer
    (later task) raises HTTP 422 on top of this; the legality decision is pinned
    here (D-P9b-5), mirroring PO_TRANSITIONS.
    """
    return target in BILL_TRANSITIONS.get(current, set())


# ---------------------------------------------------------------------------
# Accounts-payable bill CRUD + three-way match (Phase 9b, SYERP-12 AC4/5)
# ---------------------------------------------------------------------------
#
# BillRead nests its lines and carries two DERIVED roll-ups (total, open_balance)
# that are computed here, not stored — so the service constructs BillRead/
# BillLineRead explicitly rather than serializing the ORM row for those fields.
# Lines and payment allocations are assembled via ordered/grouped SELECTs (the
# models declare NO ORM relationships, to avoid MissingGreenlet in the async
# context — RESEARCH.md Pitfall 2). Every sum coalesces EACH side independently
# (func.coalesce(func.sum(...), 0)) so a NULL sum on a not-yet-billed / not-yet-
# paid row degrades to 0, never NULL — the Phase-9a NULL-propagation defect
# (D-P8-4).


async def generate_bill_number(db: AsyncSession) -> str:
    """
    Generate the next bill number in the BILL-#### series (Phase 9b, D-P9b-1).

    Finds the current highest *numeric* suffix among strictly-numeric BILL-series
    numbers (matching ``^BILL-[0-9]+$``) by casting the digits after "BILL-" to an
    integer and ordering numerically, then delegates the increment to the pure
    _next_bill_number helper. Returns "BILL-0001" when no BILL-series numbers exist.

    Mirrors generate_po_number: the regex filter MUST precede the cast (a bare cast
    over ``LIKE 'BILL-%'`` would throw on any non-numeric number), and
    ``func.substring(bill_number, 6)`` skips the 5-character "BILL-" prefix
    (Postgres substring is 1-indexed, so position 6 is the first digit). The DB
    unique constraint on syerp_bill.bill_number is the authoritative guard; this is
    a best-effort generator and the caller retries once on IntegrityError.
    """
    from app.modules.syerp.models import Bill

    result = await db.execute(
        select(Bill.bill_number)
        .where(Bill.bill_number.op("~")(r"^BILL-[0-9]+$"))
        .order_by(cast(func.substring(Bill.bill_number, 6), Integer).desc())
        .limit(1)
    )
    max_number: str | None = result.scalar()

    return _next_bill_number([max_number] if max_number is not None else [])


async def _already_billed_qty(db: AsyncSession, po_line_id: str) -> Decimal:
    """
    Return the quantity of a PO line already drawn onto (non-cancelled) bills.

    Sums BillLine.matched_qty across EVERY matched line for `po_line_id` on any
    bill that is not cancelled — draft AND posted both count, so two open drafts
    cannot double-bill the same receipt. The sum coalesces to 0 (D-P8-4): a PO
    line with no bill lines yet yields Decimal("0"), never NULL.
    """
    from app.modules.syerp.models import Bill, BillLine

    result = await db.execute(
        select(func.coalesce(func.sum(BillLine.matched_qty), 0))
        .select_from(BillLine)
        .join(Bill, Bill.id == BillLine.bill_id)
        .where(BillLine.po_line_id == po_line_id, Bill.status != "cancelled")
    )
    return Decimal(result.scalar() or 0)


async def list_unbilled_receipts(
    db: AsyncSession, vendor_id: str
) -> "list[UnbilledReceiptRead]":
    """
    List a vendor's received-but-not-fully-billed PO lines (SC1 — matched picker).

    For every PO line of `vendor_id`'s purchase orders with qty_received > 0,
    computes `unbilled_qty = qty_received - Σ BillLine.matched_qty` where the sum
    spans ALL non-cancelled bills (draft + posted) so an open draft already
    consumes the receipt. Each side of the subtraction is coalesced independently
    — the grouped SUM uses func.coalesce(..., 0) and a PO line with no bill lines
    at all falls back to Decimal("0") — so a not-yet-billed line never yields a
    NULL unbilled quantity (D-P8-4). Only lines with unbilled_qty > 0 are returned,
    carrying po_line_id, po_number, item_id, unbilled_qty, and the PO line unit_cost.
    """
    from app.modules.syerp.models import Bill, BillLine, PurchaseOrder, PurchaseOrderLine
    from app.modules.syerp.schemas import UnbilledReceiptRead

    result = await db.execute(
        select(PurchaseOrderLine, PurchaseOrder.po_number)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.po_id)
        .where(
            PurchaseOrder.vendor_id == vendor_id,
            PurchaseOrderLine.qty_received > 0,
        )
        .order_by(PurchaseOrder.po_number, PurchaseOrderLine.line_no)
    )
    rows = result.all()
    if not rows:
        return []

    line_ids = [line.id for line, _ in rows]
    billed_result = await db.execute(
        select(
            BillLine.po_line_id,
            func.coalesce(func.sum(BillLine.matched_qty), 0),
        )
        .join(Bill, Bill.id == BillLine.bill_id)
        .where(BillLine.po_line_id.in_(line_ids), Bill.status != "cancelled")
        .group_by(BillLine.po_line_id)
    )
    billed_by_line = {po_line_id: Decimal(qty) for po_line_id, qty in billed_result.all()}

    unbilled: list[UnbilledReceiptRead] = []
    for line, po_number in rows:
        already = billed_by_line.get(line.id, Decimal("0"))
        remaining = _unbilled_qty(line.qty_received, already)
        if remaining > 0:
            unbilled.append(
                UnbilledReceiptRead(
                    po_line_id=line.id,
                    po_number=po_number,
                    item_id=line.item_id,
                    unbilled_qty=remaining,
                    unit_cost=line.unit_cost,
                )
            )
    return unbilled


class _PreparedBillLine(NamedTuple):
    """A validated bill line ready to persist (pure values — survives rollback)."""

    line_type: str
    po_line_id: str | None
    matched_qty: Decimal | None
    account_id: int | None
    unit_cost: Decimal | None
    amount: Decimal


async def create_bill(
    db: AsyncSession,
    *,
    vendor_id: str,
    vendor_invoice_ref: str | None,
    bill_date: date | None = None,
    lines: "Iterable[BillLineCreate]",
    actor_id: str,
) -> "BillRead":
    """
    Create a draft vendor bill with three-way PO match validation (SC2, D-P9b-1/2/3).

    Vendor gate (mirrors create_po): `vendor_id` must reference an existing Partner
    with is_vendor==True, else 422. Every line is validated BEFORE any write (no
    partial bill):
      - matched (line_type == 'matched'): the PO line is loaded (404 if it does not
        exist), its unbilled quantity is recomputed LIVE against all non-cancelled
        bills, and the line is accepted only on an EXACT three-way match —
        _is_exact_match(matched_qty, po unit_cost, unbilled_qty, po unit_cost); any
        quantity variance is rejected with 422 (D-P9b-2). The matched line always
        books at the PO line's own unit_cost, amount = matched_qty * unit_cost.
      - expense (line_type == 'expense'): the account is resolved (404 if unknown)
        and must be an EXPENSE or ASSET account (else 422, D-P9b-3) with amount > 0
        (else 422); it books at the supplied amount.
    The bill is then assigned a server-generated BILL-#### number (retried once on a
    unique-constraint collision, mirroring create_po), status 'draft', and its lines
    are persisted in input order (line_no from 1) in ONE commit. Returned via get_bill.
    """
    import sqlalchemy.exc

    from app.modules.syerp.models import Bill, BillLine, GLAccount, Partner, PurchaseOrderLine

    # Vendor gate (D-P9b-1) — the partner must exist AND be a vendor (mirror create_po).
    result = await db.execute(select(Partner).where(Partner.id == vendor_id))
    vendor = result.scalars().first()
    if vendor is None or not vendor.is_vendor:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Partner {vendor_id} is not a vendor (is_vendor must be True).",
        )

    line_list = list(lines)

    # Serialize concurrent bills that match the SAME receipt line (REVIEW P9b-#1).
    # The exact-match guard below is read-then-write: under READ COMMITTED two
    # simultaneous create_bill transactions for one po_line_id would each read
    # already_billed == 0, both pass _is_exact_match, and both commit — billing the
    # receipt twice so Dr GR/IR overshoots the receipt's Cr and 2150 never clears
    # (the exact defect this phase exists to prevent). Lock each matched PO-line row
    # FOR UPDATE up-front, in sorted id order (deadlock-safe), so the second txn
    # blocks until the first commits and then re-reads the true billed sum. The
    # lock is held until this function's single db.commit().
    matched_po_line_ids = sorted(
        {d.po_line_id for d in line_list if d.line_type == "matched"}
    )
    for locked_id in matched_po_line_ids:
        await db.execute(
            select(PurchaseOrderLine.id)
            .where(PurchaseOrderLine.id == locked_id)
            .with_for_update()
        )

    # Validate every line first, collecting pure values (no partial posting).
    # A single bill must claim each unbilled receipt line AT MOST ONCE: two matched
    # lines against the same po_line_id would each pass the DB-live exact-match check
    # independently and jointly over-bill the receipt, breaking the exact three-way
    # match / GR-IR-clears-to-zero invariant (D-P9b-1/2). Reject on the first dup.
    seen_po_line_ids: set[str] = set()
    prepared: list[_PreparedBillLine] = []
    for data in line_list:
        if data.line_type == "matched":
            if data.po_line_id in seen_po_line_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"PO line {data.po_line_id} is matched more than once on this "
                        f"bill; a bill may claim each receipt line at most once."
                    ),
                )
            seen_po_line_ids.add(data.po_line_id)
            po_result = await db.execute(
                select(PurchaseOrderLine).where(PurchaseOrderLine.id == data.po_line_id)
            )
            po_line = po_result.scalars().first()
            if po_line is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Purchase order line {data.po_line_id} not found.",
                )
            # Recompute the still-billable quantity LIVE, then require an EXACT
            # three-way match — the matched line books at the PO unit_cost, so the
            # cost leg is exact by construction and the quantity must match to the
            # cent; any variance drops to manual review (D-P9b-2).
            unbilled = _unbilled_qty(
                po_line.qty_received, await _already_billed_qty(db, po_line.id)
            )
            if not _is_exact_match(
                data.matched_qty, po_line.unit_cost, unbilled, po_line.unit_cost
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Matched quantity {data.matched_qty} does not exactly match "
                        f"the unbilled quantity {unbilled} for PO line {po_line.id}."
                    ),
                )
            prepared.append(
                _PreparedBillLine(
                    line_type="matched",
                    po_line_id=po_line.id,
                    matched_qty=data.matched_qty,
                    account_id=None,
                    unit_cost=po_line.unit_cost,
                    amount=data.matched_qty * po_line.unit_cost,
                )
            )
        else:  # expense — schema guarantees line_type == 'expense' here
            acct_result = await db.execute(
                select(GLAccount).where(GLAccount.id == data.account_id)
            )
            account = acct_result.scalars().first()
            if account is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"GL account {data.account_id} not found.",
                )
            # Expense lines may only be coded to an EXPENSE or ASSET account
            # (a bill records a cost or a capitalised asset — never a revenue,
            # liability, or equity leg from the vendor side, D-P9b-3).
            if account.account_type not in {"EXPENSE", "ASSET"}:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"GL account {account.code} is {account.account_type}; expense "
                        f"bill lines must code to an EXPENSE or ASSET account."
                    ),
                )
            if data.amount is None or data.amount <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="An expense bill line must have amount > 0.",
                )
            prepared.append(
                _PreparedBillLine(
                    line_type="expense",
                    po_line_id=None,
                    matched_qty=None,
                    account_id=account.id,
                    unit_cost=None,
                    amount=data.amount,
                )
            )

    # Persist header (retry once on an auto-generated number collision, mirroring
    # create_po) then its lines, in one commit.
    bill_number = await generate_bill_number(db)
    bill = Bill(
        bill_number=bill_number,
        vendor_id=vendor_id,
        vendor_invoice_ref=vendor_invoice_ref,
        # bill_date defaults to today when the caller omits it, keeping existing
        # 09b callers/tests working (D-P9c-1).
        bill_date=bill_date or date.today(),
        status="draft",
        actor_id=actor_id,
    )
    db.add(bill)
    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        bill_number = await generate_bill_number(db)
        bill = Bill(
            bill_number=bill_number,
            vendor_id=vendor_id,
            vendor_invoice_ref=vendor_invoice_ref,
            status="draft",
            actor_id=actor_id,
        )
        db.add(bill)
        await db.flush()

    for line_no, p in enumerate(prepared, start=1):
        db.add(
            BillLine(
                bill_id=bill.id,
                line_no=line_no,
                line_type=p.line_type,
                po_line_id=p.po_line_id,
                matched_qty=p.matched_qty,
                account_id=p.account_id,
                unit_cost=p.unit_cost,
                amount=p.amount,
            )
        )

    await db.commit()
    return await get_bill(db, bill.id)


async def _get_bill_row(
    db: AsyncSession, bill_id: str, *, for_update: bool = False
) -> "Bill":
    """
    Load a Bill ORM row by id (internal helper).

    Raises HTTP 404 if no bill with the given id exists (mirrors _get_po_row).
    When ``for_update`` is True the row is locked FOR UPDATE for the rest of the
    transaction — record_payment uses this to serialize concurrent payments against
    the same bill so its open-balance read cannot race (REVIEW P9b-#1).
    """
    from app.modules.syerp.models import Bill

    stmt = select(Bill).where(Bill.id == bill_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    bill = result.scalars().first()
    if bill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bill {bill_id} not found.",
        )
    return bill


async def _load_bill_lines(db: AsyncSession, bill_id: str) -> "list[BillLine]":
    """Return a bill's lines ordered by line_no (no ORM relationship — Pitfall 2)."""
    from app.modules.syerp.models import BillLine

    result = await db.execute(
        select(BillLine).where(BillLine.bill_id == bill_id).order_by(BillLine.line_no)
    )
    return list(result.scalars().all())


async def _bill_paid_amount(db: AsyncSession, bill_id: str) -> Decimal:
    """
    Return the total allocated (paid) against a bill.

    Sums PaymentAllocation.amount for `bill_id`, coalescing to 0 (D-P8-4): a bill
    with no allocations yet yields Decimal("0"), never NULL.
    """
    from app.modules.syerp.models import PaymentAllocation

    result = await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
            PaymentAllocation.bill_id == bill_id
        )
    )
    return Decimal(result.scalar() or 0)


def _bill_to_read(
    bill: "Bill", lines: "Iterable[BillLine]", paid: Decimal
) -> "BillRead":
    """
    Assemble a BillRead from a Bill ORM row, its lines, and its allocated total.

    total and open_balance are DERIVED, not stored: total = Σ line.amount (an empty
    line set folds to Decimal("0")), open_balance = total - paid. Each side is
    coalesced independently (D-P8-4), so the model is CONSTRUCTED explicitly rather
    than validated from_attributes for those two fields.
    """
    from app.modules.syerp.schemas import BillLineRead, BillRead

    lines = list(lines)
    total = sum((line.amount for line in lines), Decimal("0"))
    return BillRead(
        id=bill.id,
        bill_number=bill.bill_number,
        vendor_id=bill.vendor_id,
        vendor_invoice_ref=bill.vendor_invoice_ref,
        bill_date=bill.bill_date,
        status=bill.status,
        memo=bill.memo,
        posted_at=bill.posted_at,
        total=total,
        open_balance=total - paid,
        lines=[BillLineRead.model_validate(line) for line in lines],
        created_at=bill.created_at,
    )


async def get_bill(db: AsyncSession, bill_id: str) -> "BillRead":
    """
    Load a bill (header + nested lines + derived roll-ups) by id.

    Raises HTTP 404 if no bill with the given id exists (mirrors get_po).
    """
    bill = await _get_bill_row(db, bill_id)
    lines = await _load_bill_lines(db, bill_id)
    paid = await _bill_paid_amount(db, bill_id)
    return _bill_to_read(bill, lines, paid)


async def list_bills(
    db: AsyncSession,
    vendor_id: str | None = None,
    status: str | None = None,
) -> "list[BillRead]":
    """
    List bills (newest-first), optionally filtered by vendor and/or status.

    Each bill is returned as a BillRead with its lines nested and its derived
    total/open_balance rolled up. Lines and payment allocations are fetched in one
    query each over all returned bill ids and grouped in memory (no per-bill N+1);
    the allocation sum coalesces to 0 for unpaid bills (D-P8-4). Ordered by
    created_at DESC, then bill_number DESC for a stable tie-break (mirrors list_pos).
    """
    from app.modules.syerp.models import Bill, BillLine, PaymentAllocation

    stmt = select(Bill)
    if vendor_id is not None:
        stmt = stmt.where(Bill.vendor_id == vendor_id)
    if status is not None:
        stmt = stmt.where(Bill.status == status)
    stmt = stmt.order_by(Bill.created_at.desc(), Bill.bill_number.desc())

    result = await db.execute(stmt)
    bills = list(result.scalars().all())
    if not bills:
        return []

    bill_ids = [bill.id for bill in bills]

    lines_result = await db.execute(
        select(BillLine).where(BillLine.bill_id.in_(bill_ids)).order_by(BillLine.line_no)
    )
    lines_by_bill: dict[str, list[BillLine]] = {bill_id: [] for bill_id in bill_ids}
    for line in lines_result.scalars().all():
        lines_by_bill[line.bill_id].append(line)

    paid_result = await db.execute(
        select(
            PaymentAllocation.bill_id,
            func.coalesce(func.sum(PaymentAllocation.amount), 0),
        )
        .where(PaymentAllocation.bill_id.in_(bill_ids))
        .group_by(PaymentAllocation.bill_id)
    )
    paid_by_bill = {bill_id: Decimal(amount) for bill_id, amount in paid_result.all()}

    return [
        _bill_to_read(bill, lines_by_bill[bill.id], paid_by_bill.get(bill.id, Decimal("0")))
        for bill in bills
    ]


async def advance_bill_status(
    db: AsyncSession, bill_id: str, target: str, actor_id: str
) -> "BillRead":
    """
    Advance an AP bill through the FSM (Phase 9b, SYERP-12 AC4/5).

    Validates:
      - Bill exists (404 if not).
      - target is an allowed successor of the current status per BILL_TRANSITIONS
        (draft -> posted -> paid, paid terminal) — 422 if not (D-P9b-5).

    Sets bill.status = target and flushes (NOT commits): the caller owns the single
    commit so the transition can ride the same unit of work as its side effects —
    post_bill stamps posted_at + posts the JE around it, and the payment path (Task 7)
    rolls a bill to 'paid' inside the payment's own transaction. Mirrors
    advance_po_status' structure but flushes rather than committing. Returns the
    updated bill as a BillRead (header + nested lines).
    """
    bill = await _get_bill_row(db, bill_id)

    if not _bill_transition_allowed(bill.status, target):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition bill from '{bill.status}' to '{target}'. "
                f"Allowed transitions: {sorted(BILL_TRANSITIONS.get(bill.status, set()))}"
            ),
        )

    bill.status = target
    await db.flush()

    return await get_bill(db, bill_id)


async def post_bill(db: AsyncSession, bill_id: str, actor_id: str) -> "BillRead":
    """
    Post a draft AP bill to the GL, flipping it draft -> posted (SYERP-12 AC4, SC3).

    Loads the bill (404 if missing) and rejects a non-draft bill with 422 via the
    BILL_TRANSITIONS FSM guard (a posted/paid bill cannot be re-posted, D-P9b-5).
    Builds ONE balanced journal entry from the bill's lines and posts it through
    post_journal_entry with commit=False, then stamps status='posted' + posted_at
    and takes the SINGLE commit — the JE, the status flip, and the timestamp share
    one atomic transaction (Risk #3): a bill can never flip to Posted without its
    balanced GL entry, and if the JE raises nothing persists.

    The journal entry (all debits, one credit — the vendor payable):
      - each MATCHED line: Dr 2150 GR/IR (clears the receipt's GR/IR accrual),
      - each EXPENSE line: Dr the line's own EXPENSE/ASSET account,
      - ONE Cr 2110 Accounts Payable for the whole bill total (Σ line.amount).

    GR/IR INVARIANT (D-P9b-2/5): a matched line only exists on an EXACT three-way
    match (matched_qty == unbilled_qty AND unit_cost == PO unit_cost — create_bill),
    so its Dr to GR/IR (matched_qty × unit_cost) exactly equals the original Cr to
    GR/IR that receive_line posted for that receipt (qty × unit_cost). Posting the
    bill therefore clears GR/IR (2150) back to its pre-receipt balance, leaving the
    liability on AP (2110) — the accrual is neither stranded nor double-counted.

    Returns the posted bill as a BillRead. Audit (bill.posted) is the router's job;
    this service NEVER writes audit and takes exactly one commit (atomicity).
    """
    bill = await _get_bill_row(db, bill_id)

    # FSM guard: only a draft bill may be posted (422 otherwise, D-P9b-5).
    if not _bill_transition_allowed(bill.status, "posted"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot post bill {bill.bill_number}: it is '{bill.status}', "
                f"only a 'draft' bill can be posted."
            ),
        )

    lines = await _load_bill_lines(db, bill_id)

    grir_account_id = await _gl_account_id_by_code(db, "2150")
    ap_account_id = await _gl_account_id_by_code(db, "2110")

    bill_total = sum((line.amount for line in lines), Decimal("0"))

    # One balanced JE: every bill line debits (GR/IR for matched, its own account for
    # expense), one credit lands the whole total on Accounts Payable.
    je_lines: list[dict[str, object]] = []
    for line in lines:
        debit_account_id = grir_account_id if line.line_type == "matched" else line.account_id
        je_lines.append({"account_id": debit_account_id, "debit": line.amount, "credit": 0})
    je_lines.append({"account_id": ap_account_id, "debit": 0, "credit": bill_total})

    # commit=False: the JE rides THIS transaction's single commit alongside the status
    # flip below — no partial post (Risk #3).
    # Age the JE by the bill's invoice date, not today's, so the 2110 control
    # account's entry_date-aged balance ties out to the AP subledger's bill_date
    # aging (the SC2 tie-out crux, D-P9c-1).
    await post_journal_entry(
        db,
        entry_date=bill.bill_date,
        memo=f"AP bill {bill.bill_number}",
        lines=je_lines,
        actor_id=actor_id,
        source_type="ap_bill",
        source_id=bill.id,
        commit=False,
    )

    bill.status = "posted"
    bill.posted_at = datetime.now(timezone.utc)

    await db.commit()
    return await get_bill(db, bill.id)


async def record_payment(
    db: AsyncSession,
    *,
    payment_date: date,
    cash_account_id: int,
    reference: str | None,
    allocations: "Iterable[object]",
    actor_id: str,
) -> "PaymentRead":
    """
    Record a cash payment against one or more posted AP bills (SYERP-12 AC5, SC4).

    `allocations` is the PaymentCreate payload's list of (bill_id, amount) items —
    each a PaymentAllocationCreate (or any object exposing `.bill_id` / `.amount`).
    The whole disbursement is ONE atomic unit of work: a single ``db.commit`` at the
    very end, so every guard below rejects (422/404) with NOTHING persisted, and a
    successful payment lands its header, allocations, the balanced GL entry, and any
    auto-Paid transition together — never partially (Risk #3).

    Guard order — each rejection mutates nothing:
      1. `cash_account_id` must resolve to a GL account of type ASSET (422 else) —
         the funds leave a cash/bank asset (default 1110; 1111 is ASSET too).
      2. Σ allocation amounts must be > 0, and every individual amount > 0 (422 else).
      3. For each allocation the bill must exist (404) and be 'posted' (422 for a
         'draft' or 'paid' bill). The bill's LIVE open_balance is derived exactly as
         Task 5 does — total billed (Σ line.amount, folded from Decimal("0")) minus
         the coalesced Σ of PRIOR PaymentAllocation.amount (_bill_paid_amount, D-P8-4)
         — each side coalesced independently so a NULL never propagates. Overpayment
         is rejected via the pure _is_overpayment (pay > open_balance; the == boundary
         fully pays, D-P8-7). When the SAME bill appears in several allocations of this
         one payment they must not JOINTLY overpay: the claimed amount is accumulated
         per bill_id and the running total checked against the live open_balance.

    On success, in that single transaction:
      - persist a Payment header (amount = Σ allocations) + one PaymentAllocation row
        per allocation;
      - post ONE balanced JE (commit=False): Dr 2110 Accounts Payable / Cr the cash
        account, for the payment total — the funds leave cash, the liability drops;
      - for each touched bill, re-derive open_balance INCLUDING the just-added
        allocations; when it hits EXACTLY zero, advance the bill 'posted' -> 'paid'
        via advance_bill_status (auto-Paid, D-P9b-5). A partial payment leaves the
        bill 'posted' with a reduced open_balance.

    Audit (payment.recorded) is the ROUTER's job — this service NEVER writes audit and
    takes exactly one commit. Returns the payment as a PaymentRead (constructed
    explicitly; allocations loaded via an ordered SELECT — no ORM relationship).
    """
    from app.modules.syerp.models import Payment, PaymentAllocation
    from app.modules.syerp.schemas import PaymentAllocationRead, PaymentRead

    alloc_list = list(allocations)

    # Guard 1: the cash side must be an ASSET account (422 otherwise).
    cash_account = await _require_gl_account(db, cash_account_id)  # 404 if unknown.
    if cash_account.account_type != "ASSET":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"GL account {cash_account.code} is {cash_account.account_type}; a "
                f"payment must draw on an ASSET (cash/bank) account."
            ),
        )

    # Guard 2: a payment is cash OUT — the total and every leg must be positive.
    total = Decimal("0")
    for alloc in alloc_list:
        amount = Decimal(str(alloc.amount))
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Each payment allocation amount must be greater than zero.",
            )
        total += amount
    if total <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payment total (sum of allocations) must be greater than zero.",
        )

    # Serialize concurrent payments against the same bill (REVIEW P9b-#1). The
    # overpayment guard below is read-then-write: under READ COMMITTED two
    # simultaneous payments would each read the full open_balance, each allocate it,
    # and both commit — paying the bill twice and driving AP negative. Lock each
    # target bill row FOR UPDATE up-front, in sorted id order (deadlock-safe), so a
    # second payment blocks until the first commits and then re-reads the true paid
    # sum. Locks are held until this function's single db.commit().
    for locked_bill_id in sorted({alloc.bill_id for alloc in alloc_list}):
        await _get_bill_row(db, locked_bill_id, for_update=True)

    # Guard 3: resolve/validate each bill and reject overpayment BEFORE any write.
    # open_balance is derived exactly as Task 5: total billed - coalesced prior paid
    # (each side coalesced). Same-bill allocations accumulate so they cannot jointly
    # overpay a single open balance.
    bill_rows: dict[str, "Bill"] = {}
    bill_total_by_id: dict[str, Decimal] = {}
    open_balance_by_id: dict[str, Decimal] = {}
    claimed_by_id: dict[str, Decimal] = {}
    for alloc in alloc_list:
        bill_id = alloc.bill_id
        amount = Decimal(str(alloc.amount))
        if bill_id not in bill_rows:
            bill = await _get_bill_row(db, bill_id)  # 404 if the bill is unknown.
            if bill.status != "posted":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Cannot pay bill {bill.bill_number}: it is '{bill.status}', "
                        f"only a 'posted' bill can be paid."
                    ),
                )
            lines = await _load_bill_lines(db, bill_id)
            bill_total = sum((line.amount for line in lines), Decimal("0"))
            paid = await _bill_paid_amount(db, bill_id)
            bill_rows[bill_id] = bill
            bill_total_by_id[bill_id] = bill_total
            open_balance_by_id[bill_id] = bill_total - paid
            claimed_by_id[bill_id] = Decimal("0")
        claimed_by_id[bill_id] += amount
        if _is_overpayment(open_balance_by_id[bill_id], claimed_by_id[bill_id]):
            bill = bill_rows[bill_id]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Payment of {claimed_by_id[bill_id]} overpays bill "
                    f"{bill.bill_number} (open balance {open_balance_by_id[bill_id]})."
                ),
            )

    # Persist the payment header first so its id is available for the allocations'
    # FK, the JE source link, and the read-back.
    payment = Payment(
        payment_date=payment_date,
        cash_account_id=cash_account_id,
        amount=total,
        reference=reference,
        actor_id=actor_id,
    )
    db.add(payment)
    await db.flush()  # materialize payment.id.

    for alloc in alloc_list:
        db.add(
            PaymentAllocation(
                payment_id=payment.id,
                bill_id=alloc.bill_id,
                amount=Decimal(str(alloc.amount)),
            )
        )

    # One balanced JE (commit=False): Dr 2110 AP / Cr the cash account for the total —
    # rides THIS transaction's single commit alongside the allocations and any auto-Paid
    # flip, so a payment can never persist without its balanced GL entry (Risk #3).
    ap_account_id = await _gl_account_id_by_code(db, "2110")
    await post_journal_entry(
        db,
        entry_date=payment_date,
        memo=f"AP payment {payment.id}",
        lines=[
            {"account_id": ap_account_id, "debit": total, "credit": 0},
            {"account_id": cash_account_id, "debit": 0, "credit": total},
        ],
        actor_id=actor_id,
        source_type="ap_payment",
        source_id=payment.id,
        commit=False,
    )

    # Re-derive each touched bill's open_balance INCLUDING the just-added allocations
    # (autoflushed above); a bill settled to EXACTLY zero flips 'posted' -> 'paid'
    # (auto-Paid, D-P9b-5). A partial payment leaves it 'posted'.
    for bill_id in bill_rows:
        paid = await _bill_paid_amount(db, bill_id)
        if bill_total_by_id[bill_id] - paid == 0:
            await advance_bill_status(db, bill_id, "paid", actor_id)

    await db.commit()

    # Read the allocations back in a stable order (no ORM relationship — Pitfall 2).
    alloc_result = await db.execute(
        select(PaymentAllocation)
        .where(PaymentAllocation.payment_id == payment.id)
        .order_by(PaymentAllocation.id)
    )
    saved_allocations = list(alloc_result.scalars().all())
    return PaymentRead(
        id=payment.id,
        payment_date=payment.payment_date,
        cash_account_id=payment.cash_account_id,
        amount=payment.amount,
        reference=payment.reference,
        allocations=[PaymentAllocationRead.model_validate(a) for a in saved_allocations],
        created_at=payment.created_at,
    )


async def list_payments(db: AsyncSession) -> "list[PaymentRead]":
    """
    List all recorded cash payments (SYERP-12 AC5), each with its allocations nested.

    Payments are an append-only ledger (D-P9b-5); rows are returned in creation order
    (created_at, then id as a stable tie-break). For each payment the allocations are
    loaded in the SAME stable order record_payment reads them back (PaymentAllocation.id,
    no ORM relationship — Pitfall 2) and grouped in memory over all payment ids (no
    per-payment N+1). Each PaymentRead is constructed explicitly, money as Decimal (D-11).
    """
    from app.modules.syerp.models import Payment, PaymentAllocation
    from app.modules.syerp.schemas import PaymentAllocationRead, PaymentRead

    result = await db.execute(select(Payment).order_by(Payment.created_at, Payment.id))
    payments = list(result.scalars().all())
    if not payments:
        return []

    payment_ids = [payment.id for payment in payments]

    alloc_result = await db.execute(
        select(PaymentAllocation)
        .where(PaymentAllocation.payment_id.in_(payment_ids))
        .order_by(PaymentAllocation.id)
    )
    allocations_by_payment: dict[str, list[PaymentAllocation]] = {
        payment_id: [] for payment_id in payment_ids
    }
    for allocation in alloc_result.scalars().all():
        allocations_by_payment[allocation.payment_id].append(allocation)

    return [
        PaymentRead(
            id=payment.id,
            payment_date=payment.payment_date,
            cash_account_id=payment.cash_account_id,
            amount=payment.amount,
            reference=payment.reference,
            allocations=[
                PaymentAllocationRead.model_validate(a)
                for a in allocations_by_payment[payment.id]
            ],
            created_at=payment.created_at,
        )
        for payment in payments
    ]


# ===== Phase 9c reports =====
#
# Read-only derived reporting layer (SYERP-13): the AP aging schedule plus the
# three financial statements (trial balance, P&L, balance sheet). Every figure is
# derived on demand from the append-only journal / AP subledger — nothing is stored.
#
# Two rules recur across all four (get them right — they are the flagged risks):
#   1. DATE-FILTERED balances. Unlike derive_account_balance (whole-ledger, no date),
#      a report balance is bounded by JournalEntry.entry_date over the report window.
#      Each side is COALESCEd to 0 INDEPENDENTLY (func.coalesce(func.sum(debit), 0)
#      and the same for credit) — Σdr − NULL is NULL in SQL, the recurring 09a
#      NULL-propagation bug (D-P8-4). The join is JournalLine ⋈ JournalEntry on
#      JournalLine.entry_id == JournalEntry.id (the same pattern as
#      get_account_register).
#   2. SIGN normalisation so every magnitude presents positive: debit-normal types
#      (ASSET, EXPENSE) as Σdr − Σcr; credit-normal types (LIABILITY, EQUITY,
#      REVENUE) as Σcr − Σdr.
# Money is exact Decimal throughout (never float — D-11).


async def ap_aging_report(db: AsyncSession, as_of: date | None = None) -> "ApAgingReport":
    """
    Accounts-payable aging schedule as of a date, tied out to the 2110 control (AC6).

    For every bill that is POSTED to 2110 (status in ('posted','paid') and
    bill_date <= as_of) the still-open balance is bill-line total −
    Σ PaymentAllocation.amount for payments dated on/before as_of, each side coalesced
    independently (D-P8-4). DRAFT bills are excluded — a draft is not posted to 2110,
    so including it would break the tie-out (the divergence guard, D-P9c-1). Bills
    with a non-positive open balance are dropped. Each remaining balance is bucketed
    by age = (as_of − bill_date).days — current 0–30, d31_60 31–60, d61_90 61–90,
    d90_plus 90+ — and rolled up per vendor and into a grand total.

    control_balance is the date-filtered 2110 derived balance (Σdebit − Σcredit over
    JournalLine ⋈ JournalEntry where entry_date <= as_of), NEGATED: 2110 is
    credit-normal so the raw figure is negative, and negating presents the positive
    outstanding payable. in_balance is True when the aging grand total equals that
    control to the cent — the AP subledger vs. GL tie-out (D-P9c-1). Exact Decimal.
    """
    from app.modules.syerp.models import (
        Bill,
        BillLine,
        JournalEntry,
        JournalLine,
        Partner,
        Payment,
        PaymentAllocation,
    )
    from app.modules.syerp.schemas import ApAgingBucketRow, ApAgingReport, ApAgingTotals

    if as_of is None:
        as_of = date.today()

    # Bills posted to 2110 and dated on/before as_of — DRAFT bills are NOT posted
    # to 2110 and MUST be excluded (D-P9c-1 divergence guard).
    bills_result = await db.execute(
        select(Bill.id, Bill.vendor_id, Bill.bill_date).where(
            Bill.status.in_(("posted", "paid")),
            Bill.bill_date <= as_of,
        )
    )
    bills = list(bills_result.all())
    if not bills:
        bill_meta: dict[str, tuple[str, date]] = {}
        bill_ids: list[str] = []
    else:
        bill_meta = {bid: (vid, bdate) for bid, vid, bdate in bills}
        bill_ids = list(bill_meta.keys())

    # Bill-line totals per bill (Σ line.amount), coalesced to 0 (D-P8-4).
    totals_by_bill: dict[str, Decimal] = {bid: Decimal("0") for bid in bill_ids}
    if bill_ids:
        totals_result = await db.execute(
            select(BillLine.bill_id, func.coalesce(func.sum(BillLine.amount), 0))
            .where(BillLine.bill_id.in_(bill_ids))
            .group_by(BillLine.bill_id)
        )
        for bid, amount in totals_result.all():
            totals_by_bill[bid] = Decimal(amount)

    # Allocated (paid) per bill, filtered to payments dated on/before as_of — join
    # PaymentAllocation → Payment for the payment_date bound (each side coalesced).
    paid_by_bill: dict[str, Decimal] = {bid: Decimal("0") for bid in bill_ids}
    if bill_ids:
        paid_result = await db.execute(
            select(
                PaymentAllocation.bill_id,
                func.coalesce(func.sum(PaymentAllocation.amount), 0),
            )
            .select_from(PaymentAllocation)
            .join(Payment, PaymentAllocation.payment_id == Payment.id)
            .where(
                PaymentAllocation.bill_id.in_(bill_ids),
                Payment.payment_date <= as_of,
            )
            .group_by(PaymentAllocation.bill_id)
        )
        for bid, amount in paid_result.all():
            paid_by_bill[bid] = Decimal(amount)

    # Bucket each open balance per vendor. buckets[vendor_id] = [cur, 31, 61, 90+].
    buckets: dict[str, list[Decimal]] = {}
    for bid in bill_ids:
        vendor_id, bill_date_ = bill_meta[bid]
        open_balance = totals_by_bill[bid] - paid_by_bill[bid]
        if open_balance <= 0:
            continue
        age = (as_of - bill_date_).days
        if age <= 30:
            idx = 0
        elif age <= 60:
            idx = 1
        elif age <= 90:
            idx = 2
        else:
            idx = 3
        row = buckets.setdefault(vendor_id, [Decimal("0")] * 4)
        row[idx] += open_balance

    # Resolve vendor names for the vendors that have an open payable.
    names_by_vendor: dict[str, str] = {}
    if buckets:
        names_result = await db.execute(
            select(Partner.id, Partner.name).where(Partner.id.in_(list(buckets.keys())))
        )
        names_by_vendor = {vid: name for vid, name in names_result.all()}

    vendors: list[ApAgingBucketRow] = []
    grand = [Decimal("0")] * 4
    for vendor_id, row in buckets.items():
        vendor_total = row[0] + row[1] + row[2] + row[3]
        vendors.append(
            ApAgingBucketRow(
                vendor_id=vendor_id,
                vendor_name=names_by_vendor.get(vendor_id, ""),
                current=row[0],
                d31_60=row[1],
                d61_90=row[2],
                d90_plus=row[3],
                total=vendor_total,
            )
        )
        for i in range(4):
            grand[i] += row[i]
    vendors.sort(key=lambda v: v.vendor_name)

    grand_total_amt = grand[0] + grand[1] + grand[2] + grand[3]
    grand_total = ApAgingTotals(
        current=grand[0],
        d31_60=grand[1],
        d61_90=grand[2],
        d90_plus=grand[3],
        total=grand_total_amt,
    )

    # control_balance = date-filtered 2110 derived balance, NEGATED (2110 is
    # credit-normal → raw Σdr−Σcr is negative → negate to the positive payable).
    ap_account_id = await _gl_account_id_by_code(db, "2110")
    control_raw = (
        await db.execute(
            select(
                func.coalesce(func.sum(JournalLine.debit), 0)
                - func.coalesce(func.sum(JournalLine.credit), 0)
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
            .where(
                JournalLine.account_id == ap_account_id,
                JournalEntry.entry_date <= as_of,
            )
        )
    ).scalar() or Decimal("0")
    control_balance = -Decimal(control_raw)

    return ApAgingReport(
        as_of=as_of,
        vendors=vendors,
        grand_total=grand_total,
        control_balance=control_balance,
        in_balance=(grand_total_amt == control_balance),
    )


async def trial_balance(db: AsyncSession, as_of: date | None = None) -> "TrialBalanceReport":
    """
    Trial balance as of a date — every posting account's net debit/credit (AC7).

    ONE grouped aggregate sums debit and credit per account over JournalLine ⋈
    JournalEntry where entry_date <= as_of, each side coalesced independently
    (D-P8-4), joined to GLAccount for code/name/account_type. The inner join over
    JournalLine naturally includes ONLY accounts that carry a posting (rollup parents
    carry none, so they never appear). Each account is netted into a single column:
    if Σdr − Σcr >= 0 the magnitude sits in `debit` (credit 0), else in `credit`
    (debit 0). total_debit/total_credit are the column sums; in_balance is True when
    they are equal. Rows are ordered by code; all arithmetic is exact Decimal (D-11).
    """
    from app.modules.syerp.models import GLAccount, JournalEntry, JournalLine
    from app.modules.syerp.schemas import TrialBalanceReport, TrialBalanceRow

    if as_of is None:
        as_of = date.today()

    result = await db.execute(
        select(
            GLAccount.id,
            GLAccount.code,
            GLAccount.name,
            GLAccount.account_type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(GLAccount, JournalLine.account_id == GLAccount.id)
        .where(JournalEntry.entry_date <= as_of)
        .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.account_type)
        .order_by(GLAccount.code)
    )

    rows: list[TrialBalanceRow] = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for account_id, code, name, account_type, sum_debit, sum_credit in result.all():
        net = Decimal(sum_debit) - Decimal(sum_credit)
        if net >= 0:
            debit, credit = net, Decimal("0")
        else:
            debit, credit = Decimal("0"), -net
        total_debit += debit
        total_credit += credit
        rows.append(
            TrialBalanceRow(
                account_id=account_id,
                code=code,
                name=name,
                account_type=account_type,
                debit=debit,
                credit=credit,
            )
        )

    return TrialBalanceReport(
        as_of=as_of,
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
        in_balance=(total_debit == total_credit),
    )


async def profit_loss(
    db: AsyncSession, date_from: date, date_to: date
) -> "ProfitLossReport":
    """
    Profit & loss over an inclusive [date_from, date_to] window (AC7).

    ONE grouped aggregate sums debit/credit per posting account over JournalLine ⋈
    JournalEntry where date_from <= entry_date <= date_to (BOTH bounds inclusive),
    joined to GLAccount and filtered to account_type in ('REVENUE','EXPENSE'); each
    side is coalesced independently (D-P8-4). REVENUE is credit-normal so its period
    activity is Σcr − Σdr (positive revenue); EXPENSE is debit-normal so Σdr − Σcr
    (positive expense). Each account becomes a ProfitLossLine (ordered by code);
    total_revenue / total_expense are the section sums and net_income is their
    difference. A period with no activity folds to zeros (never NULL). Exact Decimal.
    """
    from app.modules.syerp.models import GLAccount, JournalEntry, JournalLine
    from app.modules.syerp.schemas import ProfitLossLine, ProfitLossReport

    result = await db.execute(
        select(
            GLAccount.id,
            GLAccount.code,
            GLAccount.name,
            GLAccount.account_type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(GLAccount, JournalLine.account_id == GLAccount.id)
        .where(
            JournalEntry.entry_date >= date_from,
            JournalEntry.entry_date <= date_to,
            GLAccount.account_type.in_(("REVENUE", "EXPENSE")),
        )
        .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.account_type)
        .order_by(GLAccount.code)
    )

    revenue: list[ProfitLossLine] = []
    expense: list[ProfitLossLine] = []
    total_revenue = Decimal("0")
    total_expense = Decimal("0")
    for account_id, code, name, account_type, sum_debit, sum_credit in result.all():
        sum_debit = Decimal(sum_debit)
        sum_credit = Decimal(sum_credit)
        if account_type == "REVENUE":
            amount = sum_credit - sum_debit  # credit-normal → positive revenue
            total_revenue += amount
            revenue.append(
                ProfitLossLine(account_id=account_id, code=code, name=name, amount=amount)
            )
        else:  # EXPENSE
            amount = sum_debit - sum_credit  # debit-normal → positive expense
            total_expense += amount
            expense.append(
                ProfitLossLine(account_id=account_id, code=code, name=name, amount=amount)
            )

    return ProfitLossReport(
        date_from=date_from,
        date_to=date_to,
        revenue=revenue,
        total_revenue=total_revenue,
        expense=expense,
        total_expense=total_expense,
        net_income=total_revenue - total_expense,
    )


async def balance_sheet(db: AsyncSession, as_of: date | None = None) -> "BalanceSheetReport":
    """
    Balance sheet as of a date — assets vs. liabilities + equity (AC7).

    ONE grouped aggregate sums debit/credit per posting account over JournalLine ⋈
    JournalEntry where entry_date <= as_of, each side coalesced independently
    (D-P8-4), joined to GLAccount and filtered to ASSET/LIABILITY/EQUITY. ASSET is
    debit-normal → presented Σdr − Σcr; LIABILITY and EQUITY are credit-normal →
    Σcr − Σdr, so every magnitude is positive. total_assets / total_liabilities /
    posted total_equity are the section sums.

    Because NO closing entries are posted, ledger 3130 (Current Year Net Income) is
    empty, so a COMPUTED equity line is appended: revenue less expense through as_of
    (Σcr − Σdr over REVENUE minus Σdr − Σcr over EXPENSE), reusing the P&L period
    logic from beginning-of-time through as_of. Its amount is added into total_equity.
    in_balance is True when total_assets == total_liabilities + total_equity (the
    accounting identity). Each section is ordered by code; arithmetic is exact Decimal.
    """
    from app.modules.syerp.models import GLAccount, JournalEntry, JournalLine
    from app.modules.syerp.schemas import BalanceSheetLine, BalanceSheetReport

    if as_of is None:
        as_of = date.today()

    result = await db.execute(
        select(
            GLAccount.id,
            GLAccount.code,
            GLAccount.name,
            GLAccount.account_type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(GLAccount, JournalLine.account_id == GLAccount.id)
        .where(
            JournalEntry.entry_date <= as_of,
            GLAccount.account_type.in_(("ASSET", "LIABILITY", "EQUITY")),
        )
        .group_by(GLAccount.id, GLAccount.code, GLAccount.name, GLAccount.account_type)
        .order_by(GLAccount.code)
    )

    assets: list[BalanceSheetLine] = []
    liabilities: list[BalanceSheetLine] = []
    equity: list[BalanceSheetLine] = []
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    total_equity = Decimal("0")
    for account_id, code, name, account_type, sum_debit, sum_credit in result.all():
        sum_debit = Decimal(sum_debit)
        sum_credit = Decimal(sum_credit)
        if account_type == "ASSET":
            amount = sum_debit - sum_credit  # debit-normal → positive asset
            total_assets += amount
            assets.append(
                BalanceSheetLine(account_id=account_id, code=code, name=name, amount=amount)
            )
        elif account_type == "LIABILITY":
            amount = sum_credit - sum_debit  # credit-normal → positive liability
            total_liabilities += amount
            liabilities.append(
                BalanceSheetLine(account_id=account_id, code=code, name=name, amount=amount)
            )
        else:  # EQUITY
            amount = sum_credit - sum_debit  # credit-normal → positive equity
            total_equity += amount
            equity.append(
                BalanceSheetLine(account_id=account_id, code=code, name=name, amount=amount)
            )

    # Computed current-year net income (3130) — no closing entries are posted, so
    # ledger 3130 is empty; surface it as revenue less expense through as_of (the
    # P&L period logic from beginning-of-time through as_of, D-P9c-1).
    pnl_result = await db.execute(
        select(
            GLAccount.account_type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(GLAccount, JournalLine.account_id == GLAccount.id)
        .where(
            JournalEntry.entry_date <= as_of,
            GLAccount.account_type.in_(("REVENUE", "EXPENSE")),
        )
        .group_by(GLAccount.account_type)
    )
    net_income = Decimal("0")
    for account_type, sum_debit, sum_credit in pnl_result.all():
        sum_debit = Decimal(sum_debit)
        sum_credit = Decimal(sum_credit)
        if account_type == "REVENUE":
            net_income += sum_credit - sum_debit
        else:  # EXPENSE
            net_income -= sum_debit - sum_credit

    net_income_account_id = await _gl_account_id_by_code(db, "3130")
    equity.append(
        BalanceSheetLine(
            account_id=net_income_account_id,
            code="3130",
            name="Current Year Net Income",
            amount=net_income,
        )
    )
    total_equity += net_income
    equity.sort(key=lambda line: line.code)

    return BalanceSheetReport(
        as_of=as_of,
        assets=assets,
        total_assets=total_assets,
        liabilities=liabilities,
        total_liabilities=total_liabilities,
        equity=equity,
        total_equity=total_equity,
        in_balance=(total_assets == total_liabilities + total_equity),
    )
