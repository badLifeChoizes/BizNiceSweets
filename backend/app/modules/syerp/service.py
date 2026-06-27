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

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.modules.syerp.models import GLAccount, Partner
    from app.modules.syerp.schemas import PartnerCreate, PartnerUpdate


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


async def create_partner(db: AsyncSession, data: "PartnerCreate") -> "Partner":
    """
    Insert a new partner row.

    If data.code is not supplied, auto-generates one via generate_partner_code.
    On a unique-constraint IntegrityError (code collision race), rolls back and
    retries once with a freshly generated code (RESEARCH.md Pattern 3).

    Returns the refreshed Partner ORM instance.
    """
    import sqlalchemy.exc

    from app.modules.syerp.models import Partner

    code = data.code or await generate_partner_code(db)

    partner = Partner(
        code=code,
        name=data.name,
        is_vendor=data.is_vendor,
        is_customer=data.is_customer,
        # Address
        addr_line1=data.addr_line1,
        addr_line2=data.addr_line2,
        addr_city=data.addr_city,
        addr_state=data.addr_state,
        addr_postal=data.addr_postal,
        addr_country=data.addr_country,
        # Contact
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        # Commerce
        payment_terms=data.payment_terms,
        tax_id=data.tax_id,
        currency=data.currency,
        country_of_origin=data.country_of_origin,
        notes=data.notes,
    )
    db.add(partner)

    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        # Code collision — rollback this transaction savepoint and retry once
        await db.rollback()
        code = await generate_partner_code(db)
        partner = Partner(
            code=code,
            name=data.name,
            is_vendor=data.is_vendor,
            is_customer=data.is_customer,
            addr_line1=data.addr_line1,
            addr_line2=data.addr_line2,
            addr_city=data.addr_city,
            addr_state=data.addr_state,
            addr_postal=data.addr_postal,
            addr_country=data.addr_country,
            contact_name=data.contact_name,
            contact_email=data.contact_email,
            contact_phone=data.contact_phone,
            payment_terms=data.payment_terms,
            tax_id=data.tax_id,
            currency=data.currency,
            country_of_origin=data.country_of_origin,
            notes=data.notes,
        )
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
