"""
PLUM import/export tests — Phase 6.

Behaviors tested (PLUM-10):
  - Export JSON: GET /plum/export/json returns a valid JSON body with all parts
    and revisions (PLUM-10, D-16)
  - Export Excel: GET /plum/export/excel returns an .xlsx file with at minimum
    a Parts sheet and a BOM sheet (PLUM-10, D-16)
  - Import preview with valid data: POST /plum/import/validate returns
    new_count>0, updated_count>=0, errors=[] (PLUM-10, D-18 three-step flow)
  - Import preview with unknown vendor: POST /plum/import/validate returns
    an ImportRowError with field="vendor_id" (PLUM-10, D-18 validation)
  - Import commit no-delete: POST /plum/import/commit inserts and updates rows
    but never deletes existing parts or revisions (PLUM-10, D-18 no-delete contract)

Tests require a live PostgreSQL database (skip_if_no_db).

These are Wave 0 stubs: the import/export service+router do not exist yet (06-03
implements them). Tests will FAIL/ERROR until Plan 06-03 greens them. They are
written as real behavior assertions encoding PLUM-10 requirements — importable and
collectable by pytest so the test map is in place for 06-03 to drive.

Pattern mirrors backend/tests/plum/test_parts.py exactly.
"""
import io
import json

import httpx

# ---------------------------------------------------------------------------
# GET /api/v1/plum/export/json — JSON export (PLUM-10)
# ---------------------------------------------------------------------------


async def test_export_json(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    GET /plum/export/json returns a valid JSON payload with schema_version,
    parts list, and revisions list (PLUM-10, D-16). An audit event
    'plum.exported' is written.
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:read"])

    resp = await client.get(
        "/api/v1/plum/export/json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    # Response must be valid JSON with at least schema_version and parts
    content_type = resp.headers.get("content-type", "")
    assert "application/json" in content_type or "application/octet-stream" in content_type, (
        f"Unexpected content-type: {content_type}"
    )
    body = resp.json()
    assert "schema_version" in body, "Export JSON missing schema_version"
    assert "parts" in body, "Export JSON missing parts list"


# ---------------------------------------------------------------------------
# GET /api/v1/plum/export/excel — Excel export (PLUM-10)
# ---------------------------------------------------------------------------


async def test_export_excel_sheets(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    GET /plum/export/excel returns an .xlsx binary with at least a Parts
    sheet and a BOM sheet (PLUM-10, D-16). openpyxl is used to verify the
    file is a valid workbook.
    """
    import openpyxl

    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:read"])

    resp = await client.get(
        "/api/v1/plum/export/excel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    content_type = resp.headers.get("content-type", "")
    assert "spreadsheetml" in content_type or "application/octet-stream" in content_type, (
        f"Unexpected content-type for Excel export: {content_type}"
    )

    # Verify file is a valid .xlsx workbook with expected sheets
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    sheet_names = wb.sheetnames
    assert "Parts" in sheet_names, f"Excel export missing 'Parts' sheet; got: {sheet_names}"
    assert "BOM" in sheet_names, f"Excel export missing 'BOM' sheet; got: {sheet_names}"


# ---------------------------------------------------------------------------
# POST /api/v1/plum/import/validate — import preview (PLUM-10)
# ---------------------------------------------------------------------------


async def test_import_preview_valid(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    POST /plum/import/validate with a valid JSON export payload returns
    new_count>=0, updated_count>=0, and errors=[] (PLUM-10, D-18 step 1).
    No data is written during preview.
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:write"])

    # Minimal valid import payload (empty parts list — no errors expected)
    payload = json.dumps({
        "schema_version": "1.0",
        "parts": [],
        "revisions": [],
        "bom_items": [],
        "avl_links": [],
    }).encode()

    files = {
        "file": ("plum_export.json", io.BytesIO(payload), "application/json")
    }
    resp = await client.post(
        "/api/v1/plum/import/validate",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, (
        f"Expected 200 for valid import preview, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert "new_count" in body
    assert "updated_count" in body
    assert body.get("errors") == [], f"Expected empty errors for valid payload, got: {body.get('errors')}"


# ---------------------------------------------------------------------------
# Import preview with unknown vendor reference (PLUM-10/D-18 validation)
# ---------------------------------------------------------------------------


async def test_import_preview_unknown_vendor(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    POST /plum/import/validate with an AVL link referencing an unknown
    vendor_id returns errors list with an ImportRowError for field="vendor_id"
    (PLUM-10, D-18 row-level validation).
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:write"])

    # Payload referencing a non-existent vendor UUID
    payload = json.dumps({
        "schema_version": "1.0",
        "parts": [{"id": "00000000-0000-0000-0000-000000000001", "part_number": "P99999", "active": True}],
        "revisions": [],
        "bom_items": [],
        "avl_links": [
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "part_id": "00000000-0000-0000-0000-000000000001",
                "vendor_id": "00000000-dead-beef-0000-000000000000",  # non-existent
                "preferred": False,
            }
        ],
    }).encode()

    files = {
        "file": ("plum_export.json", io.BytesIO(payload), "application/json")
    }
    resp = await client.post(
        "/api/v1/plum/import/validate",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, (
        f"Expected 200 for preview (validation errors in body), got {resp.status_code}"
    )
    body = resp.json()
    errors = body.get("errors", [])
    assert len(errors) > 0, "Expected validation errors for unknown vendor_id"
    fields = [e.get("field") for e in errors]
    assert "vendor_id" in fields, f"Expected error on 'vendor_id' field, got fields: {fields}"


# ---------------------------------------------------------------------------
# Import commit no-delete contract (PLUM-10/D-18)
# ---------------------------------------------------------------------------


async def test_import_commit_no_delete(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    POST /plum/import/commit only inserts or updates rows; it never deletes
    existing parts or revisions (PLUM-10, D-18 no-delete contract).

    After creating a part, running an import that omits that part must leave
    the original part still in the database.
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user", permissions=["plum:write", "plum:read"]
    )

    # Create a part that will NOT appear in the import payload
    part_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "No-delete test part — must survive import"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert part_resp.status_code == 201
    survivor_id = part_resp.json()["id"]

    # Import an empty payload (no parts)
    payload = json.dumps({
        "schema_version": "1.0",
        "parts": [],
        "revisions": [],
        "bom_items": [],
        "avl_links": [],
    }).encode()
    files = {
        "file": ("plum_export.json", io.BytesIO(payload), "application/json")
    }
    commit_resp = await client.post(
        "/api/v1/plum/import/commit",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert commit_resp.status_code == 200, (
        f"Import commit failed: {commit_resp.status_code} {commit_resp.text}"
    )

    # The original part must still exist
    detail_resp = await client.get(
        f"/api/v1/plum/parts/{survivor_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == 200, (
        "Import deleted an existing part — violates D-18 no-delete contract"
    )
    assert detail_resp.json()["id"] == survivor_id


# ---------------------------------------------------------------------------
# JSON export with a seeded AVL link — exercises the vendor_code lookup
# (build_json_export vendor resolution path, PLUM-07/PLUM-10)
# ---------------------------------------------------------------------------


async def test_export_json_with_avl_link(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    GET /plum/export/json after seeding a PlumAvlLink resolves the vendor_code
    from syerp_partner rather than short-circuiting on an empty vendor set
    (PLUM-07/PLUM-10). The exported part's avl entry carries the vendor's code.
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user",
        permissions=["plum:write", "plum:read", "syerp:write"],
    )

    # Seed a SYERP vendor
    vendor_resp = await client.post(
        "/api/v1/syerp/partners",
        json={"name": "Export AVL Vendor Co", "is_vendor": True, "is_customer": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert vendor_resp.status_code == 201, f"Vendor create failed: {vendor_resp.text}"
    vendor_id = vendor_resp.json()["id"]
    vendor_code = vendor_resp.json()["code"]

    # Seed a PLUM part and link it to the vendor (creates a PlumAvlLink row)
    part_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Export AVL link test part"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert part_resp.status_code == 201
    part_id = part_resp.json()["id"]

    avl_resp = await client.post(
        f"/api/v1/plum/parts/{part_id}/avl",
        json={"vendor_id": vendor_id, "preferred": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert avl_resp.status_code == 201, f"AVL link create failed: {avl_resp.text}"

    # Export must now run the vendor lookup and surface the vendor_code
    resp = await client.get(
        "/api/v1/plum/export/json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    avl_codes = [
        avl.get("vendor_code")
        for part in body.get("parts", [])
        for avl in part.get("avl", [])
    ]
    assert vendor_code in avl_codes, (
        f"Exported AVL did not resolve vendor_code {vendor_code}; got: {avl_codes}"
    )


# ---------------------------------------------------------------------------
# Import commit with a valid existing vendor code — exercises the commit-time
# vendor_code -> vendor_id resolution path (commit_import, PLUM-07/PLUM-10)
# ---------------------------------------------------------------------------


async def test_import_commit_valid_vendor(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """
    POST /plum/import/commit with an avl_link referencing a valid existing
    vendor code resolves that code to a vendor_id and upserts the AVL link
    (PLUM-07/PLUM-10). Commit returns 200 (validation passes for a known vendor).
    """
    from app.modules.auth.service import create_access_token

    token = create_access_token(
        subject="admin-user",
        permissions=["plum:write", "plum:read", "syerp:write"],
    )

    # Seed a SYERP vendor so its code is a known, valid reference
    vendor_resp = await client.post(
        "/api/v1/syerp/partners",
        json={"name": "Commit AVL Vendor Co", "is_vendor": True, "is_customer": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert vendor_resp.status_code == 201, f"Vendor create failed: {vendor_resp.text}"
    vendor_code = vendor_resp.json()["code"]

    # Payload: a part whose avl link references the valid vendor code
    payload = json.dumps({
        "schema_version": "1.0",
        "parts": [
            {
                "part_number": "P-COMMIT-AVL-1",
                "active": True,
                "revisions": [],
                "avl": [
                    {
                        "vendor_code": vendor_code,
                        "vendor_part_number": "VP-1",
                        "preferred": True,
                        "notes": None,
                        "price_breaks": [],
                    }
                ],
            }
        ],
    }).encode()
    files = {
        "file": ("plum_export.json", io.BytesIO(payload), "application/json")
    }
    commit_resp = await client.post(
        "/api/v1/plum/import/commit",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert commit_resp.status_code == 200, (
        f"Import commit with valid vendor failed: "
        f"{commit_resp.status_code} {commit_resp.text}"
    )
