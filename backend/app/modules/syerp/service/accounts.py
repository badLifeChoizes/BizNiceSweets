"""SYERP service — GL account lookup helpers."""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, NamedTuple

from fastapi import HTTPException, status
from sqlalchemy import Integer, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.modules.syerp.models import (
        Bill,
        BillLine,
        GLAccount,
        InventoryItem,
        JournalEntry,
        JournalLine,
        Partner,
        PurchaseOrder,
        PurchaseOrderLine,
        StockLocation,
    )
    from app.modules.syerp.schemas import (
        AccountRegisterRead,
        ApAgingReport,
        BalanceSheetReport,
        BillLineCreate,
        BillRead,
        InventoryItemCreate,
        InventoryItemUpdate,
        ItemOnHandRead,
        JournalEntryRead,
        PartnerCreate,
        PartnerUpdate,
        POCreate,
        POLineCreate,
        POLineRead,
        POLineUpdate,
        PORead,
        ProfitLossReport,
        StockLocationCreate,
        StockLocationUpdate,
        TransactionRead,
        TrialBalanceReport,
        UnbilledReceiptRead,
    )


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


async def _gl_account_id_by_code(db: AsyncSession, code: str) -> int:
    """
    Resolve a GL account id by its Chart-of-Accounts `code` (e.g. '1130').

    Used by the receipt auto-post to resolve the Inventory (1130) and GR/IR (2150)
    control accounts by their stable codes. These accounts are seeded at startup
    (coa_seed.py); a missing one is a server MISCONFIGURATION, not a client error —
    so it raises HTTP 500 rather than 404.
    """
    from app.modules.syerp.models import GLAccount

    result = await db.execute(select(GLAccount.id).where(GLAccount.code == code))
    account_id = result.scalars().first()
    if account_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GL account {code} not seeded.",
        )
    return account_id
