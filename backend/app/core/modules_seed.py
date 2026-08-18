"""
Idempotent module table seed — Phase 3 (CORE-07).

Seeds the `modules` table with the full seven-suite catalog on every
application startup. The seed uses a static list rather than reading
registry._registry because the registry only holds modules imported under
the current Compose profile; the static list keeps the admin catalog complete
even for not-yet-deployed modules (RESEARCH Pattern 1).

All operations are idempotent — safe on repeated `podman-compose up`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Static catalog of all seven suites.
# Tuple: (key, display_name, always_on, sort_order)
# SYERP carries always_on=True — enforced here AND at the API layer (D-08).
_MODULE_SEEDS: list[tuple[str, str, bool, int]] = [
    ("syerp", "SYERP — ERP Core", True, 10),
    ("plum", "PLUM — Product Lifecycle", False, 20),
    ("flan", "FLAN — Project Management", False, 30),
    ("mousse", "MOUSSE — Manufacturing", False, 40),
    ("crumb", "CRUMB — CRM", False, 50),
    ("gelato", "GELATO — Warehouse", False, 60),
    ("crisp", "CRISP — Quality", False, 70),
]


async def seed_modules_table(db: AsyncSession) -> None:
    """
    Idempotent module seed — insert only if key not present.

    Each tuple field is mapped explicitly so SYERP inserts with always_on=True
    rather than relying on the migration server_default (server_default=false).
    """
    from sqlalchemy import select

    from app.core.modules_model import Module

    for key, display_name, always_on, sort_order in _MODULE_SEEDS:
        result = await db.execute(select(Module).where(Module.key == key))
        if result.scalars().first() is None:
            db.add(
                Module(
                    key=key,
                    display_name=display_name,
                    enabled=True,  # new modules default ON
                    always_on=always_on,
                    sort_order=sort_order,
                )
            )

    await db.commit()
