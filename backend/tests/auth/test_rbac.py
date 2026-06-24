"""
RBAC enforcement tests — plan 02-03.

Behaviors tested (CORE-05, D-10):
  - Unit test: token with permission code contains it in JWT payload
  - Unit test: token without permission code does not contain it in JWT payload
  - Integration: user WITH users:manage reaches gated GET /auth/users (200)
  - Integration: user WITHOUT users:manage is denied gated GET /auth/users (403)
  - Integration: GET /auth/_rbac_probe with syerp:read token → 200
  - Integration: GET /auth/_rbac_probe with no syerp:read → 403

Unit tests (no DB needed) verify JWT payload.
Integration tests (need DB) verify the full require_permission + DB flow.
"""
import pytest
import httpx


# ---------------------------------------------------------------------------
# Unit tests — JWT payload content (no DB needed)
# ---------------------------------------------------------------------------


def test_require_permission_allows_matching_permission() -> None:
    """
    Unit test: a token with the required permission code passes.

    Validated by checking the JWT payload contains the permission code.
    """
    from app.modules.auth.service import create_access_token, decode_access_token

    token = create_access_token(subject="u1", permissions=["syerp:read"])
    payload = decode_access_token(token)
    assert "syerp:read" in payload["perms"]


def test_require_permission_denied_when_missing() -> None:
    """
    Unit test: a token without the required permission does NOT contain it.

    The 403 is raised by the require_permission dependency when the code
    is absent from the user's loaded roles.
    """
    from app.modules.auth.service import create_access_token, decode_access_token

    token = create_access_token(subject="u1", permissions=["syerp:read"])
    payload = decode_access_token(token)
    assert "plum:write" not in payload["perms"]


def test_admin_wildcard_in_permissions() -> None:
    """
    Unit test: collect_permissions on an admin user returns '*' wildcard.

    Tested without DB using a mock-like object.
    """
    from unittest.mock import MagicMock

    from app.modules.auth.service import collect_permissions

    admin_perm = MagicMock()
    admin_perm.code = "users:manage"
    admin_role = MagicMock()
    admin_role.name = "admin"
    admin_role.permissions = [admin_perm]

    user = MagicMock()
    user.roles = [admin_role]

    perms = collect_permissions(user)
    assert "*" in perms, f"Expected wildcard in admin permissions; got {perms}"


# ---------------------------------------------------------------------------
# Integration tests — gated endpoint with users:manage (need DB)
# ---------------------------------------------------------------------------


async def test_gated_endpoint_allows_admin_token(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Admin token (has users:manage via wildcard) can GET /auth/users → 200."""
    from tests.auth.conftest_helpers import admin_login_token

    token = await admin_login_token(client)
    response = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


async def test_gated_endpoint_denies_token_without_permission(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Token with syerp:read (no users:manage) is denied on GET /auth/users → 403.

    Requires DB: get_current_user looks up the user by id to validate is_active.
    Uses the seeded admin user id via login, then tests with a reduced-permission token.
    """
    from tests.auth.conftest_helpers import admin_login_token
    from app.modules.auth.service import create_access_token
    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import User
    from sqlalchemy import select

    # Get the real admin user's id from DB so the token resolves
    async with AsyncSessionLocal() as session:
        from app.core.config import settings
        result = await session.execute(
            select(User).where(User.email == settings.bns_admin_email)
        )
        admin = result.scalars().first()

    # Mint a token for the real admin user but strip the admin permission
    # so require_permission("users:manage") denies them
    if admin is None:
        import pytest
        pytest.skip("Admin user not seeded in DB")

    # Create a user without users:manage for this test
    token = create_access_token(subject=str(admin.id), permissions=["syerp:read"])
    response = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_gated_endpoint_denies_empty_permissions(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Token with empty permissions is denied on GET /auth/users → 403.

    Requires DB: get_current_user validates the user exists in DB.
    """
    from app.modules.auth.service import create_access_token
    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import User
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        from app.core.config import settings
        result = await session.execute(
            select(User).where(User.email == settings.bns_admin_email)
        )
        admin = result.scalars().first()

    if admin is None:
        import pytest
        pytest.skip("Admin user not seeded in DB")

    token = create_access_token(subject=str(admin.id), permissions=[])
    response = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Integration tests — RBAC probe endpoint (syerp:read gate)
# Requires DB: get_current_user validates the user exists and is_active in DB.
# ---------------------------------------------------------------------------


async def test_rbac_probe_allows_syerp_read(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    GET /auth/_rbac_probe with syerp:read permission returns 200.

    Uses the seeded admin user (who has wildcard '*' which satisfies any perm check).
    """
    from tests.auth.conftest_helpers import admin_login_token

    token = await admin_login_token(client)
    response = await client.get(
        "/api/v1/auth/_rbac_probe",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


async def test_rbac_probe_denies_without_syerp_read(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    GET /auth/_rbac_probe with only plum:read (no syerp:read) returns 403.

    Creates a non-admin user with no syerp:read and uses their token.
    """
    from tests.auth.conftest_helpers import admin_login_token, create_regular_user
    from app.modules.auth.service import create_access_token
    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import User
    from sqlalchemy import select

    admin_token = await admin_login_token(client)
    # Create a regular user (no roles assigned by default → no permissions)
    user = await create_regular_user(
        client, admin_token, "rbacprobe@test.local", "pass123"
    )
    # Mint a token with only plum:read for this real user_id so DB lookup succeeds
    token = create_access_token(subject=user["id"], permissions=["plum:read"])
    response = await client.get(
        "/api/v1/auth/_rbac_probe",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_rbac_probe_denies_no_permissions(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """GET /auth/_rbac_probe with no permissions returns 403."""
    from tests.auth.conftest_helpers import admin_login_token, create_regular_user
    from app.modules.auth.service import create_access_token

    admin_token = await admin_login_token(client)
    user = await create_regular_user(
        client, admin_token, "rbacnoperms@test.local", "pass123"
    )
    token = create_access_token(subject=user["id"], permissions=[])
    response = await client.get(
        "/api/v1/auth/_rbac_probe",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_rbac_probe_allows_admin_wildcard(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """GET /auth/_rbac_probe with admin token (wildcard) returns 200."""
    from tests.auth.conftest_helpers import admin_login_token

    # Admin login returns a token with '*' wildcard via collect_permissions
    token = await admin_login_token(client)
    response = await client.get(
        "/api/v1/auth/_rbac_probe",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
