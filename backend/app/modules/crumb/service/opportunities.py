# ABOUTME: CRUMB opportunities service — opportunity CRUD, the stage FSM, the
# ABOUTME: per-stage pipeline view, and spawning a quote from a won opportunity.
"""CRUMB opportunities service (business logic).

An opportunity is a qualified sales prospect against a SYERP customer walking the
controlled stage lifecycle qualify → proposal → won | lost (STAGE_TRANSITIONS).
Stage is moved ONLY via advance_stage (the FSM), never through update_opportunity
— PATCH edits the descriptive/value fields but never the stage.

list_pipeline groups opportunities into the per-stage board used by the pipeline
view. spawn_quote turns a WON opportunity into a draft quote (D-V3-15: quoting is
gated on winning) by delegating to the quotes service.

Per D-V3-9 this mirrors syerp/service: a thin entity module with lazy imports
inside functions (SYERP is the hub; the quotes module is imported lazily to keep
the entity modules decoupled) and one commit per operation. Audit events are
written at the router layer, not here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crumb.service._common import STAGE_TRANSITIONS, _resolve_customer

if TYPE_CHECKING:
    from app.modules.crumb.models import Opportunity, Quote
    from app.modules.crumb.schemas import (
        OpportunityCreate,
        OpportunityToQuoteRequest,
        OpportunityUpdate,
    )

# The four pipeline stages, in board order (mirrors STAGE_TRANSITIONS keys).
_PIPELINE_STAGES = ["qualify", "proposal", "won", "lost"]


# ---------------------------------------------------------------------------
# Create / read (CRUMB-01)
# ---------------------------------------------------------------------------


async def create_opportunity(
    db: AsyncSession, data: OpportunityCreate, actor_id: str
) -> Opportunity:
    """
    Create an opportunity against a SYERP customer (CRUMB-01).

    Resolves the customer (404 if the partner is not a customer). Stage defaults
    to "qualify". Commits and returns the opportunity.
    """
    from app.modules.crumb.models import Opportunity

    await _resolve_customer(db, data.partner_id)

    opp = Opportunity(
        name=data.name,
        partner_id=data.partner_id,
        lead_id=data.lead_id,
        estimated_value=data.estimated_value,
        expected_close_date=data.expected_close_date,
        stage="qualify",
        actor_id=actor_id,
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)
    return opp


async def list_opportunities(db: AsyncSession) -> list[Opportunity]:
    """Return all opportunities ordered newest-first."""
    from app.modules.crumb.models import Opportunity

    result = await db.execute(
        select(Opportunity).order_by(Opportunity.created_at.desc())
    )
    return list(result.scalars().all())


async def list_pipeline(db: AsyncSession) -> dict[str, list[Opportunity]]:
    """
    Return opportunities grouped by stage for the per-stage pipeline board.

    Every stage key is always present (qualify | proposal | won | lost), mapping
    to a possibly-empty list; within each stage rows are newest-first.
    """
    opportunities = await list_opportunities(db)
    board: dict[str, list[Opportunity]] = {stage: [] for stage in _PIPELINE_STAGES}
    for opp in opportunities:
        board.setdefault(opp.stage, []).append(opp)
    return board


async def get_opportunity(db: AsyncSession, opp_id: str) -> Opportunity:
    """Load an opportunity by id. Raises 404 if it does not exist."""
    from app.modules.crumb.models import Opportunity

    opp = await db.get(Opportunity, opp_id)
    if opp is None:
        raise HTTPException(status_code=404, detail=f"Opportunity '{opp_id}' not found")
    return opp


async def update_opportunity(
    db: AsyncSession, opp_id: str, patch: OpportunityUpdate, actor_id: str
) -> Opportunity:
    """
    PATCH an opportunity's descriptive/value fields (only non-None fields applied).

    Stage is deliberately NOT patchable here — it is a controlled lifecycle moved
    only via advance_stage. OpportunityUpdate omits stage, so this is enforced at
    the schema boundary too.
    """
    opp = await get_opportunity(db, opp_id)
    for field, value in patch.model_dump(exclude_none=True).items():
        setattr(opp, field, value)
    await db.commit()
    await db.refresh(opp)
    return opp


# ---------------------------------------------------------------------------
# Stage FSM (qualify → proposal → won | lost)
# ---------------------------------------------------------------------------


async def advance_stage(
    db: AsyncSession, opp_id: str, target_stage: str, actor_id: str
) -> Opportunity:
    """
    Advance an opportunity through the stage FSM (CRUMB-01).

    Validates the opportunity exists (404) and that target_stage is an allowed
    successor of the current stage per STAGE_TRANSITIONS (422 otherwise, mirroring
    advance_po_status). Commits and returns the updated opportunity.
    """
    opp = await get_opportunity(db, opp_id)

    allowed = STAGE_TRANSITIONS.get(opp.stage, set())
    if target_stage not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition opportunity from '{opp.stage}' to '{target_stage}'. "
                f"Allowed transitions: {sorted(allowed)}"
            ),
        )

    opp.stage = target_stage
    await db.commit()
    await db.refresh(opp)
    return opp


# ---------------------------------------------------------------------------
# Spawn quote from a won opportunity (D-V3-15)
# ---------------------------------------------------------------------------


async def spawn_quote(
    db: AsyncSession, opp_id: str, data: OpportunityToQuoteRequest, actor_id: str
) -> Quote:
    """
    Create a draft quote from a WON opportunity (D-V3-15).

    Quoting is gated on winning: the opportunity must be in stage "won" (422
    otherwise). Delegates to the quotes service (imported lazily to keep the
    entity modules decoupled), seeding the new quote's partner from the
    opportunity, linking it back via opportunity_id, and passing through the
    optional seed lines. Returns the created quote.
    """
    from app.modules.crumb.schemas import QuoteCreate
    from app.modules.crumb.service import quotes

    opp = await get_opportunity(db, opp_id)
    if opp.stage != "won":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Opportunity '{opp_id}' is in stage '{opp.stage}'; a quote can only "
                "be spawned from a won opportunity."
            ),
        )

    quote_data = QuoteCreate(
        partner_id=opp.partner_id,
        opportunity_id=opp_id,
        lines=data.lines or [],
    )
    return await quotes.create_quote(db, quote_data, actor_id)
