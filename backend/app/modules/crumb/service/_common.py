# ABOUTME: Shared CRUMB service surface — the opportunity-stage and quote-status
# ABOUTME: FSM transition tables, the per-line default markup, and the customer
# ABOUTME: resolver that loads a SYERP partner and asserts it is a customer.
"""Shared CRUMB service constants and helpers.

Split into cohesive submodules like syerp/service (D-P10-6 — keep new suites'
service layers thin and per-entity; D-V3-9 — CRUMB is the CRM suite over the
SYERP hub). This module holds the surface every entity module depends on: the
two controlled-lifecycle transition tables, the default quote-line markup, and
the customer resolver.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.syerp.models import Partner


# ---------------------------------------------------------------------------
# Controlled lifecycle transition tables (FSMs)
# ---------------------------------------------------------------------------
#
# Opportunity stage and quote status each walk a controlled lifecycle; a move is
# permitted only if the target is in the current state's allowed set. Terminal
# states map to the empty set (no further transitions). Validated by the
# stage/status service functions and mirrored by the *Request schemas.

# Opportunity stage: qualify → proposal → won | lost (won/lost terminal).
STAGE_TRANSITIONS: dict[str, set[str]] = {
    "qualify": {"proposal", "won", "lost"},
    "proposal": {"won", "lost"},
    "won": set(),
    "lost": set(),
}

# Quote status: draft → sent → accepted | rejected | expired (all three terminal).
QUOTE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"sent"},
    "sent": {"accepted", "rejected", "expired"},
    "accepted": set(),
    "rejected": set(),
    "expired": set(),
}

# Sales-order status: draft → confirmed → fulfilling → closed (closed terminal).
# Cancel is allowed only from draft/confirmed — never from fulfilling/closed (AC4).
SO_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"confirmed", "cancelled"},
    "confirmed": {"fulfilling", "cancelled"},
    "fulfilling": {"closed"},
    "closed": set(),
    "cancelled": set(),
}


# ---------------------------------------------------------------------------
# Default quote-line markup (D-V3-14)
# ---------------------------------------------------------------------------
#
# 30% initial per-line markup applied to a quote line when none is supplied;
# editable per line thereafter. Decimal (never float — D-11).
DEFAULT_MARKUP_PCT = Decimal("30")


# ---------------------------------------------------------------------------
# Customer resolver
# ---------------------------------------------------------------------------


async def _resolve_customer(db: "AsyncSession", partner_id: str) -> "Partner":
    """Load the SYERP partner `partner_id` and assert it is a customer.

    Raises HTTPException(404) if the partner does not exist or is not flagged
    `is_customer` — CRUMB only ever quotes/opportunities against customers.
    Partner is imported lazily inside the function so importing this module never
    pulls in the SYERP model layer (avoids an import cycle — SYERP is the hub).
    """
    # Lazy import (inside the function) to avoid an import cycle with the hub.
    from app.modules.syerp.models import Partner

    partner = await db.get(Partner, partner_id)
    if partner is None or not partner.is_customer:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail=f"Customer partner '{partner_id}' not found",
        )
    return partner
