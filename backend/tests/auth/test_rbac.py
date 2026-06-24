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
) -> None:
    """Token with syerp:read (no users:manage) is denied on GET /auth/users → 403."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="regular-user-id", permissions=["syerp:read"])
    response = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_gated_endpoint_denies_empty_permissions(
    client: httpx.AsyncClient,
) -> None:
    """Token with empty permissions is denied on GET /auth/users → 403."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="no-perms-user", permissions=[])
    response = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Integration tests — RBAC probe endpoint (syerp:read gate)
# ---------------------------------------------------------------------------


async def test_rbac_probe_allows_syerp_read(
    client: httpx.AsyncClient,
) -> None:
    """GET /auth/_rbac_probe with syerp:read permission returns 200."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="u1", permissions=["syerp:read"])
    response = await client.get(
        "/api/v1/auth/_rbac_probe",
        headers={"Authorization": f"Bearer {token}"},
    )
    # The probe endpoint is gated by syerp:read; user has it → 200
    assert response.status_code == 200


async def test_rbac_probe_denies_without_syerp_read(
    client: httpx.AsyncClient,
) -> None:
    """GET /auth/_rbac_probe without syerp:read permission returns 403."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="u2", permissions=["plum:read"])
    response = await client.get(
        "/api/v1/auth/_rbac_probe",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_rbac_probe_denies_no_permissions(
    client: httpx.AsyncClient,
) -> None:
    """GET /auth/_rbac_probe with no permissions returns 403."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="u3", permissions=[])
    response = await client.get(
        "/api/v1/auth/_rbac_probe",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


async def test_rbac_probe_allows_admin_wildcard(
    client: httpx.AsyncClient,
) -> None:
    """GET /auth/_rbac_probe with '*' wildcard (admin) returns 200."""
    from app.modules.auth.service import create_access_token

    # Admin token embeds wildcard '*' via collect_permissions
    token = create_access_token(subject="admin-id", permissions=["*", "users:manage"])
    response = await client.get(
        "/api/v1/auth/_rbac_probe",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
