"""
Admin user management tests — plan 02-03.

Behaviors tested (CORE-04, D-05):
  - Admin can create a new user via POST /auth/users → 201 (users:manage gated)
  - Non-admin token → 403 on POST /auth/users
  - Admin can PATCH /auth/users/{id} to update full_name / assign role
  - Deactivating a user (PATCH is_active=false) revokes their refresh tokens (D-05)
  - Deactivated user's subsequent /auth/me with old access token returns 401
  - Admin create writes AuditLog action='user.created'
  - Admin deactivate writes AuditLog action='user.deactivated'

Tests require a live PostgreSQL database (skip_if_no_db) and the seeded admin user.
"""
import httpx

from tests.auth.conftest_helpers import admin_login_token, create_regular_user

# ---------------------------------------------------------------------------
# POST /auth/users — create user
# ---------------------------------------------------------------------------


async def test_admin_create_user(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Admin can create a new user; response contains id and email (201)."""
    token = await admin_login_token(client)

    response = await client.post(
        "/api/v1/auth/users",
        json={"email": "newuser@test.local", "password": "securepass123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newuser@test.local"
    assert "id" in body
    assert body["is_active"] is True


async def test_non_admin_create_user_forbidden(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Non-admin token (lacking users:manage) gets 403 on POST /auth/users."""
    from app.modules.auth.service import create_access_token

    # Mint a token with syerp:read only (no users:manage)
    user_token = create_access_token(subject="regular-user-id", permissions=["syerp:read"])

    response = await client.post(
        "/api/v1/auth/users",
        json={"email": "blocked@test.local", "password": "pass123"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


async def test_unauthenticated_create_user_rejected(
    client: httpx.AsyncClient,
) -> None:
    """No token on POST /auth/users returns 401."""
    response = await client.post(
        "/api/v1/auth/users",
        json={"email": "anon@test.local", "password": "pass123"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /auth/users — list users
# ---------------------------------------------------------------------------


async def test_admin_list_users(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Admin can GET /auth/users and receive a list containing at least the admin."""
    token = await admin_login_token(client)

    response = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1  # at minimum the seeded admin user


async def test_non_admin_list_users_forbidden(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Non-admin token gets 403 on GET /auth/users.

    Requires DB: uses a real user's id so get_current_user can validate them,
    but mints a token without users:manage so require_permission returns 403.
    """
    from app.modules.auth.service import create_access_token
    from tests.auth.conftest_helpers import admin_login_token, create_regular_user

    admin_token = await admin_login_token(client)
    user = await create_regular_user(
        client, admin_token, "listforbidden@test.local", "pass123"
    )
    user_token = create_access_token(subject=user["id"], permissions=["syerp:read"])

    response = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /auth/users/{id} — update / deactivate
# ---------------------------------------------------------------------------


async def test_admin_update_user_full_name(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Admin can PATCH full_name on a user."""
    token = await admin_login_token(client)
    user = await create_regular_user(client, token, "patchme@test.local", "pass123")
    user_id = user["id"]

    response = await client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"full_name": "Updated Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


async def test_non_admin_update_user_forbidden(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Non-admin token gets 403 on PATCH /auth/users/{id}."""
    from app.modules.auth.service import create_access_token

    # First create target user as admin
    token = await admin_login_token(client)
    user = await create_regular_user(client, token, "target@test.local", "pass123")
    user_id = user["id"]

    # Attempt update as non-admin
    non_admin_token = create_access_token(
        subject="regular-user-id", permissions=["syerp:read"]
    )
    response = await client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"full_name": "Hacked"},
        headers={"Authorization": f"Bearer {non_admin_token}"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Deactivation — D-05: revoke refresh tokens
# ---------------------------------------------------------------------------


async def test_user_deactivation(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Admin deactivates a user:
      - The user's refresh token rows are revoked/deleted (D-05).
      - Subsequent /auth/me with the user's old access token returns 401
        (get_current_user is_active check).
    """
    admin_token = await admin_login_token(client)

    # Create a target user
    user = await create_regular_user(client, admin_token, "todeactivate@test.local", "pass123")
    user_id = user["id"]

    # Log in as the target user to get a live session
    user_login = await client.post(
        "/api/v1/auth/login",
        data={"username": "todeactivate@test.local", "password": "pass123"},
    )
    assert user_login.status_code == 200
    user_token = user_login.json()["access_token"]

    # Confirm user can reach /auth/me before deactivation
    me_before = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert me_before.status_code == 200

    # Admin deactivates
    deactivate = await client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    # After deactivation the old token must be rejected (is_active check in get_current_user)
    me_after = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert me_after.status_code == 401


async def test_deactivation_revokes_refresh_tokens(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    After deactivation, the user's RefreshToken rows should be revoked (D-05).
    Using the old refresh token to mint a new access token must fail (401).
    """
    admin_token = await admin_login_token(client)

    # Create a target user and log in
    user = await create_regular_user(
        client, admin_token, "revoketest@test.local", "pass123"
    )
    user_id = user["id"]

    user_login = await client.post(
        "/api/v1/auth/login",
        data={"username": "revoketest@test.local", "password": "pass123"},
    )
    refresh_cookie = user_login.cookies.get("refresh_token")
    assert refresh_cookie, "Expected refresh_token cookie after login"

    # Deactivate the user
    await client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Attempt to use the old refresh token — should be rejected
    refresh_attempt = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_cookie},
    )
    assert refresh_attempt.status_code == 401


# ---------------------------------------------------------------------------
# Role assignment via PATCH
# ---------------------------------------------------------------------------


async def test_admin_assign_role(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Admin can PATCH a user's role via the 'role' field."""
    admin_token = await admin_login_token(client)
    user = await create_regular_user(
        client, admin_token, "roleassign@test.local", "pass123"
    )
    user_id = user["id"]

    response = await client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"role": "user"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    roles = [r["name"] for r in response.json().get("roles", [])]
    assert "user" in roles


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


async def test_create_user_writes_audit_log(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Creating a user via POST /auth/users inserts an AuditLog action='user.created' row."""
    from sqlalchemy import select

    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import AuditLog

    admin_token = await admin_login_token(client)
    user = await create_regular_user(
        client, admin_token, "auditcreate@test.local", "pass123"
    )
    user_id = user["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "user.created",
                AuditLog.target_id == user_id,
            )
        )
        row = result.scalars().first()
    assert row is not None, "Expected AuditLog row for user.created"


async def test_deactivate_user_writes_audit_log(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Deactivating a user via PATCH inserts an AuditLog action='user.deactivated' row."""
    from sqlalchemy import select

    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import AuditLog

    admin_token = await admin_login_token(client)
    user = await create_regular_user(
        client, admin_token, "auditdeact@test.local", "pass123"
    )
    user_id = user["id"]

    await client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "user.deactivated",
                AuditLog.target_id == user_id,
            )
        )
        row = result.scalars().first()
    assert row is not None, "Expected AuditLog row for user.deactivated"
