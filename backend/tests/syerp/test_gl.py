"""
SYERP GL account tests — Phase 4.

Behaviors tested (SYERP-05):
  - GL accounts endpoint returns seeded data (>= 40 accounts, all 5 types)
  - GL seed is idempotent (re-running seed does not duplicate accounts)
  - GL browse requires syerp:read permission

Tests require a live PostgreSQL database (skip_if_no_db).
These are Wave 0 stubs: the API route GET /api/v1/syerp/gl/accounts does not
exist yet. Tests will fail/skip until Plan 02 (SYERP Partner API) implements
the route — they are written as real behavior assertions to be greened by
Plan 02.
"""
import httpx

# ---------------------------------------------------------------------------
# GET /api/v1/syerp/gl/accounts — read-only CoA browse (SYERP-05)
# ---------------------------------------------------------------------------


async def test_gl_accounts_seeded(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    GET /api/v1/syerp/gl/accounts returns >= 40 accounts covering all 5 GAAP
    account types: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE.
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="syerp-reader", permissions=["syerp:read"])

    response = await client.get(
        "/api/v1/syerp/gl/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    accounts = response.json()
    assert isinstance(accounts, list)
    assert len(accounts) >= 40, (
        f"Expected >= 40 seeded GL accounts, got {len(accounts)}"
    )

    # All 5 GAAP types must be present
    types_present = {a["account_type"] for a in accounts}
    expected_types = {"ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"}
    assert types_present == expected_types, (
        f"Expected account types {expected_types}, got {types_present}"
    )

    # Each account must have the required fields
    for account in accounts:
        assert "id" in account
        assert "code" in account
        assert "name" in account
        assert "account_type" in account


async def test_gl_seed_idempotent(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Running seed_gl_accounts() twice does not duplicate GL account rows.

    T-04-02: select-before-insert idempotency — re-running seed on every
    podman-compose up must leave the CoA count unchanged.
    """
    from sqlalchemy import func, select

    from app.core.db import AsyncSessionLocal
    from app.modules.syerp.coa_seed import seed_gl_accounts
    from app.modules.syerp.models import GLAccount

    async with AsyncSessionLocal() as session:
        # Count before second seed run
        result_before = await session.execute(select(func.count()).select_from(GLAccount))
        count_before = result_before.scalar()

    # Run seed again (should be a no-op — all accounts already exist)
    async with AsyncSessionLocal() as session:
        await seed_gl_accounts(session)

    async with AsyncSessionLocal() as session:
        # Count after second seed run must be identical
        result_after = await session.execute(select(func.count()).select_from(GLAccount))
        count_after = result_after.scalar()

    assert count_after == count_before, (
        f"GL account count changed after re-running seed: "
        f"{count_before} → {count_after}. Seed is not idempotent!"
    )


async def test_gl_requires_syerp_read(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    GET /api/v1/syerp/gl/accounts is gated by syerp:read permission.
      - No token → 401 Unauthorized
      - Token without syerp:read → 403 Forbidden
      - Token with syerp:read → 200 OK
    """
    from app.modules.auth.service import create_access_token

    # No token → 401
    no_token_resp = await client.get("/api/v1/syerp/gl/accounts")
    assert no_token_resp.status_code == 401, (
        f"Expected 401 with no token, got {no_token_resp.status_code}"
    )

    # Token with unrelated permission only → 403
    wrong_perm_token = create_access_token(
        subject="limited-user", permissions=["plum:read"]
    )
    forbidden_resp = await client.get(
        "/api/v1/syerp/gl/accounts",
        headers={"Authorization": f"Bearer {wrong_perm_token}"},
    )
    assert forbidden_resp.status_code == 403, (
        f"Expected 403 without syerp:read, got {forbidden_resp.status_code}"
    )

    # Token with syerp:read → 200
    read_token = create_access_token(subject="syerp-reader", permissions=["syerp:read"])
    ok_resp = await client.get(
        "/api/v1/syerp/gl/accounts",
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert ok_resp.status_code == 200, (
        f"Expected 200 with syerp:read, got {ok_resp.status_code}"
    )
