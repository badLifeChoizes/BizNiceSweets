"""
CORE-06 integration tests — settings table + seed + endpoint.

These tests target the 03-02 API endpoints (GET/PATCH /api/v1/core/settings)
and the seed function (seed_default_settings). They are in WAVE 0 RED state
for the endpoint tests until plan 03-02 ships the settings router.
test_seed_defaults can run any time a live DB is available.

Test contract:
  - After seeded_core_db, Setting row key='company.name' owner_id=None exists
    with value='BizNiceSweets' (D-11 seed)
  - GET /api/v1/core/settings (admin) → 200, list includes company.name
  - PATCH /api/v1/core/settings/company.name {value:'Acme'} (admin) → 200,
    DB read-back shows value 'Acme'; restored to 'BizNiceSweets' at test end

Tests require a live PostgreSQL database (skip_if_no_db) and the seeded settings rows.
"""
import httpx

from tests.auth.conftest_helpers import admin_login_token

# ---------------------------------------------------------------------------
# Seed validation — verifies seed_default_settings output directly
# ---------------------------------------------------------------------------


async def test_seed_defaults(
    seeded_core_db,
) -> None:
    """After seeded_core_db, the settings table contains a global row for
    company.name='BizNiceSweets' with owner_id=None (D-11 seed)."""
    from sqlalchemy import select

    from app.core.settings_model import Setting

    result = await seeded_core_db.execute(
        select(Setting).where(
            Setting.key == "company.name",
            Setting.owner_id.is_(None),
        )
    )
    setting = result.scalars().first()
    assert setting is not None, "company.name global setting not found after seed"
    assert setting.value == "BizNiceSweets", (
        f"Expected value='BizNiceSweets', got '{setting.value}'"
    )
    assert setting.owner_id is None, "Global setting must have owner_id=None"
    assert setting.scope == "global", "Global setting must have scope='global'"


# ---------------------------------------------------------------------------
# GET /core/settings — list settings
# ---------------------------------------------------------------------------


async def test_list_settings_admin(
    client: httpx.AsyncClient,
    seeded_core_db,
) -> None:
    """GET /api/v1/core/settings with admin token returns 200 and a list that
    includes the company.name setting (CORE-06 admin configures company info)."""
    token = await admin_login_token(client)

    response = await client.get(
        "/api/v1/core/settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"GET settings failed: {response.text}"
    body = response.json()
    assert isinstance(body, list), f"Expected list, got {type(body)}"
    keys = [s["key"] for s in body]
    assert "company.name" in keys, (
        f"company.name not found in settings list. Keys present: {keys}"
    )


# ---------------------------------------------------------------------------
# PATCH /core/settings/{key} — update a setting value
# ---------------------------------------------------------------------------


async def test_update_setting(
    client: httpx.AsyncClient,
    seeded_core_db,
) -> None:
    """Admin PATCH /api/v1/core/settings/company.name {value:'Acme'} returns 200 and
    the DB shows value='Acme'. Restores to 'BizNiceSweets' at test end."""
    from sqlalchemy import select

    from app.core.settings_model import Setting

    token = await admin_login_token(client)

    # Update company.name to Acme
    response = await client.patch(
        "/api/v1/core/settings/company.name",
        json={"value": "Acme"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"PATCH company.name failed: {response.text}"
    body = response.json()
    assert body["key"] == "company.name"
    assert body["value"] == "Acme"

    # DB read-back
    result = await seeded_core_db.execute(
        select(Setting).where(
            Setting.key == "company.name",
            Setting.owner_id.is_(None),
        )
    )
    setting = result.scalars().first()
    assert setting is not None
    assert setting.value == "Acme", f"DB should show value='Acme', got '{setting.value}'"

    # Restore — keep test suite idempotent against the shared test DB
    response = await client.patch(
        "/api/v1/core/settings/company.name",
        json={"value": "BizNiceSweets"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"PATCH company.name restore failed: {response.text}"
