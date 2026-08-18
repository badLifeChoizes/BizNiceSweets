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


async def run_seeds(db: AsyncSession) -> None:
    """
    Populate the database with initial seed data.

    Called from the FastAPI lifespan startup hook in app.main.  All seed
    functions must be idempotent (safe to run on every podman-compose up).

    Phase 2: seeds the first admin user, the admin/user roles, and the
    initial permission set (including settings:manage for Phase 3).
    Phase 3: seeds the modules table (7 suites, SYERP always_on=True)
    and the default settings (company identity + locale defaults).
    Phase 4: seeds the standard chart-of-accounts (syerp_gl_account rows
    via seed_gl_accounts — idempotent, 40 accounts, 5 GAAP types).
    Phase 5: seeds PLUM classification tag vocabulary (6 tags) and default
    PLUM settings (revision_scheme, tag_vocabulary_editable).
    Phase 8: seeds the default "Main" stock location (seed_default_location —
    idempotent upsert-by-name) so receiving works out-of-the-box (D-P8-14).

    Order matters: admin/permissions must exist before modules and settings
    seeds run (settings:manage is granted to admin role in seed_admin_user).
    """
    from app.core.modules_seed import seed_modules_table
    from app.core.settings_seed import seed_default_settings
    from app.modules.auth.seed import seed_admin_user
    from app.modules.plum.seed import seed_plum_data
    from app.modules.syerp.coa_seed import seed_gl_accounts
    from app.modules.syerp.inventory_seed import seed_default_location

    await seed_admin_user(db)
    await seed_modules_table(db)
    await seed_default_settings(db)
    await seed_gl_accounts(db)
    await seed_default_location(db)
    await seed_plum_data(db)
