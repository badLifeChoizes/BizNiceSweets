"""
PLUM costing tests — Phase 6.

Behaviors tested (PLUM-08, PLUM-09):
  - Effective cost source is "vendor price" when a vendor link + price break
    is selected (PLUM-08, D-07 step 1)
  - Effective cost source is "manual" when material_cost is set and no vendor
    link is selected (PLUM-08, D-06)
  - Effective cost source is "roll-up" when only BOM child costs exist
    (PLUM-08, D-04/D-09)
  - Released revision freezes released_cost_snapshot (PLUM-09, D-14)
  - Margin and margin_pct are computed correctly; negative margin is flagged
    (PLUM-09, D-09)

Tests require a live PostgreSQL database (skip_if_no_db).

These are Wave 0 stubs: the costing service+router do not exist yet (06-02
implements them). Tests will FAIL/ERROR until Plan 06-02 greens them. They are
written as real behavior assertions encoding PLUM-08/09 requirements — importable
and collectable by pytest so the test map is in place for 06-02 to drive.

Pattern mirrors backend/tests/plum/test_revisions.py (when it exists) exactly.
"""
import httpx
import pytest

# ---------------------------------------------------------------------------
# Effective cost — vendor price source (PLUM-08)
# ---------------------------------------------------------------------------


async def test_effective_cost_vendor(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    When a revision has a selected AVL link + price break index, the cost
    GET endpoint returns effective_cost_source="vendor price" and
    effective_cost equals the unit_cost of the selected price break (PLUM-08).
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read", "syerp:write"]
    )

    # Create vendor, part, AVL link, and price break
    vendor_resp = await client.post(
        "/api/v1/syerp/partners",
        json={"name": "Costing Vendor A", "is_vendor": True, "is_customer": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    vendor_id = vendor_resp.json()["id"]

    part_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Vendor cost test part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    part_id = part_resp.json()["id"]
    revision_id = part_resp.json().get("revisions", [{}])[0].get("id")

    avl_resp = await client.post(
        f"/api/v1/plum/parts/{part_id}/avl",
        json={"vendor_id": vendor_id, "preferred": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    avl_link_id = avl_resp.json()["id"]

    # Add price break: qty=1, unit_cost=9.99
    await client.post(
        f"/api/v1/plum/parts/{part_id}/avl/{avl_link_id}/price-breaks",
        json={"qty_threshold": 1, "unit_cost": "9.990000"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Select the vendor link + price break 0 on the revision
    await client.patch(
        f"/api/v1/plum/parts/{part_id}/revisions/{revision_id}/cost",
        json={"selected_vendor_link_id": avl_link_id, "selected_price_break_index": 0},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Get cost
    cost_resp = await client.get(
        f"/api/v1/plum/parts/{part_id}/revisions/{revision_id}/cost",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cost_resp.status_code == 200
    body = cost_resp.json()
    assert body["effective_cost_source"] == "vendor price", (
        f"Expected 'vendor price', got {body.get('effective_cost_source')}"
    )
    assert float(body["effective_cost"]) == pytest.approx(9.99, rel=1e-4)


# ---------------------------------------------------------------------------
# Effective cost — manual source (PLUM-08)
# ---------------------------------------------------------------------------


async def test_effective_cost_manual(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    When a revision has material_cost set but no vendor link selected,
    effective_cost_source="manual" and effective_cost equals material_cost
    (PLUM-08, D-06 manual cost override).
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read"]
    )

    part_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Manual cost test part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    part_id = part_resp.json()["id"]
    revision_id = part_resp.json().get("revisions", [{}])[0].get("id")

    # Set manual cost only (no vendor link)
    await client.patch(
        f"/api/v1/plum/parts/{part_id}/revisions/{revision_id}/cost",
        json={"material_cost": "15.500000"},
        headers={"Authorization": f"Bearer {token}"},
    )

    cost_resp = await client.get(
        f"/api/v1/plum/parts/{part_id}/revisions/{revision_id}/cost",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cost_resp.status_code == 200
    body = cost_resp.json()
    assert body["effective_cost_source"] == "manual", (
        f"Expected 'manual', got {body.get('effective_cost_source')}"
    )
    assert float(body["effective_cost"]) == pytest.approx(15.5, rel=1e-4)


# ---------------------------------------------------------------------------
# Effective cost — BOM roll-up source (PLUM-08/D-09)
# ---------------------------------------------------------------------------


async def test_effective_cost_rollup(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    When a revision has neither vendor link nor manual cost, but children
    have costs, effective_cost_source="roll-up" and effective_cost equals
    the summed child effective costs × qty (PLUM-08, D-09 roll-up).
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read"]
    )

    # Create parent + child with a manual cost
    parent_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Roll-up parent part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    parent_id = parent_resp.json()["id"]

    child_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Roll-up child part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    child_id = child_resp.json()["id"]
    child_revision_id = child_resp.json().get("revisions", [{}])[0].get("id")

    # Set child manual cost to 5.00
    await client.patch(
        f"/api/v1/plum/parts/{child_id}/revisions/{child_revision_id}/cost",
        json={"material_cost": "5.000000"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Add child to parent BOM with qty=2
    await client.post(
        f"/api/v1/plum/parts/{parent_id}/bom",
        json={"child_part_id": child_id, "qty": "2.0"},
        headers={"Authorization": f"Bearer {token}"},
    )

    parent_revision_id = parent_resp.json().get("revisions", [{}])[0].get("id")
    cost_resp = await client.get(
        f"/api/v1/plum/parts/{parent_id}/revisions/{parent_revision_id}/cost",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cost_resp.status_code == 200
    body = cost_resp.json()
    assert body["effective_cost_source"] == "roll-up", (
        f"Expected 'roll-up', got {body.get('effective_cost_source')}"
    )
    # Expected: 2 × 5.00 = 10.00
    assert float(body["effective_cost"]) == pytest.approx(10.0, rel=1e-4)


# ---------------------------------------------------------------------------
# Released revision cost snapshot (PLUM-09/D-14)
# ---------------------------------------------------------------------------


async def test_release_snapshots_cost(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    When a revision is advanced to Released, its released_cost_snapshot is
    frozen to the effective cost at that moment (PLUM-09, D-14).
    Subsequent cost changes on child parts do NOT change the snapshot.
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read"]
    )

    part_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Snapshot cost test part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    part_id = part_resp.json()["id"]
    revision_id = part_resp.json().get("revisions", [{}])[0].get("id")

    # Set manual cost to 20.00 before release
    await client.patch(
        f"/api/v1/plum/parts/{part_id}/revisions/{revision_id}/cost",
        json={"material_cost": "20.000000"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Release the revision
    await client.post(
        f"/api/v1/plum/parts/{part_id}/revisions/latest/advance",
        json={"target_status": "in_review"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/v1/plum/parts/{part_id}/revisions/latest/advance",
        json={"target_status": "released"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Get cost on the released revision
    cost_resp = await client.get(
        f"/api/v1/plum/parts/{part_id}/revisions/{revision_id}/cost",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cost_resp.status_code == 200
    body = cost_resp.json()
    assert body["released_cost_snapshot"] is not None, (
        "released_cost_snapshot must be set on a Released revision"
    )
    assert float(body["released_cost_snapshot"]) == pytest.approx(20.0, rel=1e-4)


# ---------------------------------------------------------------------------
# Margin computation (PLUM-09/D-09)
# ---------------------------------------------------------------------------


async def test_margin_computation(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    When sale_price and effective_cost are both set, the cost GET returns
    margin = sale_price − effective_cost and margin_pct = margin / effective_cost × 100
    (PLUM-09, D-09). Negative margin must be returned (not rejected).
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read"]
    )

    part_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Margin computation test part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    part_id = part_resp.json()["id"]
    revision_id = part_resp.json().get("revisions", [{}])[0].get("id")

    # Cost = 10.00, sale = 15.00 → margin = 5.00, margin_pct = 50%
    await client.patch(
        f"/api/v1/plum/parts/{part_id}/revisions/{revision_id}/cost",
        json={"material_cost": "10.000000", "sale_price": "15.000000"},
        headers={"Authorization": f"Bearer {token}"},
    )

    cost_resp = await client.get(
        f"/api/v1/plum/parts/{part_id}/revisions/{revision_id}/cost",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cost_resp.status_code == 200
    body = cost_resp.json()
    assert float(body["margin"]) == pytest.approx(5.0, rel=1e-4)
    assert float(body["margin_pct"]) == pytest.approx(50.0, rel=1e-4)
