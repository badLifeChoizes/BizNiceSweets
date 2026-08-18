"""
Token refresh tests — plan 02-02.

Behaviors tested (CORE-03):
  - Valid refresh cookie → new access_token returned; new refresh cookie set
  - Missing refresh cookie → 401
  - Revoked refresh token → 401 (via logout then refresh)

Tests requiring a live DB use skip_if_no_db.
"""
import httpx


async def test_token_refresh(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Valid refresh cookie returns new access_token and rotates refresh cookie."""
    # First log in to obtain a refresh cookie
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert login.status_code == 200

    # Use the refresh cookie to get a new access token
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    # New refresh cookie must be set (rotation)
    assert "refresh_token" in response.cookies


async def test_refresh_missing_cookie(client: httpx.AsyncClient) -> None:
    """No refresh cookie → 401."""
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_refresh_revoked_token(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Revoked refresh token returns 401."""
    # Log in, then log out (revoke), then try to refresh
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert login.status_code == 200

    # Get the access token for logout
    login_body = login.json()
    access_token = login_body["access_token"]

    await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
