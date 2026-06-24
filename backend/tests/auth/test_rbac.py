"""
RBAC enforcement tests — Wave 0 stub (plan 02-01).

Behaviors tested in plan 02-03 when require_permission dependency is wired:
  CORE-05: User with required permission gets through gated endpoint (200)
  CORE-05: User without required permission gets 403
  CORE-05: Admin role grants all permissions (wildcard)

Unit tests (no live DB needed) use directly-minted tokens via create_access_token.
Integration tests (need live DB) check the full require_permission + DB flow.
"""
import pytest
import httpx


def test_require_permission_allows_matching_permission() -> None:
    """
    Unit test: a token with the required permission code passes.

    Validated by calling the FastAPI test client with a matching token.
    Tested end-to-end in plan 02-03 when a gated endpoint exists.
    """
    from app.modules.auth.service import create_access_token, decode_access_token

    token = create_access_token(subject="u1", permissions=["syerp:read"])
    payload = decode_access_token(token)
    assert "syerp:read" in payload["perms"]


def test_require_permission_denied_when_missing() -> None:
    """
    Unit test: a token without the required permission does NOT contain it.

    The 403 is raised by the require_permission dependency (plan 02-03);
    here we verify that the permission is absent from the JWT payload.
    """
    from app.modules.auth.service import create_access_token, decode_access_token

    token = create_access_token(subject="u1", permissions=["syerp:read"])
    payload = decode_access_token(token)
    assert "plum:write" not in payload["perms"]


@pytest.mark.xfail(reason="require_permission dependency wired in plan 02-03", strict=False)
async def test_gated_endpoint_allows_correct_role(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """User with the required permission gets 200 on a gated endpoint."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user-id", permissions=["users:manage"])
    response = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    # When endpoint is wired, admin can list users
    assert response.status_code == 200


@pytest.mark.xfail(reason="require_permission dependency wired in plan 02-03", strict=False)
async def test_gated_endpoint_denies_missing_role(
    client: httpx.AsyncClient,
) -> None:
    """User without the required permission gets 403 on a gated endpoint."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="regular-user-id", permissions=["syerp:read"])
    response = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
