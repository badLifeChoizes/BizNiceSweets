# ABOUTME: CRUMB service layer package — re-exports the shared surface (FSM
# ABOUTME: transition tables, default markup, customer resolver) now; per-entity
# ABOUTME: modules (leads, opportunities, quotes, interactions) are re-exported
# ABOUTME: here as tasks 6–9 add them.
"""CRUMB service layer (business logic).

Split into cohesive per-entity submodules like syerp/service (D-P10-6 — keep new
suites' service layers thin; D-V3-9 — CRUMB is the CRM suite over the SYERP hub).
This package re-exports the full public surface so `from app.modules.crumb.service
import X` and `service.X` work unchanged.
"""
from __future__ import annotations

from app.modules.crumb.service._common import (
    DEFAULT_MARKUP_PCT,
    QUOTE_TRANSITIONS,
    SO_TRANSITIONS,
    STAGE_TRANSITIONS,
    _resolve_customer,
)
from app.modules.crumb.service.interactions import (
    create_interaction,
    list_customer_timeline,
)
from app.modules.crumb.service.leads import (
    archive_lead,
    convert_to_opportunity,
    create_lead,
    get_lead,
    link_or_create_customer,
    list_leads,
    update_lead,
)
from app.modules.crumb.service.opportunities import (
    advance_stage,
    create_opportunity,
    get_opportunity,
    list_opportunities,
    list_pipeline,
    spawn_quote,
    update_opportunity,
)
from app.modules.crumb.service.quotes import (
    add_line,
    advance_quote_status,
    create_quote,
    delete_line,
    generate_quote_number,
    get_quote_detail,
    list_quotes,
    update_line,
)

# NOTE: sales_orders.py also defines add_line / update_line / delete_line (the
# Draft-only SO line editors, mirroring quotes). Those three names collide with
# the quotes editors already re-exported above, so they are intentionally NOT
# re-exported here — the sales-order router imports them from the submodule
# directly (from ...service.sales_orders import add_line as ...). Everything else
# in the sales-order public surface is re-exported below.
from app.modules.crumb.service.sales_orders import (
    advance_sales_order_status,
    cancel_sales_order,
    confirm_sales_order,
    convert_quote_to_sales_order,
    create_sales_order,
    generate_sales_order_number,
    get_sales_order_detail,
    list_sales_orders,
)

__all__ = [
    "DEFAULT_MARKUP_PCT",
    "QUOTE_TRANSITIONS",
    "SO_TRANSITIONS",
    "STAGE_TRANSITIONS",
    "_resolve_customer",
    # interactions
    "create_interaction",
    "list_customer_timeline",
    # leads
    "archive_lead",
    "convert_to_opportunity",
    "create_lead",
    "get_lead",
    "link_or_create_customer",
    "list_leads",
    "update_lead",
    # opportunities
    "advance_stage",
    "create_opportunity",
    "get_opportunity",
    "list_opportunities",
    "list_pipeline",
    "spawn_quote",
    "update_opportunity",
    # quotes
    "add_line",
    "advance_quote_status",
    "create_quote",
    "delete_line",
    "generate_quote_number",
    "get_quote_detail",
    "list_quotes",
    "update_line",
    # sales orders
    "advance_sales_order_status",
    "cancel_sales_order",
    "confirm_sales_order",
    "convert_quote_to_sales_order",
    "create_sales_order",
    "generate_sales_order_number",
    "get_sales_order_detail",
    "list_sales_orders",
]
