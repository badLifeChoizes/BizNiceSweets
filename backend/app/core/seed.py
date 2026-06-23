"""
Seed hook pattern (D-10).

run_seeds() is the extension point for initial data population.
Phase 1: no-op (hook only, no real data inserts).
Phase 2 will attach the first admin user/role seed here once the auth
models exist.

Usage (future entrypoint or lifespan):
    from app.core.seed import run_seeds
    await run_seeds(db)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def run_seeds(db: "AsyncSession") -> None:  # noqa: ARG001
    """
    Populate the database with initial seed data.

    Phase 1: intentionally empty — seed hook only, no data inserted.

    Phase 2 extension point:
        from app.modules.auth.seed import seed_admin_user
        await seed_admin_user(db)
    """
    # -----------------------------------------------------------------------
    # Phase 2+: add seed calls here
    # -----------------------------------------------------------------------
    pass
