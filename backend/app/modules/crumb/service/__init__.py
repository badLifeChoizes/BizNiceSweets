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
    STAGE_TRANSITIONS,
    _resolve_customer,
)

# Per-entity re-exports go here as tasks 6–9 land:
#   from app.modules.crumb.service.leads import ...
#   from app.modules.crumb.service.opportunities import ...
#   from app.modules.crumb.service.interactions import ...
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

__all__ = [
    "DEFAULT_MARKUP_PCT",
    "QUOTE_TRANSITIONS",
    "STAGE_TRANSITIONS",
    "_resolve_customer",
    # quotes
    "add_line",
    "advance_quote_status",
    "create_quote",
    "delete_line",
    "generate_quote_number",
    "get_quote_detail",
    "list_quotes",
    "update_line",
]
