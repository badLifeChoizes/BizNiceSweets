"""
Shared test helpers for auth integration tests that require a live database.

This module provides reusable async fixtures and helpers for tests that
interact with the auth models, seed functions, and DB-backed service calls.

Design choice: use the real PostgreSQL test database (skip_if_no_db pattern)
rather than an in-memory SQLite substitute.  The auth seed uses PostgreSQL-
specific insert semantics that SQLite does not support, and aiosqlite is not
installed in this environment.  Tests skip cleanly when no DB is available.

Usage in test files:
    from tests.auth.conftest_helpers import (
        async_db_session,
        seeded_db,
        admin_login_token,
        create_regular_user,
    )
"""
from __future__ import annotations

from typing import AsyncGenerator

import pytest


# ---------------------------------------------------------------------------
# Async DB session factory (real PostgreSQL; skip when unavailable)
# ---------------------------------------------------------------------------


@pytest.fixture
async def async_db_session(skip_if_no_db: None) -> AsyncGenerator:
    """
    Yield an AsyncSession connected to the test PostgreSQL database.

    Requires skip_if_no_db to ensure the test is skipped when no DB is
    available.  Each fixture call opens its own session and closes it on
    exit — no shared state across tests.
    """
    from app.core.db import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Seeded DB: runs seed_admin_user and yields the session
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded_db(skip_if_no_db: None) -> AsyncGenerator:
    """
    Run seed_admin_user against the test DB and yield an AsyncSession.

    This fixture is idempotent — if the admin already exists from a prior
    test run it will not fail (the seed is designed to be a no-op in that
    case).  Tests that depend on a fresh DB should wrap with transaction
    rollback (not implemented here — acceptable for the current test scope).
    """
    from app.core.db import AsyncSessionLocal
    from app.modules.auth.seed import seed_admin_user

    async with AsyncSessionLocal() as session:
        await seed_admin_user(session)
        yield session


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


async def admin_login_token(client) -> str:
    """
    Log in as the seeded admin user and return a Bearer access token string.

    Expects BNS_ADMIN_EMAIL / BNS_ADMIN_PASSWORD from the environment
    (injected by conftest.py before imports).
    """
    from app.core.config import settings

    email = settings.bns_admin_email
    password = settings.bns_admin_password.get_secret_value()

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["access_token"]


async def create_regular_user(client, admin_token: str, email: str, password: str) -> dict:
    """
    Create a regular (non-admin) user via POST /api/v1/auth/users.

    Returns the created user dict (UserRead).
    """
    response = await client.post(
        "/api/v1/auth/users",
        json={"email": email, "password": password},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201, f"User creation failed: {response.text}"
    return response.json()
