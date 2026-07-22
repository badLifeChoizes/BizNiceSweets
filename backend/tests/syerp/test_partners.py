"""
SYERP partner tests — Phase 4.

Behaviors tested (SYERP-01..04):
  - Partner create → 201, fields correct (SYERP-01)
  - Partner create without role flags → 422 validation error (SYERP-01)
  - Partner update → 200, audit log written (SYERP-01)
  - Partner archive sets active=false (SYERP-01)
  - Archived partner absent from default list (SYERP-01)
  - syerp:write required for create → 403 without it (SYERP-01)
  - Duplicate code → 409 or 422 (SYERP-01)
  - Search ?q= filters by name (SYERP-02)
  - Search ?q= filters by code (SYERP-02)
  - ?role=vendor returns only is_vendor=true partners (SYERP-02)
  - Customer create → 201 with is_customer=true (SYERP-03)
  - ?role=customer returns only is_customer=true partners (SYERP-04)
  - Dual-role partner appears in both vendor and customer lists (SYERP-04)

Tests require a live PostgreSQL database (skip_if_no_db) and the seeded admin user.
These are Wave 0 stubs: the API routes do not exist yet. Tests will fail/skip until
Plan 02 (SYERP Partner API) implements the routes — they are written as real
behavior assertions to be greened by Plan 02.
"""
import httpx

# ---------------------------------------------------------------------------
# POST /api/v1/syerp/partners — create partner
# ---------------------------------------------------------------------------


async def test_create_vendor(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Admin can create a vendor partner; response is 201 with correct fields."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["syerp:write"])

    response = await client.post(
        "/api/v1/syerp/partners",
        json={
            "name": "Acme Supplies",
            "is_vendor": True,
            "is_customer": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme Supplies"
    assert body["is_vendor"] is True
    assert body["is_customer"] is False
    assert "id" in body
    assert "code" in body
    assert body["active"] is True


async def test_create_requires_role(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Creating a partner with both is_vendor=false and is_customer=false → 422."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["syerp:write"])

    response = await client.post(
        "/api/v1/syerp/partners",
        json={
            "name": "Orphan Corp",
            "is_vendor": False,
            "is_customer": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    # Pydantic model_validator enforces at least one role flag is True
    assert response.status_code == 422


async def test_update_partner_writes_audit(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """PATCH partner → 200; AuditLog row with action='partner.updated' is written."""
    from app.modules.auth.service import create_access_token

    write_token = create_access_token(subject="admin-user", permissions=["syerp:write"])

    # Create the partner first
    create_resp = await client.post(
        "/api/v1/syerp/partners",
        json={"name": "Audit Target Inc", "is_vendor": True},
        headers={"Authorization": f"Bearer {write_token}"},
    )
    assert create_resp.status_code == 201
    partner_id = create_resp.json()["id"]

    # Update it
    update_resp = await client.patch(
        f"/api/v1/syerp/partners/{partner_id}",
        json={"contact_name": "Jane Doe"},
        headers={"Authorization": f"Bearer {write_token}"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["contact_name"] == "Jane Doe"

    # Verify AuditLog row was written
    from sqlalchemy import select

    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import AuditLog

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "partner.updated",
                AuditLog.target_id == partner_id,
            )
        )
        row = result.scalars().first()
    assert row is not None, "Expected AuditLog row for partner.updated"


async def test_archive_partner(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """PATCH partner with active=False sets active=false (archive action)."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["syerp:write"])

    # Create partner
    create_resp = await client.post(
        "/api/v1/syerp/partners",
        json={"name": "To Archive LLC", "is_vendor": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 201
    partner_id = create_resp.json()["id"]

    # Archive it
    archive_resp = await client.patch(
        f"/api/v1/syerp/partners/{partner_id}",
        json={"active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert archive_resp.status_code == 200
    assert archive_resp.json()["active"] is False


async def test_archived_excluded_by_default(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Archived partner (active=False) is absent from the default list response."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["syerp:write", "syerp:read"])

    # Create and immediately archive a vendor
    create_resp = await client.post(
        "/api/v1/syerp/partners",
        json={"name": "Hidden Vendor Co", "is_vendor": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 201
    partner_id = create_resp.json()["id"]

    await client.patch(
        f"/api/v1/syerp/partners/{partner_id}",
        json={"active": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Default list must not include the archived partner
    list_resp = await client.get(
        "/api/v1/syerp/partners",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    ids = [p["id"] for p in list_resp.json()]
    assert partner_id not in ids, "Archived partner should be excluded from default list"


async def test_create_requires_syerp_write(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Token with only syerp:read (no syerp:write) → 403 on partner create."""
    from app.modules.auth.service import create_access_token

    # The roster's syerp-reader holds ONLY syerp:read (lacks syerp:write), so a
    # token minted for it hits a genuine 403 on the write-gated create endpoint.
    # Shipped RBAC authorizes from the DB user's roles, not the JWT perms claim.
    read_only_token = create_access_token(
        subject="syerp-reader", permissions=["syerp:read"]
    )

    response = await client.post(
        "/api/v1/syerp/partners",
        json={"name": "Forbidden Corp", "is_vendor": True},
        headers={"Authorization": f"Bearer {read_only_token}"},
    )
    assert response.status_code == 403


async def test_duplicate_code_rejected(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Creating two partners with the same code → 409 Conflict or 422 Unprocessable."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["syerp:write"])

    # First create succeeds
    first_resp = await client.post(
        "/api/v1/syerp/partners",
        json={"name": "Original Corp", "code": "P-DUPE", "is_vendor": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first_resp.status_code == 201

    # Second create with same code must be rejected
    second_resp = await client.post(
        "/api/v1/syerp/partners",
        json={"name": "Duplicate Corp", "code": "P-DUPE", "is_vendor": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second_resp.status_code in (409, 422), (
        f"Expected 409 or 422 for duplicate code, got {second_resp.status_code}"
    )


# ---------------------------------------------------------------------------
# GET /api/v1/syerp/partners — search / filter (SYERP-02)
# ---------------------------------------------------------------------------


async def test_search_by_name(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """?q= search parameter filters partners by name (case-insensitive)."""
    from app.modules.auth.service import create_access_token

    write_token = create_access_token(subject="admin-user", permissions=["syerp:write"])
    read_token = create_access_token(subject="admin-user", permissions=["syerp:read"])

    # Create a partner with a unique name for this test
    await client.post(
        "/api/v1/syerp/partners",
        json={"name": "UniqueNameSearchTarget", "is_vendor": True},
        headers={"Authorization": f"Bearer {write_token}"},
    )

    # Search by a substring of the name
    resp = await client.get(
        "/api/v1/syerp/partners?q=UniqueNameSearch",
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert resp.status_code == 200
    partners = resp.json()
    names = [p["name"] for p in partners]
    assert "UniqueNameSearchTarget" in names, (
        f"Expected UniqueNameSearchTarget in search results, got: {names}"
    )


async def test_search_by_code(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """?q= search parameter filters partners by code."""
    from app.modules.auth.service import create_access_token

    write_token = create_access_token(subject="admin-user", permissions=["syerp:write"])
    read_token = create_access_token(subject="admin-user", permissions=["syerp:read"])

    # Create a partner and capture its auto-generated code
    create_resp = await client.post(
        "/api/v1/syerp/partners",
        json={"name": "CodeSearchVendor", "is_vendor": True},
        headers={"Authorization": f"Bearer {write_token}"},
    )
    assert create_resp.status_code == 201
    partner_code = create_resp.json()["code"]

    # Search by the exact code
    resp = await client.get(
        f"/api/v1/syerp/partners?q={partner_code}",
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert resp.status_code == 200
    partners = resp.json()
    codes = [p["code"] for p in partners]
    assert partner_code in codes, f"Expected {partner_code} in search results"


async def test_vendor_role_filter(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """?role=vendor returns only partners where is_vendor=True."""
    from app.modules.auth.service import create_access_token

    write_token = create_access_token(subject="admin-user", permissions=["syerp:write"])
    read_token = create_access_token(subject="admin-user", permissions=["syerp:read"])

    # Create a customer-only partner (should not appear in vendor list)
    await client.post(
        "/api/v1/syerp/partners",
        json={"name": "Customer Only Corp", "is_customer": True, "is_vendor": False},
        headers={"Authorization": f"Bearer {write_token}"},
    )

    # Create a vendor-only partner (should appear in vendor list)
    vendor_resp = await client.post(
        "/api/v1/syerp/partners",
        json={"name": "Vendor Only Corp", "is_vendor": True, "is_customer": False},
        headers={"Authorization": f"Bearer {write_token}"},
    )
    vendor_id = vendor_resp.json()["id"]

    resp = await client.get(
        "/api/v1/syerp/partners?role=vendor",
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert resp.status_code == 200
    partners = resp.json()
    # All returned partners must have is_vendor=True
    for p in partners:
        assert p["is_vendor"] is True, f"Non-vendor in vendor list: {p}"
    ids = [p["id"] for p in partners]
    assert vendor_id in ids, "Vendor-only partner missing from ?role=vendor results"


# ---------------------------------------------------------------------------
# POST /api/v1/syerp/partners — customer role (SYERP-03)
# ---------------------------------------------------------------------------


async def test_create_customer(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Admin can create a customer partner; response is 201 with is_customer=True."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["syerp:write"])

    response = await client.post(
        "/api/v1/syerp/partners",
        json={
            "name": "Buying Corp",
            "is_vendor": False,
            "is_customer": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Buying Corp"
    assert body["is_customer"] is True
    assert body["is_vendor"] is False
    assert "id" in body


async def test_customer_role_filter(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """?role=customer returns only partners where is_customer=True."""
    from app.modules.auth.service import create_access_token

    write_token = create_access_token(subject="admin-user", permissions=["syerp:write"])
    read_token = create_access_token(subject="admin-user", permissions=["syerp:read"])

    # Create a vendor-only partner (must NOT appear in customer list)
    await client.post(
        "/api/v1/syerp/partners",
        json={"name": "VendorNotCustomer Ltd", "is_vendor": True, "is_customer": False},
        headers={"Authorization": f"Bearer {write_token}"},
    )

    # Create a customer-only partner (must appear in customer list)
    cust_resp = await client.post(
        "/api/v1/syerp/partners",
        json={"name": "CustomerOnly Ltd", "is_customer": True, "is_vendor": False},
        headers={"Authorization": f"Bearer {write_token}"},
    )
    cust_id = cust_resp.json()["id"]

    resp = await client.get(
        "/api/v1/syerp/partners?role=customer",
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert resp.status_code == 200
    partners = resp.json()
    for p in partners:
        assert p["is_customer"] is True, f"Non-customer in customer list: {p}"
    ids = [p["id"] for p in partners]
    assert cust_id in ids, "Customer-only partner missing from ?role=customer results"


async def test_dual_role_appears_in_both(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """A partner with both is_vendor=True and is_customer=True appears in both lists."""
    from app.modules.auth.service import create_access_token

    write_token = create_access_token(subject="admin-user", permissions=["syerp:write"])
    read_token = create_access_token(subject="admin-user", permissions=["syerp:read"])

    # Create a dual-role partner
    dual_resp = await client.post(
        "/api/v1/syerp/partners",
        json={
            "name": "DualRole Partners Inc",
            "is_vendor": True,
            "is_customer": True,
        },
        headers={"Authorization": f"Bearer {write_token}"},
    )
    assert dual_resp.status_code == 201
    dual_id = dual_resp.json()["id"]

    # Confirm it appears in the vendor list
    vendor_resp = await client.get(
        "/api/v1/syerp/partners?role=vendor",
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert vendor_resp.status_code == 200
    vendor_ids = [p["id"] for p in vendor_resp.json()]
    assert dual_id in vendor_ids, "Dual-role partner missing from vendor list"

    # Confirm it appears in the customer list
    customer_resp = await client.get(
        "/api/v1/syerp/partners?role=customer",
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert customer_resp.status_code == 200
    customer_ids = [p["id"] for p in customer_resp.json()]
    assert dual_id in customer_ids, "Dual-role partner missing from customer list"
