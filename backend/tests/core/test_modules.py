"""
CORE-07 integration tests — modules table + toggle endpoint.

These tests target the 03-02 API endpoints (GET/PATCH /api/v1/core/modules).
They are in WAVE 0 RED state until plan 03-02 ships the routers.

Test contract:
  - GET /api/v1/core/modules (any authenticated user) → 200, list with enabled/always_on
  - PATCH /api/v1/core/modules/plum {enabled:false} (admin) → 200, DB shows plum disabled
  - PATCH /api/v1/core/modules/syerp {enabled:false} (admin) → 422 (always-on guard, D-08)
  - PATCH /api/v1/core/modules/plum (non-admin token) → 403

Tests require a live PostgreSQL database (skip_if_no_db) and the seeded modules rows.
"""
import pytest
import httpx

from tests.auth.conftest_helpers import admin_login_token


# ---------------------------------------------------------------------------
# GET /core/modules — list modules with enabled flag
# ---------------------------------------------------------------------------


async def test_list_modules_returns_enabled_flag(
    client: httpx.AsyncClient,
    seeded_core_db,
) -> None:
    """GET /api/v1/core/modules with admin token returns 200 with list including
    key, enabled, and always_on fields on each item (CORE-07)."""
    token = await admin_login_token(client)

    response = await client.get(
        "/api/v1/core/modules",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list), f"Expected list, got {type(body)}"
    assert len(body) >= 7, f"Expected at least 7 modules (full catalog), got {len(body)}"
    # Verify required fields on each item
    for item in body:
        assert "key" in item, f"Missing 'key' field in {item}"
        assert "enabled" in item, f"Missing 'enabled' field in {item}"
        assert "always_on" in item, f"Missing 'always_on' field in {item}"
    # SYERP must be always_on=True (D-08)
    syerp = next((m for m in body if m["key"] == "syerp"), None)
    assert syerp is not None, "SYERP module not found in list"
    assert syerp["always_on"] is True, "SYERP must have always_on=True (D-08)"


# ---------------------------------------------------------------------------
# PATCH /core/modules/{key} — toggle enabled
# ---------------------------------------------------------------------------


async def test_toggle_module(
    client: httpx.AsyncClient,
    seeded_core_db,
) -> None:
    """Admin PATCH /api/v1/core/modules/plum {enabled:false} returns 200 and the
    DB shows plum.enabled is False. Restores enabled=True at test end (idempotent)."""
    from sqlalchemy import select
    from app.core.modules_model import Module

    token = await admin_login_token(client)

    # Disable PLUM
    response = await client.patch(
        "/api/v1/core/modules/plum",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"PATCH plum disabled failed: {response.text}"
    body = response.json()
    assert body["key"] == "plum"
    assert body["enabled"] is False

    # DB read-back
    result = await seeded_core_db.execute(select(Module).where(Module.key == "plum"))
    plum = result.scalars().first()
    assert plum is not None
    assert plum.enabled is False, "DB should show plum.enabled=False after toggle"

    # Restore — keep test suite idempotent against the shared test DB
    response = await client.patch(
        "/api/v1/core/modules/plum",
        json={"enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"PATCH plum re-enable failed: {response.text}"


# ---------------------------------------------------------------------------
# Always-on guard (D-08)
# ---------------------------------------------------------------------------


async def test_cannot_disable_always_on(
    client: httpx.AsyncClient,
    seeded_core_db,
) -> None:
    """Admin PATCH /api/v1/core/modules/syerp {enabled:false} returns 422.
    The backend must reject disabling an always-on module (D-08)."""
    token = await admin_login_token(client)

    response = await client.patch(
        "/api/v1/core/modules/syerp",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, (
        f"Expected 422 for always-on SYERP disable, got {response.status_code}: "
        f"{response.text}"
    )


# ---------------------------------------------------------------------------
# Auth gate — non-admin cannot toggle
# ---------------------------------------------------------------------------


async def test_toggle_requires_admin(
    client: httpx.AsyncClient,
    seeded_core_db,
) -> None:
    """Non-admin token with syerp:read (no settings:manage) gets 403 on
    PATCH /api/v1/core/modules/plum (D-12 admin-only toggle)."""
    from app.modules.auth.service import create_access_token

    # Mint a token with only syerp:read — lacks settings:manage
    user_token = create_access_token(
        subject="non-admin-user-id",
        permissions=["syerp:read"],
    )

    response = await client.patch(
        "/api/v1/core/modules/plum",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403, (
        f"Expected 403 for non-admin toggle, got {response.status_code}: {response.text}"
    )
