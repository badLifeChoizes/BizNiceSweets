# ABOUTME: Idempotent seed for the default "Main" stock location (D-P8-14).
# ABOUTME: Mirrors coa_seed's select-before-insert upsert-by-name pattern so a
# ABOUTME: fresh deploy can receive stock out-of-the-box and re-runs add none.
"""
Default stock-location seed (D-P8-14, Decision 3 = yes).

Called from app.core.seed:run_seeds() on every application startup, so
receiving works out-of-the-box on a fresh deploy without an admin first having
to create a location.

The operation is idempotent — safe to call on repeated `podman-compose up`.
It uses the same select-before-insert (upsert-by-name) pattern as
app.modules.syerp.coa_seed.seed_gl_accounts: a location with name "Main" is
inserted only when no row with that name already exists, so re-running the seed
adds nothing.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# The single default location seeded on a fresh deploy (D-P8-14).
DEFAULT_LOCATION_NAME = "Main"


async def seed_default_location(db: "AsyncSession") -> None:
    """
    Idempotent seed of the default "Main" stock location.

    Select-before-insert (upsert-by-name): inserts a StockLocation named
    DEFAULT_LOCATION_NAME only if no location with that name already exists.
    Running it twice yields exactly one "Main" row.

    Single await db.commit() at the end (mirrors coa_seed.seed_gl_accounts).
    """
    from sqlalchemy import select

    from app.modules.syerp.models import StockLocation

    existing = await db.execute(
        select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
    )
    if existing.scalars().first() is not None:
        return  # already exists — idempotent skip, nothing to commit

    db.add(StockLocation(name=DEFAULT_LOCATION_NAME, active=True))
    await db.commit()
