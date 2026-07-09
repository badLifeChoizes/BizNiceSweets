"""
PLUM BOM tests — Phase 6.

Behaviors tested (PLUM-04, PLUM-05, PLUM-06):
  - Add a BOM line to a Draft revision; response 201 with correct fields (PLUM-04)
  - BOM line on a Released revision returns 422 — BOM is immutable (PLUM-04/D-07)
  - Adding a part as its own ancestor raises 422 — cycle detection (PLUM-05)
  - Flat BOM rolls up shared part quantity across paths (PLUM-04/D-04)
  - Where-used includes indirect (transitive) references (PLUM-06)

Tests require a live PostgreSQL database (skip_if_no_db).

These are Wave 0 stubs: the BOM service+router do not exist yet (06-02 implements
them). Tests will FAIL/ERROR until Plan 06-02 greens them. They are written as
real behavior assertions encoding PLUM-04/05/06 requirements — importable and
collectable by pytest so the test map is in place for 06-02 to drive.

Pattern mirrors backend/tests/plum/test_parts.py exactly.
"""
import pytest
import httpx


# ---------------------------------------------------------------------------
# POST /api/v1/plum/parts/{id}/bom — add BOM line (PLUM-04)
# ---------------------------------------------------------------------------


async def test_add_bom_line(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Adding a child part to a Draft revision's BOM returns 201 with correct
    fields: id, parent_revision_id, child_part_id, qty, sort_order (PLUM-04).
    Requires the BOM service add_bom_line and router POST /parts/{id}/bom.
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:write"])

    # Create parent part
    parent_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Parent assembly"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert parent_resp.status_code == 201
    parent = parent_resp.json()
    parent_id = parent["id"]
    revision_id = parent["revisions"][0]["id"] if "revisions" in parent else None

    # Create child part
    child_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Child component"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert child_resp.status_code == 201
    child_id = child_resp.json()["id"]

    # Add child to parent BOM
    bom_resp = await client.post(
        f"/api/v1/plum/parts/{parent_id}/bom",
        json={"child_part_id": child_id, "qty": "2.000000", "revision_id": revision_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bom_resp.status_code == 201, f"Expected 201, got {bom_resp.status_code}: {bom_resp.text}"
    body = bom_resp.json()
    assert "id" in body
    assert body["child_part_id"] == child_id


# ---------------------------------------------------------------------------
# BOM immutability on Released revision (PLUM-04/D-07)
# ---------------------------------------------------------------------------


async def test_bom_line_released_immutable(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Attempting to add a BOM line to a Released revision returns 422 —
    Released revisions are immutable (D-07 BOM immutability invariant).
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:write"])

    # Create and release a part
    part_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Immutable BOM test part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert part_resp.status_code == 201
    part = part_resp.json()
    part_id = part["id"]

    # Advance to released (via in_review first if FSM requires)
    await client.post(
        f"/api/v1/plum/parts/{part_id}/revisions/latest/advance",
        json={"target_status": "in_review"},
        headers={"Authorization": f"Bearer {token}"},
    )
    advance_resp = await client.post(
        f"/api/v1/plum/parts/{part_id}/revisions/latest/advance",
        json={"target_status": "released"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert advance_resp.status_code == 200

    # Create child part
    child_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Child for immutable BOM test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    child_id = child_resp.json()["id"]

    # Attempt BOM add on released revision → must fail
    bom_resp = await client.post(
        f"/api/v1/plum/parts/{part_id}/bom",
        json={"child_part_id": child_id, "qty": "1.0"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bom_resp.status_code == 422, (
        f"Expected 422 for BOM mutation on Released revision, got {bom_resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Cycle detection (PLUM-05)
# ---------------------------------------------------------------------------


async def test_bom_cycle_detection(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Adding a part as a BOM child of one of its own descendants returns 422
    — BOM cycle detection (PLUM-05). A → B → A would be a cycle.
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:write"])

    # Create part A and part B
    a_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Cycle test part A"},
        headers={"Authorization": f"Bearer {token}"},
    )
    a_id = a_resp.json()["id"]

    b_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Cycle test part B"},
        headers={"Authorization": f"Bearer {token}"},
    )
    b_id = b_resp.json()["id"]

    # A contains B (valid)
    await client.post(
        f"/api/v1/plum/parts/{a_id}/bom",
        json={"child_part_id": b_id, "qty": "1.0"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # B contains A — creates cycle A → B → A (must be rejected)
    cycle_resp = await client.post(
        f"/api/v1/plum/parts/{b_id}/bom",
        json={"child_part_id": a_id, "qty": "1.0"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cycle_resp.status_code == 422, (
        f"Expected 422 for cyclic BOM reference, got {cycle_resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Flat BOM shared-part roll-up (PLUM-04/D-04)
# ---------------------------------------------------------------------------


async def test_flat_bom_shared_part(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Flat BOM rolls up the total quantity of a shared part across all paths
    (D-04 quantity roll-up). If resistor R appears in two sub-assemblies
    with qty 3 and qty 5 respectively, the flat BOM shows total_qty=8.
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:write", "plum:read"])

    # Create top assembly, two sub-assemblies, and one shared component
    top_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Top assembly (flat BOM roll-up test)"},
        headers={"Authorization": f"Bearer {token}"},
    )
    top_id = top_resp.json()["id"]

    sub1_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Sub-assembly 1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    sub1_id = sub1_resp.json()["id"]

    sub2_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Sub-assembly 2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    sub2_id = sub2_resp.json()["id"]

    shared_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Shared resistor component"},
        headers={"Authorization": f"Bearer {token}"},
    )
    shared_id = shared_resp.json()["id"]

    # Wire: Top → Sub1 (×1), Top → Sub2 (×1), Sub1 → Shared (×3), Sub2 → Shared (×5)
    await client.post(
        f"/api/v1/plum/parts/{top_id}/bom",
        json={"child_part_id": sub1_id, "qty": "1.0"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/v1/plum/parts/{top_id}/bom",
        json={"child_part_id": sub2_id, "qty": "1.0"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/v1/plum/parts/{sub1_id}/bom",
        json={"child_part_id": shared_id, "qty": "3.0"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/v1/plum/parts/{sub2_id}/bom",
        json={"child_part_id": shared_id, "qty": "5.0"},
        headers={"Authorization": f"Bearer {token}"},
    )

    flat_resp = await client.get(
        f"/api/v1/plum/parts/{top_id}/bom/flat",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert flat_resp.status_code == 200
    rows = flat_resp.json()
    shared_rows = [r for r in rows if r["part_id"] == shared_id]
    assert len(shared_rows) == 1, "Shared part should appear once in flat BOM"
    assert float(shared_rows[0]["total_qty"]) == 8.0, (
        f"Expected total_qty=8.0 for shared part, got {shared_rows[0]['total_qty']}"
    )


# ---------------------------------------------------------------------------
# Where-used indirect traversal (PLUM-06)
# ---------------------------------------------------------------------------


async def test_where_used_indirect(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    Where-used query returns both direct parents and indirect (transitive)
    ancestors (PLUM-06). If C is in B and B is in A, where-used(C) includes
    A with indirect=True.
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:write", "plum:read"])

    # Create three parts: A → B → C
    a_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Where-used test A (indirect parent)"},
        headers={"Authorization": f"Bearer {token}"},
    )
    a_id = a_resp.json()["id"]

    b_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Where-used test B (direct parent)"},
        headers={"Authorization": f"Bearer {token}"},
    )
    b_id = b_resp.json()["id"]

    c_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Where-used test C (target part)"},
        headers={"Authorization": f"Bearer {token}"},
    )
    c_id = c_resp.json()["id"]

    # Wire A → B → C
    await client.post(
        f"/api/v1/plum/parts/{a_id}/bom",
        json={"child_part_id": b_id, "qty": "1.0"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/v1/plum/parts/{b_id}/bom",
        json={"child_part_id": c_id, "qty": "1.0"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Where-used of C should include B (direct) and A (indirect)
    wu_resp = await client.get(
        f"/api/v1/plum/parts/{c_id}/where-used",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert wu_resp.status_code == 200
    rows = wu_resp.json()
    parent_ids = {r["parent_part_id"] for r in rows}
    assert b_id in parent_ids, "Direct parent B missing from where-used"
    assert a_id in parent_ids, "Indirect ancestor A missing from where-used"

    # A should be marked indirect
    a_row = next(r for r in rows if r["parent_part_id"] == a_id)
    assert a_row.get("indirect") is True, "A should be marked indirect=True"

    # A is reached through B — the UI renders "Indirect via {via_part_number}",
    # so an indirect row without this field silently degrades to "Direct parent"
    # (milestone-audit defect G1).
    b_part_number = b_resp.json()["part_number"]
    assert a_row.get("via_part_number") == b_part_number, (
        "Indirect ancestor A must name B as the part it is reached through"
    )

    # B is a direct parent: no intermediate part.
    b_row = next(r for r in rows if r["parent_part_id"] == b_id)
    assert b_row.get("direct") is True, "B should be marked direct=True"
    assert b_row.get("via_part_number") is None, "Direct parent B has no via part"
