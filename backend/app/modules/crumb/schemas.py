# ABOUTME: CRUMB (CRM) Pydantic request/response schemas — leads, opportunities,
# ABOUTME: quotes and sales orders (both with lines), and customer interactions,
# ABOUTME: plus the pipeline conversion requests (link-customer, lead→opportunity,
# ABOUTME: opp→quote, quote→sales-order) and the stage/status transition requests.
# ABOUTME: Pure Pydantic (never imports the ORM); Read models fill from ORM via
# ABOUTME: from_attributes, service-derived figures (line_total, shortage,
# ABOUTME: total_value) are plain Decimal fields.
"""
CRUMB Pydantic schemas (request/response models) — CRUMB-01.

Separation (mirrors mousse/schemas.py):
  - Input schemas (Create/Update/Request): no from_attributes — validate incoming
    JSON. Update schemas are all-optional PATCH payloads.
  - Response schemas (Read): from_attributes=True where they serialize an ORM
    instance; service-CONSTRUCTED reads carrying derived figures the service
    computes (QuoteLineRead.line_total, QuoteDetailRead.total_value) expose those
    as plain Decimal fields the service populates.

All quantity/money fields are fixed-point `Decimal` (never float — D-11),
matching the Numeric(18,6) columns in crumb/models.py. Positive-quantity guards
(quote-line `quantity` > 0) are enforced at the boundary with `Field(gt=0)`.

Three controlled lifecycles are walked by the *Request transition schemas:
  opportunity  `stage`  : qualify | proposal | won | lost
  quote        `status` : draft | sent | accepted | rejected | expired
  sales order  `status` : draft | confirmed | fulfilling | closed | cancelled
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Leads (CRUMB-01)
# ---------------------------------------------------------------------------


class LeadCreate(BaseModel):
    """
    Lead creation payload (POST /crumb/leads).

    `name` is the only required field — the minimum to enter a prospect into the
    pipeline. `company`, `contact` and `source` are optional descriptive fields.
    `status` (new → qualified → converted), `active`, and every link
    (partner_id, opportunity_id) are server-owned and so absent here.
    """

    name: str = Field(..., min_length=1)
    company: Optional[str] = None
    contact: Optional[str] = None
    source: Optional[str] = None


class LeadUpdate(BaseModel):
    """
    Lead PATCH payload (PATCH /crumb/leads/{id}).

    All fields optional — only the provided fields are updated. The conversion
    links and lifecycle status are moved by dedicated endpoints, not here.
    """

    name: Optional[str] = None
    company: Optional[str] = None
    contact: Optional[str] = None
    source: Optional[str] = None


class LeadRead(BaseModel):
    """
    Lead returned to API callers, serialized from a Lead ORM instance.

    `partner_id` is NULL until the lead is linked to a SYERP customer;
    `opportunity_id` is NULL until the lead is converted into an opportunity.
    `status` walks new | qualified | converted; `active` is the archive flag.
    """

    id: str
    name: str
    company: Optional[str] = None
    contact: Optional[str] = None
    source: Optional[str] = None
    status: str
    active: bool
    partner_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    actor_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadLinkCustomerRequest(BaseModel):
    """
    Link-a-lead-to-a-customer payload (POST /crumb/leads/{id}/link-customer).

    Exactly one of two mutually-exclusive intents (validated in the service):
      - link an EXISTING SYERP customer by `partner_id`, or
      - create a NEW SYERP customer from `new_customer_name` (with optional flags
        the service passes through to partner creation).
    Both are optional at the schema boundary; the service enforces exactly-one.
    """

    partner_id: Optional[str] = None
    new_customer_name: Optional[str] = None
    is_customer: Optional[bool] = None
    is_supplier: Optional[bool] = None


class LeadToOpportunityRequest(BaseModel):
    """
    Convert-lead-to-opportunity payload (POST /crumb/leads/{id}/convert).

    `name` names the new opportunity (required). `estimated_value` and
    `expected_close_date` seed the opportunity's value/timing; both optional.
    The partner is taken from the lead's linked customer by the service.
    """

    name: str = Field(..., min_length=1)
    estimated_value: Optional[Decimal] = None
    expected_close_date: Optional[date] = None


# ---------------------------------------------------------------------------
# Opportunities (CRUMB-01)
# ---------------------------------------------------------------------------


class OpportunityCreate(BaseModel):
    """
    Opportunity creation payload (POST /crumb/opportunities).

    `name` and `partner_id` (the SYERP customer) are required. `estimated_value`
    and `expected_close_date` are optional value/timing. `lead_id` softly links
    the originating lead when the opportunity is created from one.
    `stage` is server-owned (defaults to qualify) and so absent here.
    """

    name: str = Field(..., min_length=1)
    partner_id: str
    estimated_value: Optional[Decimal] = None
    expected_close_date: Optional[date] = None
    lead_id: Optional[str] = None


class OpportunityUpdate(BaseModel):
    """
    Opportunity PATCH payload (PATCH /crumb/opportunities/{id}).

    All fields optional. `stage` is deliberately NOT here — stage is a controlled
    lifecycle moved only via the stage-transition endpoint, never a free edit.
    """

    name: Optional[str] = None
    estimated_value: Optional[Decimal] = None
    expected_close_date: Optional[date] = None


class OpportunityRead(BaseModel):
    """
    Opportunity returned to API callers, serialized from an Opportunity ORM
    instance. `stage` walks qualify | proposal | won | lost; `estimated_value`
    is a fixed-point Decimal (Numeric(18,6)), never float.
    """

    id: str
    name: str
    partner_id: str
    lead_id: Optional[str] = None
    estimated_value: Optional[Decimal] = None
    expected_close_date: Optional[date] = None
    stage: str
    actor_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OpportunityStageRequest(BaseModel):
    """
    Opportunity stage-transition payload (POST /crumb/opportunities/{id}/stage).

    `target_stage` is the stage to move to; the service validates the move
    against the controlled qualify → proposal → won | lost transition table.
    """

    target_stage: str


# QuoteLineCreate is defined BEFORE OpportunityToQuoteRequest and QuoteCreate
# because both reference it — see the Quotes section below.


# ---------------------------------------------------------------------------
# Quotes (CRUMB-01)
# ---------------------------------------------------------------------------


class QuoteLineCreate(BaseModel):
    """
    One line of a quote-create/opp→quote request.

    A line prices either a PLUM catalog part (`plum_part_id`) or a free-text item
    (`description`) — the required-when-no-part rule is enforced in the service.
    `quantity` must be > 0 (a zero/negative line is meaningless) — Field(gt=0).
    `unit_price` is optional: when omitted the service defaults it from the PLUM
    part's cost. `markup_pct` optionally marks the line up; omitted → the service
    applies the per-line default (D-V3-14). All amounts are Decimal (never float).
    """

    plum_part_id: Optional[str] = None
    description: Optional[str] = None
    quantity: Decimal = Field(..., gt=0)
    unit_price: Optional[Decimal] = None
    markup_pct: Optional[Decimal] = None


class QuoteLineRead(BaseModel):
    """
    One priced line of a quote returned to API callers.

    Serialized from a QuoteLine ORM instance (from_attributes=True) for the
    stored fields; `line_total` is a DERIVED figure the service populates (it is
    not an ORM column) — quantity * unit_price after markup. Fixed-point Decimal.
    """

    id: str
    quote_id: str
    plum_part_id: Optional[str] = None
    description: Optional[str] = None
    quantity: Decimal
    unit_price: Decimal
    markup_pct: Optional[Decimal] = None
    sort_order: int

    # Service-derived (not an ORM column) — filled by the detail loader.
    line_total: Decimal = Decimal("0")

    model_config = ConfigDict(from_attributes=True)


class QuoteCreate(BaseModel):
    """
    Quote creation payload (POST /crumb/quotes).

    `partner_id` is the SYERP customer the quote is for (required);
    `opportunity_id` softly links the opportunity it quotes. `lines` are the
    priced lines; `quote_number` and `status` (default draft) are server-owned.
    """

    partner_id: str
    opportunity_id: Optional[str] = None
    lines: list[QuoteLineCreate] = Field(default_factory=list)


class QuoteRead(BaseModel):
    """
    Quote header returned to API callers (list rows), serialized from a Quote ORM
    instance. `status` walks draft | sent | accepted | rejected | expired.
    """

    id: str
    quote_number: str
    partner_id: str
    opportunity_id: Optional[str] = None
    status: str
    actor_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuoteDetailRead(QuoteRead):
    """
    Quote detail — the header plus its priced lines nested.

    Extends QuoteRead with `lines` (each a QuoteLineRead carrying its derived
    `line_total`) and `total_value`, a DERIVED figure the service populates
    (SUM of the lines' line_total). Fixed-point Decimal (never float).
    """

    lines: list[QuoteLineRead] = Field(default_factory=list)

    # Service-derived (not an ORM column) — filled by the detail loader.
    total_value: Decimal = Decimal("0")


class QuoteStatusRequest(BaseModel):
    """
    Quote status-transition payload (POST /crumb/quotes/{id}/status).

    `target_status` is the status to move to; the service validates the move
    against the controlled draft → sent → accepted | rejected | expired table.
    """

    target_status: str


class OpportunityToQuoteRequest(BaseModel):
    """
    Convert-opportunity-to-quote payload (POST /crumb/opportunities/{id}/quote).

    `lines` optionally seed the new quote's priced lines; when omitted the
    service creates an empty-lined draft quote against the opportunity's partner.
    """

    lines: Optional[list[QuoteLineCreate]] = None


# ---------------------------------------------------------------------------
# Interactions (CRUMB-01)
# ---------------------------------------------------------------------------


class InteractionCreate(BaseModel):
    """
    Interaction creation payload (POST /crumb/interactions).

    Logs one customer touch against SYERP customer `partner_id` (required).
    `interaction_type` is call | email | note | meeting; `body` is the content.
    `lead_id` / `opportunity_id` / `quote_id` softly link the pipeline record it
    relates to (any NULL). `occurred_at` is when the touch actually happened;
    omitted → the service defaults it to now.
    """

    partner_id: str
    interaction_type: str
    body: str
    lead_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    quote_id: Optional[str] = None
    occurred_at: Optional[datetime] = None


class InteractionRead(BaseModel):
    """
    Interaction returned to API callers, serialized from an Interaction ORM
    instance. Append-only: interactions are never updated or deleted.
    """

    id: str
    partner_id: str
    lead_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    quote_id: Optional[str] = None
    interaction_type: str
    occurred_at: datetime
    body: str
    actor_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Sales orders (CRUMB-01, Phase 11b)
# ---------------------------------------------------------------------------


class SalesOrderLineCreate(BaseModel):
    """
    One line of a sales-order-create request.

    A line orders either a SYERP stock item (`item_id`) or a non-stock/free-text
    item (`description`, with `item_id` NULL — D-V3-16); `plum_part_id` is an
    optional display link to a PLUM catalog part. `qty_ordered` must be > 0 (a
    zero/negative line is meaningless) — Field(gt=0). `unit_price` is the agreed
    price per unit. All amounts are Decimal (never float — D-11). `qty_reserved`
    is server-owned (the reservation accumulator) and so absent here.
    """

    item_id: Optional[str] = None
    plum_part_id: Optional[str] = None
    description: Optional[str] = None
    qty_ordered: Decimal = Field(..., gt=0)
    unit_price: Decimal


class SalesOrderLineRead(BaseModel):
    """
    One ordered line of a sales order returned to API callers.

    Serialized from a SalesOrderLine ORM instance (from_attributes=True) for the
    stored fields — `qty_reserved` is the server-set reservation accumulator.
    `line_total` (qty_ordered * unit_price) and `shortage` (qty_ordered −
    qty_reserved) are DERIVED figures the service populates; they are not ORM
    columns. All amounts are fixed-point Decimal (never float).
    """

    id: str
    sales_order_id: str
    item_id: Optional[str] = None
    plum_part_id: Optional[str] = None
    description: Optional[str] = None
    qty_ordered: Decimal
    unit_price: Decimal
    qty_reserved: Decimal
    sort_order: int

    # Service-derived (not ORM columns) — filled by the detail loader.
    line_total: Decimal = Decimal("0")
    shortage: Decimal = Decimal("0")

    model_config = ConfigDict(from_attributes=True)


class SalesOrderCreate(BaseModel):
    """
    Sales order creation payload (POST /crumb/sales-orders).

    `partner_id` is the SYERP customer the order is for (required). `order_date`
    and `required_date` are optional timing; omitted `order_date` → the service
    defaults it to today. `lines` are the ordered lines. `so_number` and `status`
    (default draft) are server-owned, as is each line's `qty_reserved`.
    """

    partner_id: str
    order_date: Optional[date] = None
    required_date: Optional[date] = None
    lines: list[SalesOrderLineCreate] = Field(default_factory=list)


class SalesOrderRead(BaseModel):
    """
    Sales order header returned to API callers (list rows), serialized from a
    SalesOrder ORM instance. `status` walks
    draft | confirmed | fulfilling | closed | cancelled. `source_quote_id` /
    `source_opportunity_id` softly link the quote / opportunity it originated
    from (either may be NULL for a directly-created order).
    """

    id: str
    so_number: str
    partner_id: str
    source_quote_id: Optional[str] = None
    source_opportunity_id: Optional[str] = None
    status: str
    order_date: date
    required_date: Optional[date] = None
    actor_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SalesOrderDetailRead(SalesOrderRead):
    """
    Sales order detail — the header plus its ordered lines nested.

    Extends SalesOrderRead with `lines` (each a SalesOrderLineRead carrying its
    derived `line_total` and `shortage`) and `total_value`, a DERIVED figure the
    service populates (SUM of the lines' line_total). Fixed-point Decimal.
    """

    lines: list[SalesOrderLineRead] = Field(default_factory=list)

    # Service-derived (not an ORM column) — filled by the detail loader.
    total_value: Decimal = Decimal("0")


class SalesOrderStatusRequest(BaseModel):
    """
    Sales order status-transition payload (POST /crumb/sales-orders/{id}/status).

    `target_status` is the status to move to; the service validates the move
    against the controlled
    draft → confirmed → fulfilling → closed | cancelled table.
    """

    target_status: str


class QuoteToSalesOrderRequest(BaseModel):
    """
    Convert-quote-to-sales-order payload (POST /crumb/quotes/{id}/sales-order).

    Thin by design — the conversion pulls the ordered lines from the quote's
    priced lines, so no line payload is carried here. `order_date` and
    `required_date` optionally seed the new order's timing; omitted `order_date`
    → the service defaults it to today.
    """

    order_date: Optional[date] = None
    required_date: Optional[date] = None
