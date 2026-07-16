# ABOUTME: CRUMB interactions service — append-only customer touch log and the
# ABOUTME: per-customer timeline (newest-first). No update/delete: history is permanent.
"""CRUMB interactions service (business logic).

An interaction is one immutable record of a customer touch (call | email | note |
meeting) against a SYERP customer, optionally linked to a pipeline record. The
log is APPEND-ONLY: there is deliberately no update or delete — the history of
contact is a permanent audit trail (CRUMB-01 / models.Interaction).

Per D-V3-9 this mirrors syerp/service: a thin entity module with lazy imports
inside functions (SYERP is the hub) and one commit per operation. Audit events
are written at the router layer, not here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.crumb.service._common import _resolve_customer

if TYPE_CHECKING:
    from app.modules.crumb.models import Interaction
    from app.modules.crumb.schemas import InteractionCreate


# Allowed interaction types (mirrors models.Interaction docstring).
_INTERACTION_TYPES = {"call", "email", "note", "meeting"}


async def create_interaction(
    db: AsyncSession, data: "InteractionCreate", actor_id: str
) -> "Interaction":
    """
    Append one immutable customer-touch record (CRUMB-01).

    Resolves the SYERP customer (404 if not a customer), validates
    interaction_type against {call, email, note, meeting} (422 otherwise), and
    defaults occurred_at to now (tz-aware UTC) when omitted. Commits and returns
    the new row. APPEND-ONLY — there is no update/delete counterpart.
    """
    from app.modules.crumb.models import Interaction

    await _resolve_customer(db, data.partner_id)

    if data.interaction_type not in _INTERACTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid interaction_type '{data.interaction_type}'. "
                f"Allowed: {sorted(_INTERACTION_TYPES)}"
            ),
        )

    interaction = Interaction(
        partner_id=data.partner_id,
        interaction_type=data.interaction_type,
        body=data.body,
        lead_id=data.lead_id,
        opportunity_id=data.opportunity_id,
        quote_id=data.quote_id,
        occurred_at=data.occurred_at or datetime.now(timezone.utc),
        actor_id=actor_id,
    )
    db.add(interaction)
    await db.commit()
    await db.refresh(interaction)
    return interaction


async def list_customer_timeline(
    db: AsyncSession, partner_id: str
) -> list["Interaction"]:
    """
    Return a customer's full interaction timeline, newest-first.

    Ordered by occurred_at descending (when the touch happened, not when logged).
    """
    from app.modules.crumb.models import Interaction

    result = await db.execute(
        select(Interaction)
        .where(Interaction.partner_id == partner_id)
        .order_by(Interaction.occurred_at.desc())
    )
    return list(result.scalars().all())
