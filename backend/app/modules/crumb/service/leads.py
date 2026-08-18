# ABOUTME: CRUMB leads service — lead CRUD/archive plus the two pipeline
# ABOUTME: conversions: link/create a SYERP customer, and convert to an opportunity.
"""CRUMB leads service (business logic).

A lead is a prospective customer entering the pipeline (status new → qualified →
converted; `active` is the archive flag). Two conversions move it along:

  * link_or_create_customer — attaches the lead to a SYERP customer, either an
    existing partner (by id) or a freshly created one, and marks it qualified.
  * convert_to_opportunity  — spins up an Opportunity against the lead's linked
    customer and marks the lead converted.

Per D-V3-9 this mirrors syerp/service: a thin entity module with lazy imports
inside functions (SYERP is the hub — never import its model/service layer at
module import time) and one commit per operation. SYERP partner creation is
REUSED via syerp.service.partners.create_partner, never re-implemented here.
Audit events are written at the router layer, not in the service.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crumb.service._common import _resolve_customer

if TYPE_CHECKING:
    from app.modules.crumb.models import Lead, Opportunity
    from app.modules.crumb.schemas import (
        LeadCreate,
        LeadLinkCustomerRequest,
        LeadToOpportunityRequest,
        LeadUpdate,
    )


# ---------------------------------------------------------------------------
# CRUD (CRUMB-01)
# ---------------------------------------------------------------------------


async def create_lead(db: AsyncSession, data: LeadCreate, actor_id: str) -> Lead:
    """Create a new pipeline lead (status defaults to new, active). Returns the lead."""
    from app.modules.crumb.models import Lead

    lead = Lead(
        name=data.name,
        company=data.company,
        contact=data.contact,
        source=data.source,
        actor_id=actor_id,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


async def list_leads(db: AsyncSession, include_archived: bool = False) -> list[Lead]:
    """
    Return leads ordered newest-first.

    Excludes archived (active=False) leads unless include_archived is True.
    """
    from app.modules.crumb.models import Lead

    stmt = select(Lead)
    if not include_archived:
        stmt = stmt.where(Lead.active == True)  # noqa: E712
    stmt = stmt.order_by(Lead.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_lead(db: AsyncSession, lead_id: str) -> Lead:
    """Load a lead by id. Raises 404 if it does not exist."""
    from app.modules.crumb.models import Lead

    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead '{lead_id}' not found")
    return lead


async def update_lead(
    db: AsyncSession, lead_id: str, patch: LeadUpdate, actor_id: str
) -> Lead:
    """
    PATCH a lead's descriptive fields (only non-None fields are applied).

    The conversion links and lifecycle status are moved by the dedicated
    link/convert functions, not here.
    """
    lead = await get_lead(db, lead_id)
    for field, value in patch.model_dump(exclude_none=True).items():
        setattr(lead, field, value)
    await db.commit()
    await db.refresh(lead)
    return lead


async def archive_lead(db: AsyncSession, lead_id: str, actor_id: str) -> Lead:
    """Soft-archive a lead by clearing its active flag. Returns the lead."""
    lead = await get_lead(db, lead_id)
    lead.active = False
    await db.commit()
    await db.refresh(lead)
    return lead


# ---------------------------------------------------------------------------
# Pipeline conversions (CRUMB-01)
# ---------------------------------------------------------------------------


async def link_or_create_customer(
    db: AsyncSession,
    lead_id: str,
    data: LeadLinkCustomerRequest,
    actor_id: str,
) -> Lead:
    """
    Link a lead to a SYERP customer and mark it qualified (CRUMB-01).

    Exactly one intent is required:
      * partner_id → link an EXISTING partner (404 if it is not a customer), or
      * new_customer_name → create a NEW customer partner (is_customer=True) via
        the SYERP partners service (REUSED, never re-implemented) and link it.
    Neither supplied → 422. Stamps lead.partner_id, sets status="qualified",
    commits and returns the lead.
    """
    lead = await get_lead(db, lead_id)

    if data.partner_id:
        partner = await _resolve_customer(db, data.partner_id)
    elif data.new_customer_name:
        from app.modules.syerp.schemas import PartnerCreate
        from app.modules.syerp.service.partners import create_partner

        partner = await create_partner(
            db,
            PartnerCreate(
                name=data.new_customer_name,
                is_customer=True,
                is_supplier=bool(data.is_supplier),
            ),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either partner_id (existing customer) or new_customer_name.",
        )

    lead.partner_id = partner.id
    lead.status = "qualified"
    await db.commit()
    await db.refresh(lead)
    return lead


async def convert_to_opportunity(
    db: AsyncSession,
    lead_id: str,
    data: LeadToOpportunityRequest,
    actor_id: str,
) -> Opportunity:
    """
    Convert a qualified lead into an opportunity (CRUMB-01).

    Requires the lead to already be linked to a customer (lead.partner_id set,
    422 otherwise) that is still a valid customer (re-resolved via _resolve_customer,
    AC6 — the flag may have been cleared in SYERP since link time). Creates an
    Opportunity in stage "qualify" against that partner seeded from the request
    (name/estimated_value/expected_close_date), stamps lead.opportunity_id and
    status="converted", commits and returns the opportunity.
    """
    from app.modules.crumb.models import Opportunity

    lead = await get_lead(db, lead_id)
    if lead.partner_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Lead must be linked to a customer before it can be converted.",
        )
    # Re-resolve the customer (404 if the partner is gone or no longer is_customer),
    # matching create_opportunity / create_quote so every opportunity path enforces
    # the AC6 is_customer invariant rather than trusting the link-time check.
    await _resolve_customer(db, lead.partner_id)

    opp = Opportunity(
        name=data.name,
        partner_id=lead.partner_id,
        lead_id=lead.id,
        estimated_value=data.estimated_value,
        expected_close_date=data.expected_close_date,
        stage="qualify",
        actor_id=actor_id,
    )
    db.add(opp)
    await db.flush()

    lead.opportunity_id = opp.id
    lead.status = "converted"
    await db.commit()
    await db.refresh(opp)
    return opp
