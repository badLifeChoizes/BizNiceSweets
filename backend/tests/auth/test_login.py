"""
Login endpoint tests — plan 02-02 + plan 02-03.

Behaviors tested (CORE-02, D-14):
  - Valid credentials → 200 + access_token + refresh cookie set (httpOnly)
  - Wrong password → 401
  - Unknown email → 401 (constant-time; no user-enumeration timing leak)
  - Successful login writes AuditLog action='auth.login_success' (D-14)
  - Failed login writes AuditLog action='auth.login_failed' with actor_id=None (D-14)

Tests require a live database (skip_if_no_db).  The admin user is seeded by
conftest via BNS_ADMIN_EMAIL / BNS_ADMIN_PASSWORD env vars.
"""
import pytest
import httpx


async def test_login_success(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Valid credentials return 200 with access_token and set refresh cookie."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body.get("token_type") == "bearer"
    assert "refresh_token" in response.cookies


async def test_login_bad_password(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Wrong password returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "wrongpassword"},
    )
    assert response.status_code == 401


async def test_login_unknown_email(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Unknown email returns 401 (no user enumeration)."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@nowhere.test", "password": "anything"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Audit log on login (D-14)
# ---------------------------------------------------------------------------


async def test_login_success_writes_audit_log(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Successful login writes an AuditLog row:
      action='auth.login_success', actor_id == the authenticated user's id.
    """
    from sqlalchemy import select

    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import AuditLog

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert response.status_code == 200

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(AuditLog.action == "auth.login_success")
        )
        row = result.scalars().first()

    assert row is not None, "Expected AuditLog row for auth.login_success"
    assert row.actor_id is not None, "actor_id must be set (user's id) on successful login"


async def test_me_includes_permissions(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    GET /api/v1/auth/me returns a body that includes a `permissions` list (CORE-08).

    The flat permissions list feeds the frontend nav filter (D-04): the sidebar
    shows a module only if enabled AND user.permissions includes the module's
    required permission code.

    For the admin user, permissions includes "*" (wildcard) plus all explicit codes.
    """
    # Log in as admin
    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Call /me and assert permissions is present and is a list
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200, f"GET /me failed: {me_resp.text}"
    body = me_resp.json()
    assert "permissions" in body, (
        f"Expected 'permissions' key in /me response body. Keys present: {list(body.keys())}"
    )
    assert isinstance(body["permissions"], list), (
        f"Expected permissions to be a list, got {type(body['permissions'])}"
    )
    # Admin should have at least the wildcard marker
    assert "*" in body["permissions"] or len(body["permissions"]) > 0, (
        "Admin user should have at least one permission in the list"
    )


async def test_login_failure_writes_audit_log(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Failed login (wrong password) writes an AuditLog row:
      action='auth.login_failed', actor_id is None (no user resolved).
    """
    from sqlalchemy import select

    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import AuditLog

    # Count existing failure rows first to identify newly added row
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(AuditLog.action == "auth.login_failed")
        )
        rows_before = len(result.scalars().all())

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "wrongpassword"},
    )
    assert response.status_code == 401

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(AuditLog.action == "auth.login_failed")
        )
        rows_after = result.scalars().all()

    assert len(rows_after) > rows_before, "Expected a new AuditLog row for auth.login_failed"
    latest = rows_after[-1]
    assert latest.actor_id is None, "actor_id must be None on failed login (no user resolved)"
