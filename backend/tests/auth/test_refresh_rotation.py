"""
Refresh-token rotation and reuse-detection tests — Wave 0 stub (plan 02-01).

Behaviors tested in plan 02-02:
  CORE-03 / D-07: Using a refresh token issues a new one and revokes the prior
  CORE-03 / D-07: Replaying the old (now-revoked) token revokes the whole family → 401

These tests are intentionally xfail until plan 02-02 implements rotation.
"""
import pytest
import httpx


@pytest.mark.xfail(reason="Refresh-token rotation implemented in plan 02-02", strict=False)
async def test_refresh_rotation_invalidates_old_token(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Using a refresh token issues a new one; the old token is revoked."""
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert login.status_code == 200
    old_cookie = client.cookies.get("refresh_token")
    assert old_cookie is not None

    # First refresh — succeeds; rotates the cookie
    r1 = await client.post("/api/v1/auth/refresh")
    assert r1.status_code == 200
    new_cookie = client.cookies.get("refresh_token")
    assert new_cookie != old_cookie

    # Replay the old token — must fail (D-07 reuse detection)
    client.cookies.set("refresh_token", old_cookie)
    r2 = await client.post("/api/v1/auth/refresh")
    assert r2.status_code == 401


@pytest.mark.xfail(reason="Family revocation implemented in plan 02-02", strict=False)
async def test_reuse_detection_revokes_chain(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Replaying an old token revokes the entire token family (D-07)."""
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert login.status_code == 200
    old_cookie = client.cookies.get("refresh_token")

    # Rotate once legitimately
    await client.post("/api/v1/auth/refresh")
    new_cookie = client.cookies.get("refresh_token")

    # Replay the old token → triggers chain revocation
    client.cookies.set("refresh_token", old_cookie)
    await client.post("/api/v1/auth/refresh")

    # The legitimately rotated token should also be revoked
    client.cookies.set("refresh_token", new_cookie)
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401
