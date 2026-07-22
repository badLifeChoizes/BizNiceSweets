# ABOUTME: syerp-package pytest fixtures — seed the standard chart of accounts for GL tests.
# ABOUTME: The root _isolate baseline omits the COA seed; GL browse/idempotency tests opt in here.
"""
Shared test helpers for SYERP GL tests that require the seeded chart of accounts.

The root conftest's per-test _isolate baseline deliberately omits the COA seed
to keep the bare-DB baseline minimal (so the many tests that assume an empty DB
stay green). GL browse/idempotency tests opt into the standard chart of accounts
by depending on seeded_gl_accounts — mirroring how tests/core/conftest.py's
seeded_core_db seeds its own data on top of the baseline.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest


@pytest.fixture
async def seeded_gl_accounts(skip_if_no_db: None) -> AsyncGenerator:
    """
    Seed the standard chart of accounts against the test DB and yield a session.

    Calls the idempotent seed_gl_accounts (select-before-insert, safe to re-run)
    so GL tests see the full >= 40-account CoA covering all 5 GAAP types.
    """
    from app.core.db import AsyncSessionLocal
    from app.modules.syerp.coa_seed import seed_gl_accounts

    async with AsyncSessionLocal() as session:
        await seed_gl_accounts(session)
        yield session
