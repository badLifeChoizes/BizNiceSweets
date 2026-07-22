"""
PLUM part tests — Phase 5.

Behaviors tested (PLUM-01, PLUM-02):
  - Part create → 201, part_number present, active=True, first revision auto-created
    in Draft (PLUM-01)
  - Part create with duplicate part_number → 409 (PLUM-01)
  - Part update → 200, AuditLog row written (PLUM-01)
  - Part archive sets active=False (PLUM-01)
  - Archived part absent from default list (PLUM-01)
  - plum:write required for create → 403 without it (PLUM-01)
  - Search ?q= filters by part_number (PLUM-02)
  - Search ?q= filters by description (PLUM-02)
  - Status filter returns only matching parts (PLUM-02)

Tests require a live PostgreSQL database (skip_if_no_db).

These are Wave 0 tests: the service+router do not exist yet (05-02 implements
them). Tests will FAIL/ERROR until Plan 05-02 greens them. They are written as
real behavior assertions encoding PLUM-01/PLUM-02 requirements — importable and
collectable by pytest so the test map is in place for 05-02 to drive.

Pattern mirrors backend/tests/syerp/test_partners.py exactly.
"""
import httpx

# ---------------------------------------------------------------------------
# POST /api/v1/plum/parts — create part (PLUM-01)
# ---------------------------------------------------------------------------


async def test_create_part(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Admin can create a part; response is 201 with part_number, active=True,
    and the first revision auto-created in Draft status (D-03)."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:write"])

    response = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Widget housing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "part_number" in body
    assert body["active"] is True
    # current_revision_status must be "draft" (D-03 — first revision auto Draft)
    assert body.get("current_revision_status") == "draft"


async def test_create_duplicate_part_number(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Creating two parts with the same part_number → 409 Conflict (D-06)."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:write"])

    # First create with explicit part_number succeeds
    first_resp = await client.post(
        "/api/v1/plum/parts",
        json={"part_number": "P-DUPE-01", "description": "Original part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first_resp.status_code == 201

    # Second create with same part_number must be rejected
    second_resp = await client.post(
        "/api/v1/plum/parts",
        json={"part_number": "P-DUPE-01", "description": "Duplicate attempt"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second_resp.status_code == 409, (
        f"Expected 409 Conflict for duplicate part_number, got {second_resp.status_code}"
    )


async def test_update_part(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """PATCH part → 200; AuditLog row with action='part.updated' is written."""
    from app.modules.auth.service import create_access_token

    write_token = create_access_token(subject="admin-user", permissions=["plum:write"])

    # Create the part first
    create_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Audit target part"},
        headers={"Authorization": f"Bearer {write_token}"},
    )
    assert create_resp.status_code == 201
    part_id = create_resp.json()["id"]

    # Update it (part-level field: part_number)
    update_resp = await client.patch(
        f"/api/v1/plum/parts/{part_id}",
        json={"part_number": "P99901"},
        headers={"Authorization": f"Bearer {write_token}"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["part_number"] == "P99901"

    # Verify AuditLog row was written (mirrors test_update_partner_writes_audit pattern)
    from sqlalchemy import select

    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import AuditLog

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "part.updated",
                AuditLog.target_id == part_id,
            )
        )
        row = result.scalars().first()
    assert row is not None, "Expected AuditLog row for part.updated"


async def test_archive_part(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """PATCH part with active=False archives the part (D-11 soft-delete)."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:write"])

    # Create part
    create_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Part to archive"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 201
    part_id = create_resp.json()["id"]

    # Archive it
    archive_resp = await client.patch(
        f"/api/v1/plum/parts/{part_id}",
        json={"active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert archive_resp.status_code == 200
    assert archive_resp.json()["active"] is False


async def test_archive_part_excluded_from_default_list(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Archived part (active=False) is absent from the default parts list (D-11)."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read"]
    )

    # Create and immediately archive a part
    create_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Hidden part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 201
    part_id = create_resp.json()["id"]

    await client.patch(
        f"/api/v1/plum/parts/{part_id}",
        json={"active": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Default list must not include the archived part
    list_resp = await client.get(
        "/api/v1/plum/parts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    ids = [p["id"] for p in list_resp.json()]
    assert part_id not in ids, "Archived part should be excluded from default list"


async def test_create_requires_write_permission(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Token for a real user lacking plum:write → 403 on part create (D-10).

    Shipped RBAC authorizes from the subject's DB roles, ignoring the JWT
    `perms` claim, so this mints a token for a genuinely limited user — NOT
    the wildcard admin, who would be granted regardless of the claim. A user
    provisioned with no roles lacks plum:write, so the gate returns a real 403.
    """
    from app.modules.auth.service import create_access_token
    from tests.auth.conftest_helpers import admin_login_token, create_regular_user

    admin_token = await admin_login_token(client)
    user = await create_regular_user(
        client, admin_token, "limited@test.example", "pass123"
    )
    # Even a token carrying plum:read is denied — the claim is ignored and the
    # user has no roles granting plum:write.
    read_only_token = create_access_token(
        subject=user["id"], permissions=["plum:read"]
    )

    response = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Forbidden part"},
        headers={"Authorization": f"Bearer {read_only_token}"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/v1/plum/parts — search / filter (PLUM-02)
# ---------------------------------------------------------------------------


async def test_search_by_part_number(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """?q= filters by part_number (case-insensitive ilike, D-15/PLUM-02)."""
    from app.modules.auth.service import create_access_token

    write_token = create_access_token(subject="admin-user", permissions=["plum:write"])
    read_token = create_access_token(subject="admin-user", permissions=["plum:read"])

    # Create a part with a unique explicit part_number for this test
    await client.post(
        "/api/v1/plum/parts",
        json={"part_number": "SRCHPN001", "description": "Search by PN test"},
        headers={"Authorization": f"Bearer {write_token}"},
    )

    resp = await client.get(
        "/api/v1/plum/parts?q=SRCHPN001",
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert resp.status_code == 200
    parts = resp.json()
    part_numbers = [p["part_number"] for p in parts]
    assert "SRCHPN001" in part_numbers, (
        f"Expected SRCHPN001 in search results, got: {part_numbers}"
    )


async def test_search_by_description(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """?q= filters by description on the current revision (D-15/PLUM-02)."""
    from app.modules.auth.service import create_access_token

    write_token = create_access_token(subject="admin-user", permissions=["plum:write"])
    read_token = create_access_token(subject="admin-user", permissions=["plum:read"])

    # Create a part with a unique description
    create_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "UniqueDescriptionSearchTarget9999"},
        headers={"Authorization": f"Bearer {write_token}"},
    )
    assert create_resp.status_code == 201
    created_id = create_resp.json()["id"]

    resp = await client.get(
        "/api/v1/plum/parts?q=UniqueDescriptionSearchTarget9999",
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert resp.status_code == 200
    parts = resp.json()
    ids = [p["id"] for p in parts]
    assert created_id in ids, (
        f"Expected part with unique description in search results, got IDs: {ids}"
    )


async def test_filter_by_status(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """?status=draft returns only parts whose current revision is in draft (D-15/PLUM-02)."""
    from app.modules.auth.service import create_access_token

    write_token = create_access_token(subject="admin-user", permissions=["plum:write"])
    read_token = create_access_token(subject="admin-user", permissions=["plum:read"])

    # Create a part (its first revision will be Draft by D-03)
    create_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Status filter test part"},
        headers={"Authorization": f"Bearer {write_token}"},
    )
    assert create_resp.status_code == 201
    created_id = create_resp.json()["id"]

    # Filter by status=draft — our new part should appear
    resp = await client.get(
        "/api/v1/plum/parts?status=draft",
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert resp.status_code == 200
    parts = resp.json()
    # All returned parts must have current revision in draft
    for p in parts:
        assert p.get("current_revision_status") == "draft", (
            f"Non-draft part in draft filter: {p}"
        )
    ids = [p["id"] for p in parts]
    assert created_id in ids, "Newly-created Draft part missing from ?status=draft results"


# ---------------------------------------------------------------------------
# Auto part-number numeric safety across a digit-width boundary (PLUM-01 defect)
# ---------------------------------------------------------------------------


async def test_generate_part_number_digit_boundary(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Auto-numbering returns the true numeric successor past the 5->6 digit
    boundary, never a lexicographic one.

    Regression for the PLUM-01 defect: the old generate_part_number() used
    lexicographic MAX(part_number), so once a "P100000" row existed it would
    hand out "P100000" again (str "P99999" < "P100000" but the +1 logic keyed
    off the wrong max), colliding on the unique constraint. The fix filters
    ^P[0-9]+$ and orders by CAST(substring AS INTEGER).

    Shared-DB caveat: this runs against the persistent dev database, which may
    already hold rows past this boundary, so the assertions are relative (true
    numeric MAX + 1 / uniqueness), never a hardcoded "P100001".
    """
    from sqlalchemy import Integer, cast, func, select

    from app.core.db import AsyncSessionLocal
    from app.modules.auth.service import create_access_token
    from app.modules.plum.models import PlumPart

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read"]
    )

    # Seed the boundary rows explicitly (idempotent: already-present -> 409).
    for pn in ("P99999", "P100000"):
        seed = await client.post(
            "/api/v1/plum/parts",
            json={"part_number": pn, "description": f"boundary seed {pn}"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert seed.status_code in (201, 409), (
            f"seeding {pn} returned {seed.status_code}"
        )

    # Capture the true numeric MAX suffix BEFORE auto-numbering.
    async with AsyncSessionLocal() as session:
        pre_max = (
            await session.execute(
                select(
                    func.max(cast(func.substring(PlumPart.part_number, 2), Integer))
                ).where(PlumPart.part_number.op("~")(r"^P[0-9]+$"))
            )
        ).scalar()
    assert pre_max is not None and pre_max >= 100000, (
        f"expected boundary seed to place max >= 100000, got {pre_max}"
    )

    # Create a part with NO part_number -> service auto-generates one.
    resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "auto-numbered boundary part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"auto-number create failed: {resp.status_code}"
    new_pn = resp.json()["part_number"]

    # It must be a strictly-numeric P-series value...
    import re

    assert re.fullmatch(r"P[0-9]+", new_pn), f"non-numeric auto part_number: {new_pn}"
    new_suffix = int(new_pn[1:])
    # ...equal to the true numeric MAX + 1 (numeric successor, not lexicographic)...
    assert new_suffix == pre_max + 1, (
        f"expected numeric successor {pre_max + 1}, got {new_suffix}"
    )
    # ...and unique (no collision on the unique constraint).
    async with AsyncSessionLocal() as session:
        count = (
            await session.execute(
                select(func.count())
                .select_from(PlumPart)
                .where(PlumPart.part_number == new_pn)
            )
        ).scalar()
    assert count == 1, f"auto part_number {new_pn} is not unique (count={count})"
