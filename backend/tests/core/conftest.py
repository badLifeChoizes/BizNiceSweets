# ABOUTME: Core-package pytest fixtures — seeded_core_db runs the modules + settings seeds.
# ABOUTME: Builds on the root conftest's DB provisioning and per-test truncate/reseed isolation.
"""
Shared test helpers for core (modules + settings) integration tests.

Provides seeded_core_db that opens a session, runs seed_admin_user,
seed_modules_table, and seed_default_settings, then yields the session —
mirroring the seeded_db pattern in tests/auth/conftest_helpers.py.

All fixtures depend on skip_if_no_db so they skip cleanly without a live DB.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from tests.auth.conftest_helpers import admin_login_token  # noqa: F401 (re-exported)


@pytest.fixture
async def seeded_core_db(skip_if_no_db: None) -> AsyncGenerator:
    """
    Run admin + modules + settings seeds against the test DB and yield an
    AsyncSession.

    Idempotent: if rows already exist from a prior test run the seeds are
    no-ops (select-before-insert pattern). All three seeds must run in order
    (admin/permissions must exist before modules/settings are seeded).
    """
    from app.core.db import AsyncSessionLocal
    from app.core.modules_seed import seed_modules_table
    from app.core.settings_seed import seed_default_settings
    from app.modules.auth.seed import seed_admin_user

    async with AsyncSessionLocal() as session:
        await seed_admin_user(session)
        await seed_modules_table(session)
        await seed_default_settings(session)
        yield session
