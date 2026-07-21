# ABOUTME: CRUMB quotes service — QUOTE-#### number generation, PLUM-priced and
# ABOUTME: free-text lines, draft-only line edits, and the quote-status FSM.
"""CRUMB quotes service (business logic).

A quote is a header (QUOTE-#### number, partner, optional opportunity, status)
plus priced lines. A line prices either a PLUM catalog part or a free-text item:

  * unit_price supplied      → persisted verbatim (a user override, editable).
  * plum_part_id, no price    → priced from the part's released cost snapshot
                                marked up by markup_pct (default DEFAULT_MARKUP_PCT,
                                D-V3-14): unit_price = snapshot * (1 + markup/100).
  * free-text, no part/price  → requires both a description and an explicit
                                unit_price (else 422).

Line edits are permitted only while the quote is in Draft (409 otherwise). The
status walks the controlled draft → sent → accepted | rejected | expired FSM
(QUOTE_TRANSITIONS); an illegal move is rejected with 422.

Per D-V3-9 this module mirrors syerp/service — small entity module, lazy imports
inside functions to avoid import cycles, one commit per operation. Audit events
are written at the router layer, not here.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crumb.service._common import (
    DEFAULT_MARKUP_PCT,
    QUOTE_TRANSITIONS,
    _resolve_customer,
)

if TYPE_CHECKING:
    from app.modules.crumb.models import Quote, QuoteLine
    from app.modules.crumb.schemas import QuoteCreate, QuoteLineCreate


# ---------------------------------------------------------------------------
# Quote-number generation (QUOTE-####, D-P8-6 numeric-safe series)
# ---------------------------------------------------------------------------
#
# QUOTE numbers follow the numeric-safe QUOTE-#### series, mirroring
# generate_item_code / generate_wo_number: the highest strictly-NUMERIC suffix
# + 1, zero-padded — never a lexicographic MAX (which re-issues a number once
# the suffix crosses a digit-width boundary, D-P8-6). The DB unique constraint on
# crumb_quote.quote_number is the authoritative backstop; create_quote retries
# once on an IntegrityError collision.


def _next_quote_number(existing_max: int | None) -> str:
    """
    Compute the next QUOTE-#### number from the current highest numeric suffix.

    Pure (no DB) so the digit-boundary guarantee is unit-testable in isolation.
    Returns "QUOTE-0001" when no QUOTE-series numbers exist yet, otherwise the
    given suffix + 1 zero-padded to 4 digits.
    """
    if existing_max is None:
        return "QUOTE-0001"
    return f"QUOTE-{existing_max + 1:04d}"


async def generate_quote_number(db: AsyncSession) -> str:
    """
    Generate the next quote number in the QUOTE-#### series (CRUMB-01).

    Finds the current highest *numeric* suffix among strictly-numeric QUOTE-series
    numbers by casting the digits after "QUOTE-" to an integer and ordering
    numerically, then delegates the increment to the pure _next_quote_number
    helper. The regex filter MUST precede the cast (a bare cast over
    ``LIKE 'QUOTE-%'`` would throw on a non-numeric number);
    ``func.substring(quote_number, 7)`` skips the 6-character "QUOTE-" prefix
    (Postgres substring is 1-indexed, so position 7 is the first digit).
    """
    from app.modules.crumb.models import Quote

    result = await db.execute(
        select(Quote.quote_number)
        .where(Quote.quote_number.op("~")(r"^QUOTE-[0-9]+$"))
        .order_by(cast(func.substring(Quote.quote_number, 7), Integer).desc())
        .limit(1)
    )
    max_number: str | None = result.scalar()
    existing_max = int(max_number.split("-", 1)[1]) if max_number is not None else None
    return _next_quote_number(existing_max)


# ---------------------------------------------------------------------------
# Line pricing (D-V3-14)
# ---------------------------------------------------------------------------


async def _resolve_line_amounts(
    db: AsyncSession, line: QuoteLineCreate
) -> tuple[Decimal, Decimal | None]:
    """
    Resolve (unit_price, markup_pct) for one quote line per the pricing rules.

    Identity rule (D-V3-14): a line must label itself — a part-less line always
    requires a non-empty description, regardless of whether a price was supplied.
    This is enforced FIRST so a caller cannot slip an unlabeled, part-less line
    onto a customer-facing quote via the explicit-price branch below.

    Priority:
      1. Explicit unit_price → persisted verbatim (a user override); markup_pct
         passes through unchanged (may be None).
      2. plum_part_id, no price → price from the part's released cost snapshot
         (0 when there is no released revision / no snapshot) marked up by
         markup_pct (DEFAULT_MARKUP_PCT when omitted, D-V3-14):
         unit_price = snapshot * (1 + markup/100). The applied markup is returned.
      3. Free-text (no part, no price) → requires a description (422) and then an
         explicit unit_price (422).
    """
    if line.plum_part_id is None and not line.description:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A free-text quote line (no PLUM part) requires a description.",
        )

    if line.unit_price is not None:
        return line.unit_price, line.markup_pct

    if line.plum_part_id is not None:
        from app.modules.plum.service import get_released_revision

        rev = await get_released_revision(db, line.plum_part_id)
        snapshot = (
            rev.released_cost_snapshot
            if rev is not None and rev.released_cost_snapshot is not None
            else Decimal("0")
        )
        markup = line.markup_pct if line.markup_pct is not None else DEFAULT_MARKUP_PCT
        unit_price = snapshot * (Decimal("1") + markup / Decimal("100"))
        return unit_price, markup

    # Free-text line with a description but no price: the description was already
    # enforced by the identity rule above, so only the missing price remains.
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="A free-text quote line (no PLUM part) requires an explicit unit_price.",
    )


def _build_line_kwargs(
    quote_id: str,
    line: QuoteLineCreate,
    unit_price: Decimal,
    markup_pct: Decimal | None,
    sort_order: int,
) -> dict:
    """Build the QuoteLine constructor kwargs from a resolved line."""
    return {
        "quote_id": quote_id,
        "plum_part_id": line.plum_part_id,
        "description": line.description,
        "quantity": line.quantity,
        "unit_price": unit_price,
        "markup_pct": markup_pct,
        "sort_order": sort_order,
    }


# ---------------------------------------------------------------------------
# Create / read (CRUMB-01)
# ---------------------------------------------------------------------------


async def create_quote(db: AsyncSession, data: QuoteCreate, actor_id: str) -> Quote:
    """
    Create a draft quote header and its priced lines (CRUMB-01).

    Resolves the SYERP customer (404 if not a customer), generates a QUOTE-####
    number, and creates the header in Draft. Each line is priced by
    _resolve_line_amounts and stored with its resolved unit_price, the markup used,
    and sort_order = line index. Retries once on a quote_number IntegrityError
    (mirrors create_item, RESEARCH.md Pattern 3). Commits and returns the header.
    """
    import sqlalchemy.exc

    from app.modules.crumb.models import Quote, QuoteLine

    await _resolve_customer(db, data.partner_id)

    # Validate an optional opportunity link up front (404) so a bad opportunity_id
    # surfaces as a clean 4xx rather than a DB FK IntegrityError that the
    # quote_number retry below would misread and re-raise as a 500.
    if data.opportunity_id is not None:
        from app.modules.crumb.models import Opportunity

        if await db.get(Opportunity, data.opportunity_id) is None:
            raise HTTPException(
                status_code=404,
                detail=f"Opportunity '{data.opportunity_id}' not found",
            )

    # Resolve line pricing up front (independent of the header id) so a
    # quote_number collision retry does not re-run the PLUM cost lookups.
    resolved = [await _resolve_line_amounts(db, line) for line in data.lines]

    number = await generate_quote_number(db)
    quote = Quote(
        quote_number=number,
        partner_id=data.partner_id,
        opportunity_id=data.opportunity_id,
        status="draft",
        actor_id=actor_id,
    )
    db.add(quote)

    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        # Auto-generated quote number collided (race) — retry once with a fresh one.
        await db.rollback()
        number = await generate_quote_number(db)
        quote = Quote(
            quote_number=number,
            partner_id=data.partner_id,
            opportunity_id=data.opportunity_id,
            status="draft",
            actor_id=actor_id,
        )
        db.add(quote)
        await db.flush()

    for index, (line, (unit_price, markup_pct)) in enumerate(zip(data.lines, resolved)):
        db.add(
            QuoteLine(**_build_line_kwargs(quote.id, line, unit_price, markup_pct, index))
        )

    await db.commit()
    await db.refresh(quote)
    return quote


async def _get_quote_lines(db: AsyncSession, quote_id: str) -> list[QuoteLine]:
    """Load a quote's lines ordered by sort_order."""
    from app.modules.crumb.models import QuoteLine

    result = await db.execute(
        select(QuoteLine)
        .where(QuoteLine.quote_id == quote_id)
        .order_by(QuoteLine.sort_order)
    )
    return list(result.scalars().all())


async def get_quote_detail(db: AsyncSession, quote_id: str) -> Quote:
    """
    Load a quote with its lines and the derived line/total figures (CRUMB-01).

    Raises 404 if the quote does not exist. Attaches the service-derived figures
    the schema serializes as transient attributes on the ORM instances (chosen
    over building QuoteDetailRead here so the router owns Pydantic construction):
    each line gets `line_total = quantity * unit_price`, and the header gets
    `lines` and `total_value = Σ line_total`. QuoteDetailRead.model_validate(quote)
    then reads them straight through from_attributes.
    """
    from app.modules.crumb.models import Quote

    quote = await db.get(Quote, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"Quote '{quote_id}' not found")

    lines = await _get_quote_lines(db, quote_id)
    total = Decimal("0")
    for line in lines:
        line.line_total = line.quantity * line.unit_price
        total += line.line_total

    quote.lines = lines
    quote.total_value = total
    return quote


async def list_quotes(db: AsyncSession) -> list[Quote]:
    """Return all quotes ordered by quote_number."""
    from app.modules.crumb.models import Quote

    result = await db.execute(select(Quote).order_by(Quote.quote_number))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Line editing — Draft only (409 otherwise)
# ---------------------------------------------------------------------------


async def _get_draft_quote(db: AsyncSession, quote_id: str) -> Quote:
    """Load a quote (404) and assert it is editable, i.e. status == draft (409)."""
    from app.modules.crumb.models import Quote

    quote = await db.get(Quote, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"Quote '{quote_id}' not found")
    if quote.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Quote '{quote_id}' is '{quote.status}'; lines are editable only in draft.",
        )
    return quote


async def add_line(
    db: AsyncSession, quote_id: str, line: QuoteLineCreate, actor_id: str
) -> QuoteLine:
    """Add a priced line to a draft quote (409 if not draft). Returns the line."""
    from app.modules.crumb.models import QuoteLine

    await _get_draft_quote(db, quote_id)
    unit_price, markup_pct = await _resolve_line_amounts(db, line)

    existing = await _get_quote_lines(db, quote_id)
    sort_order = max((ln.sort_order for ln in existing), default=-1) + 1

    row = QuoteLine(**_build_line_kwargs(quote_id, line, unit_price, markup_pct, sort_order))
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _get_line(db: AsyncSession, quote_id: str, line_id: str) -> QuoteLine:
    """Load a quote line belonging to the given quote (404 if not found)."""
    from app.modules.crumb.models import QuoteLine

    line = await db.get(QuoteLine, line_id)
    if line is None or line.quote_id != quote_id:
        raise HTTPException(
            status_code=404, detail=f"Quote line '{line_id}' not found on quote '{quote_id}'"
        )
    return line


async def update_line(
    db: AsyncSession,
    quote_id: str,
    line_id: str,
    patch: QuoteLineCreate,
    actor_id: str,
) -> QuoteLine:
    """
    Replace a draft quote line's priced fields (409 if the quote is not draft).

    The patch is a full QuoteLineCreate (the only line input schema) re-run through
    the pricing rules, so a PLUM-part line re-prices from the released snapshot and
    a free-text line re-validates description/unit_price. sort_order is preserved.
    """
    await _get_draft_quote(db, quote_id)
    line = await _get_line(db, quote_id, line_id)
    unit_price, markup_pct = await _resolve_line_amounts(db, patch)

    line.plum_part_id = patch.plum_part_id
    line.description = patch.description
    line.quantity = patch.quantity
    line.unit_price = unit_price
    line.markup_pct = markup_pct

    await db.commit()
    await db.refresh(line)
    return line


async def delete_line(db: AsyncSession, quote_id: str, line_id: str, actor_id: str) -> None:
    """Delete a line from a draft quote (409 if the quote is not draft)."""
    await _get_draft_quote(db, quote_id)
    line = await _get_line(db, quote_id, line_id)
    await db.delete(line)
    await db.commit()


# ---------------------------------------------------------------------------
# Status FSM (draft → sent → accepted | rejected | expired)
# ---------------------------------------------------------------------------


async def advance_quote_status(
    db: AsyncSession, quote_id: str, target_status: str, actor_id: str
) -> Quote:
    """
    Advance a quote through the status FSM (CRUMB-01).

    Validates the quote exists (404) and that target_status is an allowed successor
    of the current status per QUOTE_TRANSITIONS (422 otherwise, mirroring
    advance_po_status). Commits and returns the updated quote.
    """
    from app.modules.crumb.models import Quote

    quote = await db.get(Quote, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"Quote '{quote_id}' not found")

    allowed = QUOTE_TRANSITIONS.get(quote.status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition quote from '{quote.status}' to '{target_status}'. "
                f"Allowed transitions: {sorted(allowed)}"
            ),
        )

    quote.status = target_status
    await db.commit()
    await db.refresh(quote)
    return quote
