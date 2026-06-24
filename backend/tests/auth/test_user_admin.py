"""
Admin user management tests — Wave 0 stub (plan 02-01).

Behaviors tested in plan 02-03 when /auth/users CRUD is implemented:
  CORE-04: Admin can create a new user account
  CORE-04: Admin can deactivate a user; deactivated user's /auth/me returns 401
  CORE-04: Non-admin creating a user gets 403
  CORE-04: Deactivation revokes live refresh tokens (D-05)

These tests are intentionally xfail until plan 02-03.
"""
import pytest
import httpx


@pytest.mark.xfail(reason="POST /auth/users implemented in plan 02-03", strict=False)
async def test_admin_create_user(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Admin can create a new user; response contains id and email."""
    # Obtain admin token
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/users",
        json={"email": "newuser@test.local", "password": "securepass123"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newuser@test.local"
    assert "id" in body


@pytest.mark.xfail(reason="User deactivation implemented in plan 02-03", strict=False)
async def test_user_deactivation(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Admin deactivates user; subsequent /auth/me with user token returns 401."""
    # Login as admin, create user, deactivate
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    access_token = login.json()["access_token"]

    create = await client.post(
        "/api/v1/auth/users",
        json={"email": "temp@test.local", "password": "temppass123"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    user_id = create.json()["id"]

    # Login as the new user
    user_login = await client.post(
        "/api/v1/auth/login",
        data={"username": "temp@test.local", "password": "temppass123"},
    )
    user_token = user_login.json()["access_token"]

    # Deactivate
    await client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # Deactivated user's token should be rejected
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert me.status_code == 401


@pytest.mark.xfail(reason="RBAC on /auth/users implemented in plan 02-03", strict=False)
async def test_non_admin_cannot_create_user(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Non-admin user attempting POST /auth/users gets 403."""
    from app.modules.auth.service import create_access_token

    # Mint a token for a user without admin permissions
    user_token = create_access_token(subject="regular-user-id", permissions=["syerp:read"])

    response = await client.post(
        "/api/v1/auth/users",
        json={"email": "newuser@test.local", "password": "pass"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403
