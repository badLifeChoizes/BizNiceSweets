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
from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import Integer, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.modules.syerp.models import GLAccount, InventoryItem, Partner, StockLocation
    from app.modules.syerp.schemas import (
        InventoryItemCreate,
        InventoryItemUpdate,
        ItemOnHandRead,
        PartnerCreate,
        PartnerUpdate,
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
