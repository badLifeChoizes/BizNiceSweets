"""
PLUM revision tests — Phase 5.

Behaviors tested (PLUM-03):
  - Create revision → 201, status=draft, attributes copied forward from prior (D-03)
  - Advance Draft → In Review → 200, status updated (D-07)
  - Advance In Review → Released → prior Released revision becomes Obsolete (D-08)
  - Edit Released revision → 422 Unprocessable (D-07 immutability)
  - Revision history visible, ordered newest-first (D-14)

Tests require a live PostgreSQL database (skip_if_no_db).

These are Wave 0 tests: the service+router do not exist yet (05-02 implements
them). Tests will FAIL/ERROR until Plan 05-02 greens them. They encode the
PLUM-03 behaviors with real assertions against /api/v1/plum/... endpoints —
importable and collectable by pytest so the test map is ready for 05-02.

Pattern mirrors backend/tests/syerp/test_partners.py (structure) with
revision FSM assertions that are net-new domain behavior.
"""
import pytest
import httpx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_part(client: httpx.AsyncClient, token: str, description: str = "Test part") -> dict:
    """Helper: POST /api/v1/plum/parts and return the response body."""
    resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": description},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"Part creation failed: {resp.text}"
    return resp.json()


async def _advance_revision(
    client: httpx.AsyncClient,
    token: str,
    part_id: str,
    revision_id: str,
    target_status: str,
) -> dict:
    """Helper: POST /api/v1/plum/parts/{id}/revisions/{rev_id}/advance."""
    resp = await client.post(
        f"/api/v1/plum/parts/{part_id}/revisions/{revision_id}/advance",
        json={"target_status": target_status},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


# ---------------------------------------------------------------------------
# POST /api/v1/plum/parts/{id}/revisions — create revision (PLUM-03)
# ---------------------------------------------------------------------------


async def test_create_revision(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Create a new revision on an existing part → 201, status=draft,
    attributes copied forward from the first revision (D-03)."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read"]
    )

    # Step 1: create a part (gets first revision in Draft automatically)
    part = await _create_part(client, token, "Original description for revision test")
    part_id = part["id"]

    # Step 2: create a second revision (copy-forward from first)
    create_rev_resp = await client.post(
        f"/api/v1/plum/parts/{part_id}/revisions",
        json={"reason_for_revision": "Design change for test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_rev_resp.status_code == 201
    rev_body = create_rev_resp.json()

    # Step 3: new revision must be in Draft (D-07) with attributes copied forward (D-03)
    assert rev_body["status"] == "draft"
    assert rev_body["description"] == "Original description for revision test", (
        "New revision should copy description forward from prior revision (D-03)"
    )


async def test_advance_to_in_review(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Advance a Draft revision to In Review → 200, status updated (D-07)."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read"]
    )

    # Create a part (first revision in Draft)
    part = await _create_part(client, token, "Part for in_review advance test")
    part_id = part["id"]

    # Get the detail to find the current revision ID
    detail_resp = await client.get(
        f"/api/v1/plum/parts/{part_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == 200
    revisions = detail_resp.json().get("revisions", [])
    assert len(revisions) >= 1
    draft_revision_id = revisions[0]["id"]
    assert revisions[0]["status"] == "draft"

    # Advance to in_review
    advance_resp = await _advance_revision(
        client, token, part_id, draft_revision_id, "in_review"
    )
    assert advance_resp.status_code == 200
    assert advance_resp.json()["status"] == "in_review"


async def test_release_supersedes_prior(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Releasing Rev B auto-obsoletes Rev A; exactly one Released per part (D-08).

    Flow:
      1. Create part (Rev A in Draft)
      2. Advance Rev A: draft → in_review → released
      3. Create Rev B (Draft, copy-forward from Rev A)
      4. Advance Rev B: draft → in_review → released
      5. Assert Rev A is status=obsolete
      6. Assert Rev B is status=released
      7. Assert exactly one released row in the part's revision history
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read"]
    )

    # Step 1: create part (Rev A in Draft)
    part = await _create_part(client, token, "Supersede test part")
    part_id = part["id"]

    # Get Rev A's ID
    detail_resp = await client.get(
        f"/api/v1/plum/parts/{part_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == 200
    revisions = detail_resp.json()["revisions"]
    rev_a_id = revisions[0]["id"]

    # Step 2: advance Rev A to released (draft → in_review → released)
    advance_to_review = await _advance_revision(
        client, token, part_id, rev_a_id, "in_review"
    )
    assert advance_to_review.status_code == 200

    advance_to_released = await _advance_revision(
        client, token, part_id, rev_a_id, "released"
    )
    assert advance_to_released.status_code == 200

    # Step 3: create Rev B (Draft, copy-forward from Rev A)
    create_rev_b = await client.post(
        f"/api/v1/plum/parts/{part_id}/revisions",
        json={"reason_for_revision": "Next version"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_rev_b.status_code == 201
    rev_b_id = create_rev_b.json()["id"]

    # Step 4: advance Rev B to released (draft → in_review → released)
    await _advance_revision(client, token, part_id, rev_b_id, "in_review")
    advance_b_released = await _advance_revision(
        client, token, part_id, rev_b_id, "released"
    )
    assert advance_b_released.status_code == 200

    # Step 5+6+7: verify the supersede invariant
    final_detail = await client.get(
        f"/api/v1/plum/parts/{part_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert final_detail.status_code == 200
    final_revisions = final_detail.json()["revisions"]

    rev_a_final = next(r for r in final_revisions if r["id"] == rev_a_id)
    rev_b_final = next(r for r in final_revisions if r["id"] == rev_b_id)

    # Rev A must be obsolete now (superseded by Rev B)
    assert rev_a_final["status"] == "obsolete", (
        f"Rev A should be obsolete after Rev B released, got: {rev_a_final['status']}"
    )
    # Rev B must be released
    assert rev_b_final["status"] == "released", (
        f"Rev B should be released, got: {rev_b_final['status']}"
    )
    # Exactly one revision should be released (DB invariant D-08 / T-05-01)
    released_count = sum(1 for r in final_revisions if r["status"] == "released")
    assert released_count == 1, (
        f"Expected exactly 1 released revision, got {released_count}"
    )


async def test_released_revision_immutable(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """PATCH a Released revision's description → 422 Unprocessable (D-07 immutability)."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read"]
    )

    # Create a part and release its first revision
    part = await _create_part(client, token, "Immutability test part")
    part_id = part["id"]

    detail_resp = await client.get(
        f"/api/v1/plum/parts/{part_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == 200
    rev_id = detail_resp.json()["revisions"][0]["id"]

    # Advance to released
    await _advance_revision(client, token, part_id, rev_id, "in_review")
    await _advance_revision(client, token, part_id, rev_id, "released")

    # Attempt to PATCH a revision-controlled field on the Released revision
    patch_resp = await client.patch(
        f"/api/v1/plum/parts/{part_id}",
        json={"description": "Illegal mutation of released revision"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # 422 Unprocessable — Released revisions are immutable (D-07)
    assert patch_resp.status_code == 422, (
        f"Expected 422 for editing a Released revision, got {patch_resp.status_code}"
    )


async def test_revision_history_order(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Revision history in GET /plum/parts/{id} is ordered newest-first (D-14)."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read"]
    )

    # Create a part and add a second revision
    part = await _create_part(client, token, "History order test part")
    part_id = part["id"]

    # Create Rev B
    rev_b_resp = await client.post(
        f"/api/v1/plum/parts/{part_id}/revisions",
        json={"reason_for_revision": "Second revision for ordering test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rev_b_resp.status_code == 201

    # Get the part detail and verify revision order (newest-first = highest revision_number first)
    detail_resp = await client.get(
        f"/api/v1/plum/parts/{part_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == 200
    revisions = detail_resp.json()["revisions"]

    assert len(revisions) >= 2, "Expected at least 2 revisions"

    # Newest-first: revision_number must be descending
    revision_numbers = [r["revision_number"] for r in revisions]
    assert revision_numbers == sorted(revision_numbers, reverse=True), (
        f"Revisions must be ordered newest-first (descending revision_number), "
        f"got: {revision_numbers}"
    )
