"""
First-admin seed tests — Wave 0 stub (plan 02-01).

Behaviors tested in plan 02-03 when seed_admin_user is implemented:
  CORE-04 / D-02: Seed creates admin user on first startup
  CORE-04 / D-02: Seed is idempotent — repeated runs do not duplicate the admin
  CORE-04 / D-09: Admin can log in with BNS_ADMIN_EMAIL / BNS_ADMIN_PASSWORD

These tests are intentionally xfail until plan 02-03 implements seed_admin_user.
"""
import pytest
import httpx


@pytest.mark.xfail(reason="seed_admin_user implemented in plan 02-03", strict=False)
async def test_seed_admin_login(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Admin can log in using seeded credentials from environment."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.xfail(reason="seed_admin_user implemented in plan 02-03", strict=False)
async def test_seed_is_idempotent(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Running run_seeds() twice does not create a duplicate admin user."""
    from app.core.db import AsyncSessionLocal
    from app.core.seed import run_seeds

    async with AsyncSessionLocal() as db:
        await run_seeds(db)
        await run_seeds(db)  # second call must not raise or duplicate

    # Admin login still works (not duplicated)
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    assert response.status_code == 200


@pytest.mark.xfail(reason="seed_admin_user implemented in plan 02-03", strict=False)
async def test_seed_creates_admin_role(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """Seeded admin user has the 'admin' role."""
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "testadminpass"},
    )
    access_token = login.json()["access_token"]

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me.status_code == 200
    body = me.json()
    role_names = [r["name"] for r in body.get("roles", [])]
    assert "admin" in role_names
