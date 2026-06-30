"""
PLUM AVL (Approved Vendor List) tests — Phase 6.

Behaviors tested (PLUM-07):
  - Add an AVL link from a part to a SYERP vendor; response 201 with correct fields
  - Attempting to link a non-vendor partner returns 422 (D-13 vendor-only guard)

Tests require a live PostgreSQL database (skip_if_no_db).

These are Wave 0 stubs: the AVL service+router do not exist yet (06-02 implements
them). Tests will FAIL/ERROR until Plan 06-02 greens them. They are written as
real behavior assertions encoding PLUM-07 requirements — importable and collectable
by pytest so the test map is in place for 06-02 to drive.

Pattern mirrors backend/tests/plum/test_parts.py exactly.
"""
import pytest
import httpx


# ---------------------------------------------------------------------------
# POST /api/v1/plum/parts/{id}/avl — add AVL link (PLUM-07)
# ---------------------------------------------------------------------------


async def test_add_avl_link(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Adding an AVL link from a part to a SYERP vendor returns 201 with
    correct fields: id, part_id, vendor_id, preferred (PLUM-07, D-11/D-13).
    Requires a vendor in syerp_partner (is_vendor=True) to exist.
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "syerp:write"]
    )

    # Create a SYERP vendor
    vendor_resp = await client.post(
        "/api/v1/syerp/partners",
        json={
            "name": "AVL Test Vendor Co",
            "is_vendor": True,
            "is_customer": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert vendor_resp.status_code == 201, f"Vendor create failed: {vendor_resp.text}"
    vendor_id = vendor_resp.json()["id"]

    # Create a PLUM part
    part_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "AVL link test part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert part_resp.status_code == 201
    part_id = part_resp.json()["id"]

    # Link the part to the vendor
    avl_resp = await client.post(
        f"/api/v1/plum/parts/{part_id}/avl",
        json={"vendor_id": vendor_id, "preferred": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert avl_resp.status_code == 201, (
        f"Expected 201 for AVL link create, got {avl_resp.status_code}: {avl_resp.text}"
    )
    body = avl_resp.json()
    assert "id" in body
    assert body["part_id"] == part_id
    assert body["vendor_id"] == vendor_id
    assert body["preferred"] is True


# ---------------------------------------------------------------------------
# Non-vendor partner rejection (PLUM-07/D-13)
# ---------------------------------------------------------------------------


async def test_avl_link_non_vendor(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Attempting to link a part to a SYERP partner that is NOT a vendor
    (is_vendor=False) returns 422 — only vendors may appear in AVL (D-13).
    This enforces the SYERP-as-hub vendor validation at the PLUM service layer.
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "syerp:write"]
    )

    # Create a customer-only partner (not a vendor)
    customer_resp = await client.post(
        "/api/v1/syerp/partners",
        json={
            "name": "Customer Only Corp",
            "is_vendor": False,
            "is_customer": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert customer_resp.status_code == 201
    customer_id = customer_resp.json()["id"]

    # Create a PLUM part
    part_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Non-vendor AVL test part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    part_id = part_resp.json()["id"]

    # Attempt to link the customer as a vendor — must be rejected
    avl_resp = await client.post(
        f"/api/v1/plum/parts/{part_id}/avl",
        json={"vendor_id": customer_id, "preferred": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert avl_resp.status_code == 422, (
        f"Expected 422 for non-vendor AVL link, got {avl_resp.status_code}"
    )
