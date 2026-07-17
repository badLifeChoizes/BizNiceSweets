# ABOUTME: CRUMB (CRM) API router — leads, opportunities, quotes (+lines) and
# ABOUTME: interactions. Thin: each route delegates to crumb/service, gates on
# ABOUTME: crumb:read (GET) / crumb:write (mutations), and writes an attributable
# ABOUTME: audit row AFTER the service commit (write_audit self-commits).
"""
CRUMB API router — CRM pipeline (CRUMB-01).

Endpoints (mount_all in registry.py adds the /api/v1 prefix — full paths are
/api/v1/crumb/leads, etc.; this router carries no prefix and spells the
/crumb/... path on each route, mirroring mousse/router.py):

  Leads
    GET    /crumb/leads                       — list leads (crumb:read)
    POST   /crumb/leads                       — create a lead (crumb:write)
    GET    /crumb/leads/{lead_id}             — lead detail (crumb:read)
    PATCH  /crumb/leads/{lead_id}             — edit descriptive fields (crumb:write)
    POST   /crumb/leads/{lead_id}/archive     — soft-archive (crumb:write)
    POST   /crumb/leads/{lead_id}/link-customer — link/create a customer (crumb:write)
    POST   /crumb/leads/{lead_id}/convert     — convert to an opportunity (crumb:write)

  Opportunities
    GET    /crumb/opportunities               — list (?pipeline=true → stage board) (crumb:read)
    POST   /crumb/opportunities               — create (crumb:write)
    GET    /crumb/opportunities/{opp_id}      — detail (crumb:read)
    PATCH  /crumb/opportunities/{opp_id}      — edit descriptive/value fields (crumb:write)
    POST   /crumb/opportunities/{opp_id}/stage — advance the stage FSM (crumb:write)
    POST   /crumb/opportunities/{opp_id}/quote — spawn a draft quote (crumb:write)

  Quotes
    GET    /crumb/quotes                      — list quote headers (crumb:read)
    POST   /crumb/quotes                      — create a draft quote (crumb:write)
    GET    /crumb/quotes/{quote_id}           — header + priced lines + total (crumb:read)
    POST   /crumb/quotes/{quote_id}/lines     — add a line (draft only) (crumb:write)
    PATCH  /crumb/quotes/{quote_id}/lines/{line_id} — replace a line (draft only) (crumb:write)
    DELETE /crumb/quotes/{quote_id}/lines/{line_id} — delete a line (draft only) (crumb:write)
    POST   /crumb/quotes/{quote_id}/status    — advance the status FSM (crumb:write)
    POST   /crumb/quotes/{quote_id}/convert   — convert an accepted quote → sales order (crumb:write)

  Sales orders
    GET    /crumb/sales-orders                 — list order headers (crumb:read)
    POST   /crumb/sales-orders                 — create a draft order (crumb:write)
    GET    /crumb/sales-orders/{so_id}         — header + lines + totals (crumb:read)
    POST   /crumb/sales-orders/{so_id}/lines   — add a line (draft only) (crumb:write)
    PATCH  /crumb/sales-orders/{so_id}/lines/{line_id} — replace a line (draft only) (crumb:write)
    DELETE /crumb/sales-orders/{so_id}/lines/{line_id} — delete a line (draft only) (crumb:write)
    POST   /crumb/sales-orders/{so_id}/status  — advance the order-status FSM (crumb:write)

  Interactions
    POST   /crumb/interactions                — log a customer touch (crumb:write)
    GET    /crumb/interactions?partner_id=    — per-customer timeline (crumb:read)

Permission gating (mirrors mousse): every mutation requires crumb:write, every
read crumb:read. Unauthenticated → 401, wrong permission → 403 (admin wildcard is
handled inside require_permission).

Audit logging: every mutation writes one AuditLog row AFTER the service's own
commit (write_audit self-commits), reads never audit. Actions: lead.created,
lead.updated, lead.archived, lead.linked_customer, lead.converted,
opportunity.created, opportunity.updated, opportunity.stage_changed,
opportunity.quote_spawned, quote.created, quote.line_added, quote.line_updated,
quote.line_deleted, quote.status_changed, quote.converted_to_sales_order,
sales_order.created, sales_order.line_added, sales_order.line_updated,
sales_order.line_deleted, sales_order.status_changed, sales_order.confirmed,
sales_order.cancelled, interaction.logged.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.service import write_audit
from app.modules.crumb import service as crumb_service
from app.modules.crumb.schemas import (
    InteractionCreate,
    InteractionRead,
    LeadCreate,
    LeadLinkCustomerRequest,
    LeadRead,
    LeadToOpportunityRequest,
    LeadUpdate,
    OpportunityCreate,
    OpportunityRead,
    OpportunityStageRequest,
    OpportunityToQuoteRequest,
    OpportunityUpdate,
    QuoteCreate,
    QuoteDetailRead,
    QuoteLineCreate,
    QuoteLineRead,
    QuoteRead,
    QuoteStatusRequest,
    QuoteToSalesOrderRequest,
    SalesOrderCreate,
    SalesOrderDetailRead,
    SalesOrderLineCreate,
    SalesOrderLineRead,
    SalesOrderRead,
    SalesOrderStatusRequest,
)

# The sales-order Draft-only line editors share the names add_line/update_line/
# delete_line with the quote editors, so they are intentionally NOT flat-re-exported
# from service/__init__.py (see its NOTE). Import them from the submodule and alias
# so calling the SO editors never shadows crumb_service.add_line (the quote editor).
from app.modules.crumb.service.sales_orders import (
    add_line as add_so_line,
    delete_line as delete_so_line,
    update_line as update_so_line,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Leads (CRUMB-01)
# ---------------------------------------------------------------------------


@router.get("/crumb/leads", response_model=list[LeadRead])
async def list_leads_endpoint(
    include_archived: bool = False,
    current_user=Depends(require_permission("crumb:read")),
    db: AsyncSession = Depends(get_db),
) -> list[LeadRead]:
    """List leads newest-first (archived excluded unless include_archived). Read-only."""
    return await crumb_service.list_leads(db, include_archived=include_archived)


@router.post(
    "/crumb/leads",
    response_model=LeadRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_lead_endpoint(
    data: LeadCreate,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> LeadRead:
    """Create a pipeline lead. Writes a lead.created audit row after the commit."""
    lead = await crumb_service.create_lead(db, data, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="lead.created",
        target_type="crumb_lead",
        target_id=lead.id,
        detail=f"Lead created: {lead.name}",
    )
    return lead


@router.get("/crumb/leads/{lead_id}", response_model=LeadRead)
async def get_lead_endpoint(
    lead_id: str,
    current_user=Depends(require_permission("crumb:read")),
    db: AsyncSession = Depends(get_db),
) -> LeadRead:
    """Get a single lead by id (404 if missing). Read-only."""
    return await crumb_service.get_lead(db, lead_id)


@router.patch("/crumb/leads/{lead_id}", response_model=LeadRead)
async def update_lead_endpoint(
    lead_id: str,
    patch: LeadUpdate,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> LeadRead:
    """PATCH a lead's descriptive fields. Writes a lead.updated audit row."""
    lead = await crumb_service.update_lead(db, lead_id, patch, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="lead.updated",
        target_type="crumb_lead",
        target_id=lead.id,
        detail=f"Lead updated: {lead.name}",
    )
    return lead


@router.post("/crumb/leads/{lead_id}/archive", response_model=LeadRead)
async def archive_lead_endpoint(
    lead_id: str,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> LeadRead:
    """Soft-archive a lead (clear active). Writes a lead.archived audit row."""
    lead = await crumb_service.archive_lead(db, lead_id, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="lead.archived",
        target_type="crumb_lead",
        target_id=lead.id,
        detail=f"Lead archived: {lead.name}",
    )
    return lead


@router.post("/crumb/leads/{lead_id}/link-customer", response_model=LeadRead)
async def link_customer_endpoint(
    lead_id: str,
    data: LeadLinkCustomerRequest,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> LeadRead:
    """
    Link a lead to a SYERP customer (existing or newly created) and mark it
    qualified. Writes a lead.linked_customer audit row after the commit.
    """
    lead = await crumb_service.link_or_create_customer(
        db, lead_id, data, str(current_user.id)
    )
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="lead.linked_customer",
        target_type="crumb_lead",
        target_id=lead.id,
        detail=f"Lead '{lead.name}' linked to customer {lead.partner_id}",
    )
    return lead


@router.post(
    "/crumb/leads/{lead_id}/convert",
    response_model=OpportunityRead,
    status_code=status.HTTP_201_CREATED,
)
async def convert_lead_endpoint(
    lead_id: str,
    data: LeadToOpportunityRequest,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> OpportunityRead:
    """
    Convert a qualified lead into an opportunity. Writes a lead.converted audit
    row (target: the lead) after the commit.
    """
    opp = await crumb_service.convert_to_opportunity(
        db, lead_id, data, str(current_user.id)
    )
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="lead.converted",
        target_type="crumb_lead",
        target_id=lead_id,
        detail=f"Lead {lead_id} converted to opportunity {opp.id} ({opp.name})",
    )
    return opp


# ---------------------------------------------------------------------------
# Opportunities (CRUMB-01)
# ---------------------------------------------------------------------------


@router.get("/crumb/opportunities", response_model=None)
async def list_opportunities_endpoint(
    pipeline: bool = False,
    current_user=Depends(require_permission("crumb:read")),
    db: AsyncSession = Depends(get_db),
) -> list[OpportunityRead] | dict[str, list[OpportunityRead]]:
    """
    List opportunities newest-first, or (?pipeline=true) the stage-grouped board
    (qualify | proposal | won | lost → lists). Read-only.
    """
    if pipeline:
        board = await crumb_service.list_pipeline(db)
        return {
            stage: [OpportunityRead.model_validate(opp) for opp in opps]
            for stage, opps in board.items()
        }
    opps = await crumb_service.list_opportunities(db)
    return [OpportunityRead.model_validate(opp) for opp in opps]


@router.post(
    "/crumb/opportunities",
    response_model=OpportunityRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_opportunity_endpoint(
    data: OpportunityCreate,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> OpportunityRead:
    """Create an opportunity. Writes an opportunity.created audit row."""
    opp = await crumb_service.create_opportunity(db, data, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="opportunity.created",
        target_type="crumb_opportunity",
        target_id=opp.id,
        detail=f"Opportunity created: {opp.name}",
    )
    return opp


@router.get("/crumb/opportunities/{opp_id}", response_model=OpportunityRead)
async def get_opportunity_endpoint(
    opp_id: str,
    current_user=Depends(require_permission("crumb:read")),
    db: AsyncSession = Depends(get_db),
) -> OpportunityRead:
    """Get a single opportunity by id (404 if missing). Read-only."""
    return await crumb_service.get_opportunity(db, opp_id)


@router.patch("/crumb/opportunities/{opp_id}", response_model=OpportunityRead)
async def update_opportunity_endpoint(
    opp_id: str,
    patch: OpportunityUpdate,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> OpportunityRead:
    """PATCH an opportunity's fields (not stage). Writes an opportunity.updated row."""
    opp = await crumb_service.update_opportunity(db, opp_id, patch, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="opportunity.updated",
        target_type="crumb_opportunity",
        target_id=opp.id,
        detail=f"Opportunity updated: {opp.name}",
    )
    return opp


@router.post("/crumb/opportunities/{opp_id}/stage", response_model=OpportunityRead)
async def advance_stage_endpoint(
    opp_id: str,
    data: OpportunityStageRequest,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> OpportunityRead:
    """Advance the opportunity stage FSM. Writes an opportunity.stage_changed row."""
    opp = await crumb_service.advance_stage(
        db, opp_id, data.target_stage, str(current_user.id)
    )
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="opportunity.stage_changed",
        target_type="crumb_opportunity",
        target_id=opp.id,
        detail=f"Opportunity {opp.id} moved to stage '{opp.stage}'",
    )
    return opp


@router.post(
    "/crumb/opportunities/{opp_id}/quote",
    response_model=QuoteRead,
    status_code=status.HTTP_201_CREATED,
)
async def spawn_quote_endpoint(
    opp_id: str,
    data: OpportunityToQuoteRequest,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> QuoteRead:
    """
    Spawn a draft quote from a won opportunity. Writes two audit rows after the
    commit: an opportunity.quote_spawned row (target: the opportunity) and a
    quote.created row (target: the new quote) so the spawned quote carries the same
    attributable creation record as a directly-created quote (no audit asymmetry).
    """
    quote = await crumb_service.spawn_quote(db, opp_id, data, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="opportunity.quote_spawned",
        target_type="crumb_opportunity",
        target_id=opp_id,
        detail=f"Opportunity {opp_id} spawned quote {quote.quote_number}",
    )
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="quote.created",
        target_type="crumb_quote",
        target_id=quote.id,
        detail=f"Quote created: {quote.quote_number} (spawned from opportunity {opp_id})",
    )
    return quote


# ---------------------------------------------------------------------------
# Quotes (CRUMB-01)
# ---------------------------------------------------------------------------


@router.get("/crumb/quotes", response_model=list[QuoteRead])
async def list_quotes_endpoint(
    current_user=Depends(require_permission("crumb:read")),
    db: AsyncSession = Depends(get_db),
) -> list[QuoteRead]:
    """List quote headers ordered by quote number. Read-only."""
    return await crumb_service.list_quotes(db)


@router.post(
    "/crumb/quotes",
    response_model=QuoteRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_quote_endpoint(
    data: QuoteCreate,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> QuoteRead:
    """Create a draft quote (header + priced lines). Writes a quote.created row."""
    quote = await crumb_service.create_quote(db, data, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="quote.created",
        target_type="crumb_quote",
        target_id=quote.id,
        detail=f"Quote created: {quote.quote_number}",
    )
    return quote


@router.get("/crumb/quotes/{quote_id}", response_model=QuoteDetailRead)
async def get_quote_endpoint(
    quote_id: str,
    current_user=Depends(require_permission("crumb:read")),
    db: AsyncSession = Depends(get_db),
) -> QuoteDetailRead:
    """
    Get a quote header with its priced lines and derived totals (each line's
    line_total and the header total_value). Read-only.
    """
    quote = await crumb_service.get_quote_detail(db, quote_id)
    return QuoteDetailRead.model_validate(quote)


@router.post(
    "/crumb/quotes/{quote_id}/lines",
    response_model=QuoteLineRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_quote_line_endpoint(
    quote_id: str,
    line: QuoteLineCreate,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> QuoteLineRead:
    """Add a priced line to a draft quote. Writes a quote.line_added audit row."""
    row = await crumb_service.add_line(db, quote_id, line, str(current_user.id))
    row.line_total = row.quantity * row.unit_price
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="quote.line_added",
        target_type="crumb_quote",
        target_id=quote_id,
        detail=f"Quote {quote_id} line added: {row.id}",
    )
    return QuoteLineRead.model_validate(row)


@router.patch(
    "/crumb/quotes/{quote_id}/lines/{line_id}",
    response_model=QuoteLineRead,
)
async def update_quote_line_endpoint(
    quote_id: str,
    line_id: str,
    patch: QuoteLineCreate,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> QuoteLineRead:
    """Replace a draft quote line's priced fields. Writes a quote.line_updated row."""
    row = await crumb_service.update_line(
        db, quote_id, line_id, patch, str(current_user.id)
    )
    row.line_total = row.quantity * row.unit_price
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="quote.line_updated",
        target_type="crumb_quote",
        target_id=quote_id,
        detail=f"Quote {quote_id} line updated: {line_id}",
    )
    return QuoteLineRead.model_validate(row)


@router.delete(
    "/crumb/quotes/{quote_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_quote_line_endpoint(
    quote_id: str,
    line_id: str,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a line from a draft quote. Writes a quote.line_deleted audit row."""
    await crumb_service.delete_line(db, quote_id, line_id, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="quote.line_deleted",
        target_type="crumb_quote",
        target_id=quote_id,
        detail=f"Quote {quote_id} line deleted: {line_id}",
    )


@router.post("/crumb/quotes/{quote_id}/status", response_model=QuoteRead)
async def advance_quote_status_endpoint(
    quote_id: str,
    data: QuoteStatusRequest,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> QuoteRead:
    """Advance the quote status FSM. Writes a quote.status_changed audit row."""
    quote = await crumb_service.advance_quote_status(
        db, quote_id, data.target_status, str(current_user.id)
    )
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="quote.status_changed",
        target_type="crumb_quote",
        target_id=quote.id,
        detail=f"Quote {quote.quote_number} moved to status '{quote.status}'",
    )
    return quote


@router.post(
    "/crumb/quotes/{quote_id}/convert",
    response_model=SalesOrderDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def convert_quote_endpoint(
    quote_id: str,
    data: QuoteToSalesOrderRequest,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> SalesOrderDetailRead:
    """
    Convert an accepted quote into a draft sales order (422 if the quote is not
    accepted). Writes a quote.converted_to_sales_order audit row (target: the new
    order) after the commit.
    """
    so = await crumb_service.convert_quote_to_sales_order(
        db, quote_id, data, str(current_user.id)
    )
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="quote.converted_to_sales_order",
        target_type="sales_order",
        target_id=so.id,
        detail=f"Quote {quote_id} converted to sales order {so.so_number}",
    )
    return SalesOrderDetailRead.model_validate(so)


# ---------------------------------------------------------------------------
# Sales orders (CRUMB-01)
# ---------------------------------------------------------------------------


@router.get("/crumb/sales-orders", response_model=list[SalesOrderRead])
async def list_sales_orders_endpoint(
    current_user=Depends(require_permission("crumb:read")),
    db: AsyncSession = Depends(get_db),
) -> list[SalesOrderRead]:
    """List sales-order headers ordered by SO number. Read-only."""
    return await crumb_service.list_sales_orders(db)


@router.post(
    "/crumb/sales-orders",
    response_model=SalesOrderDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_sales_order_endpoint(
    data: SalesOrderCreate,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> SalesOrderDetailRead:
    """Create a draft sales order (header + ordered lines). Writes a sales_order.created row."""
    so = await crumb_service.create_sales_order(db, data, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="sales_order.created",
        target_type="sales_order",
        target_id=so.id,
        detail=f"Sales order created: {so.so_number}",
    )
    return SalesOrderDetailRead.model_validate(so)


@router.get("/crumb/sales-orders/{so_id}", response_model=SalesOrderDetailRead)
async def get_sales_order_endpoint(
    so_id: str,
    current_user=Depends(require_permission("crumb:read")),
    db: AsyncSession = Depends(get_db),
) -> SalesOrderDetailRead:
    """
    Get a sales-order header with its ordered lines and derived figures (each
    line's line_total and shortage, and the header total_value). Read-only.
    """
    so = await crumb_service.get_sales_order_detail(db, so_id)
    return SalesOrderDetailRead.model_validate(so)


@router.post(
    "/crumb/sales-orders/{so_id}/lines",
    response_model=SalesOrderLineRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_sales_order_line_endpoint(
    so_id: str,
    line: SalesOrderLineCreate,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> SalesOrderLineRead:
    """Add an ordered line to a draft sales order. Writes a sales_order.line_added row."""
    row = await add_so_line(db, so_id, line, str(current_user.id))
    row.line_total = row.qty_ordered * row.unit_price
    row.shortage = row.qty_ordered - row.qty_reserved
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="sales_order.line_added",
        target_type="sales_order",
        target_id=so_id,
        detail=f"Sales order {so_id} line added: {row.id}",
    )
    return SalesOrderLineRead.model_validate(row)


@router.patch(
    "/crumb/sales-orders/{so_id}/lines/{line_id}",
    response_model=SalesOrderLineRead,
)
async def update_sales_order_line_endpoint(
    so_id: str,
    line_id: str,
    patch: SalesOrderLineCreate,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> SalesOrderLineRead:
    """Replace a draft sales-order line's ordered fields. Writes a sales_order.line_updated row."""
    row = await update_so_line(db, so_id, line_id, patch, str(current_user.id))
    row.line_total = row.qty_ordered * row.unit_price
    row.shortage = row.qty_ordered - row.qty_reserved
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="sales_order.line_updated",
        target_type="sales_order",
        target_id=so_id,
        detail=f"Sales order {so_id} line updated: {line_id}",
    )
    return SalesOrderLineRead.model_validate(row)


@router.delete(
    "/crumb/sales-orders/{so_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_sales_order_line_endpoint(
    so_id: str,
    line_id: str,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a line from a draft sales order. Writes a sales_order.line_deleted row."""
    await delete_so_line(db, so_id, line_id, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="sales_order.line_deleted",
        target_type="sales_order",
        target_id=so_id,
        detail=f"Sales order {so_id} line deleted: {line_id}",
    )


@router.post("/crumb/sales-orders/{so_id}/status", response_model=SalesOrderDetailRead)
async def advance_sales_order_status_endpoint(
    so_id: str,
    data: SalesOrderStatusRequest,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> SalesOrderDetailRead:
    """
    Advance the sales-order status FSM (confirm reserves stock; cancel releases it —
    both dispatched inside the service). Writes one audit row after the commit:
    sales_order.confirmed (target=confirmed, with a reserved/shortage summary),
    sales_order.cancelled (target=cancelled), else sales_order.status_changed — each
    carrying the from→to transition.
    """
    # Read the current status BEFORE the transition so the audit row can carry
    # from→to (the service returns the post-transition detail only).
    prior = await crumb_service.get_sales_order_detail(db, so_id)
    from_status = prior.status

    so = await crumb_service.advance_sales_order_status(
        db, so_id, data.target_status, str(current_user.id)
    )

    if data.target_status == "confirmed":
        reserved = sum((ln.qty_reserved for ln in so.lines), Decimal("0"))
        shortage = sum((ln.shortage for ln in so.lines), Decimal("0"))
        action = "sales_order.confirmed"
        detail = (
            f"Sales order {so.so_number} {from_status}→{so.status} "
            f"(reserved {reserved}, shortage {shortage})"
        )
    elif data.target_status == "cancelled":
        action = "sales_order.cancelled"
        detail = f"Sales order {so.so_number} {from_status}→{so.status}"
    else:
        action = "sales_order.status_changed"
        detail = f"Sales order {so.so_number} {from_status}→{so.status}"

    await write_audit(
        db,
        actor_id=str(current_user.id),
        action=action,
        target_type="sales_order",
        target_id=so.id,
        detail=detail,
    )
    return SalesOrderDetailRead.model_validate(so)


# ---------------------------------------------------------------------------
# Interactions (CRUMB-01)
# ---------------------------------------------------------------------------


@router.post(
    "/crumb/interactions",
    response_model=InteractionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_interaction_endpoint(
    data: InteractionCreate,
    current_user=Depends(require_permission("crumb:write")),
    db: AsyncSession = Depends(get_db),
) -> InteractionRead:
    """Log one customer-touch record. Writes an interaction.logged audit row."""
    interaction = await crumb_service.create_interaction(db, data, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="interaction.logged",
        target_type="crumb_interaction",
        target_id=interaction.id,
        detail=(
            f"Interaction logged: {interaction.interaction_type} against "
            f"customer {interaction.partner_id}"
        ),
    )
    return interaction


@router.get("/crumb/interactions", response_model=list[InteractionRead])
async def list_interactions_endpoint(
    partner_id: str,
    current_user=Depends(require_permission("crumb:read")),
    db: AsyncSession = Depends(get_db),
) -> list[InteractionRead]:
    """Return a customer's interaction timeline (newest-first). Read-only."""
    return await crumb_service.list_customer_timeline(db, partner_id)
