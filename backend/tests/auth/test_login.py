"""
Login endpoint tests — Wave 0 stub (plan 02-01).

Behaviors tested in plan 02-02 when POST /auth/login is implemented:
  CORE-02: Valid credentials → 200 + access_token + refresh cookie set
  CORE-02: Wrong password → 401
  CORE-02: Unknown email → 401 (constant-time; no user-enumeration timing leak)

These tests are intentionally xfail because the /auth/login endpoint does not
exist until plan 02-02.  They will be promoted to full tests in that plan.
"""
import pytest
import httpx


@pytest.mark.xfail(reason="POST /auth/login implemented in plan 02-02", strict=False)
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


@pytest.mark.xfail(reason="POST /auth/login implemented in plan 02-02", strict=False)
async def test_login_bad_password(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Wrong password returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.xfail(reason="POST /auth/login implemented in plan 02-02", strict=False)
async def test_login_unknown_email(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Unknown email returns 401 (no user enumeration)."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@nowhere.test", "password": "anything"},
    )
    assert response.status_code == 401
