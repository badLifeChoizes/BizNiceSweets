---
phase: 05-plum-parts-revisions
reviewed: 2026-06-29T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - backend/app/modules/plum/service.py
  - backend/app/modules/plum/router.py
  - backend/app/modules/plum/models.py
  - backend/app/modules/plum/schemas.py
  - backend/app/modules/plum/seed.py
  - backend/app/modules/plum/__init__.py
  - backend/app/core/models.py
  - backend/app/core/seed.py
  - backend/alembic/versions/0005_plum_tables.py
  - backend/tests/plum/test_parts.py
  - backend/tests/plum/test_revisions.py
  - frontend/src/routes/plum/PartsList.tsx
  - frontend/src/routes/plum/PartDetail.tsx
  - frontend/src/routes/plum/components/PartSheet.tsx
  - frontend/src/routes/plum/components/NewRevisionDialog.tsx
  - frontend/src/routes/plum/components/AdvanceStatusDialog.tsx
  - frontend/src/routes/plum/components/ArchivePartDialog.tsx
  - frontend/src/routes/plum/components/PlumNav.tsx
  - frontend/src/App.tsx
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-06-29
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 5 implements the PLUM module — parts header table, revision FSM, RBAC gating, tag join-table, and the Parts list + Part Detail frontend screens. The structural decisions (two-table model, MAX-based revision ordering, partial unique index for the one-Released invariant) are sound and follow the Phase 4 SYERP patterns faithfully. The async SQLAlchemy pitfalls documented in RESEARCH.md are correctly avoided: no ORM relationships are declared, and all queries use explicit `select()` calls.

Three blockers were found. The most serious is a security gap: the `released → obsolete` transition is reachable via the public advance endpoint, allowing any `plum:write` user to manually obsolete a Released revision without releasing a successor — breaking the one-Released-per-part audit trail (D-08). The second blocker is a domain-rule violation: revision-controlled fields are editable via PATCH while a revision is `in_review` (D-07 says "In Review = locked from edits"). The third is a functional defect: the Description column in the Parts list is hardcoded to "—" for every row because description is not included in the list endpoint response, making the column useless despite being searchable.

Five warnings round out the review: a misleading success toast, a dead class in the router, a duplicate unique index on `part_number`, missing `in_review` immutability in tests, and a hardcoded tag vocabulary in the frontend that will silently break if the DB seed order ever changes.

---

## Critical Issues

### CR-01: `released → obsolete` Transition Accessible via Public Endpoint (Security / Domain Invariant)

**File:** `backend/app/modules/plum/service.py:65-69` and `backend/app/modules/plum/router.py:287-323`

**Issue:** `VALID_TRANSITIONS["released"]` includes `"obsolete"`, and the advance endpoint applies no additional guard beyond the FSM table. Any authenticated user with `plum:write` can `POST /plum/parts/{id}/revisions/{rev_id}/advance` with `{ "target_status": "obsolete" }` on the currently Released revision and succeed — making that revision Obsolete without a successor being Released. This leaves the part with zero Released revisions, breaking the D-08 invariant from the other direction (the partial unique index `uq_plum_part_one_released` only prevents *two* Released rows; it does not enforce *at least one*). It also produces a misleading audit trail where `revision.obsoleted` fires without a corresponding `revision.released` for a new revision.

The docstring at line 737 acknowledges this path is "`obsolete` → not exposed via API directly (supersede-only path)", but the code does not enforce that restriction.

**Fix:** Remove `"obsolete"` from `VALID_TRANSITIONS["released"]`. The supersede path in `advance_revision_status` sets the prior revision to obsolete directly on the ORM object — it does not go through the FSM table. A separate entry for the internal-only transition is not needed and is actively harmful here.

```python
# service.py — VALID_TRANSITIONS
VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft":     ["in_review"],
    "in_review": ["released", "draft"],
    "released":  [],          # terminal via API; obsoleted internally by supersede only
    "obsolete":  [],          # terminal
}
```

---

### CR-02: `in_review` Revision-Controlled Fields Are Editable (Domain Rule Violation)

**File:** `backend/app/modules/plum/service.py:503-515`

**Issue:** `update_part` only raises HTTP 422 when the current revision is `"released"`. It silently accepts PATCH mutations to `description`, `category`, `unit_of_measure`, and `notes` when the current revision is `"in_review"`. D-07 (the locked decision from CONTEXT.md) explicitly states "In Review = locked from edits (submitted for review)". Allowing edits while a revision is in review undermines the integrity of the review process — the reviewer is approving content that can change underneath them.

```python
# service.py, update_part — current check:
if current_rev and current_rev.status == "released":
    raise HTTPException(422, ...)
```

**Fix:** Extend the immutability check to cover both locked states:

```python
IMMUTABLE_STATUSES = {"released", "in_review"}

if current_rev and current_rev.status in IMMUTABLE_STATUSES:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            f"Cannot edit revision-controlled fields on a "
            f"{current_rev.status.replace('_', ' ').title()} revision (D-07)."
        ),
    )
```

Also update the docstring and the test `test_released_revision_immutable` to add a parallel test for `in_review` immutability.

---

### CR-03: Description Column Always Shows "—" (Functional Defect — Data Never Sent)

**File:** `frontend/src/routes/plum/PartsList.tsx:285` and `backend/app/modules/plum/service.py:390-403`

**Issue:** The Parts list table has a "Description" column (matching the UI-SPEC at line 128 which specifies "plain text cell"), but the cell is hardcoded to `"—"` for every row. The `list_parts` service builds its response dict with `current_revision_label` and `current_revision_status` from the latest revision, but omits `current_revision_description`. `PartRead` (the Pydantic response schema) also has no `description` or `current_revision_description` field. The result is that users searching by description see matching results, but the column next to the part number is blank for all of them — a confusing UX gap.

**Fix (two parts):**

1. Add `current_revision_description` to the `list_parts` result dict in `service.py`:

```python
# service.py, list_parts — in the parts_out loop:
{
    "id": part.id,
    "part_number": part.part_number,
    "active": part.active,
    "created_at": part.created_at,
    "updated_at": part.updated_at,
    "current_revision_label": revision.revision_label if revision else None,
    "current_revision_status": revision.status if revision else None,
    "current_revision_description": revision.description if revision else None,  # ADD
    "tags": tag_map.get(part.id, []),
}
```

2. Add the field to `PartRead` in `schemas.py`:

```python
current_revision_description: Optional[str] = None
```

3. Replace the hardcoded dash in `PartsList.tsx`:

```tsx
<TableCell>{part.current_revision_description ?? '—'}</TableCell>
```

---

## Warnings

### WR-01: Success Toast Always Says "Prior revision obsoleted." Even on First Release

**File:** `frontend/src/routes/plum/components/AdvanceStatusDialog.tsx:68`

**Issue:** The `onSuccess` callback fires `toast("Revision X released. Prior revision obsoleted.")` unconditionally, even when `priorReleasedLabel` is `undefined` (i.e., this is the first-ever release for the part). The dialog body copy is correctly conditional on `priorReleasedLabel` (lines 97–99), but the toast is not. A user releasing a brand-new part's first revision sees "Prior revision obsoleted." which is factually incorrect and potentially confusing.

**Fix:**
```tsx
onSuccess: () => {
  void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId] })
  const msg = priorReleasedLabel
    ? `Revision ${revision.revision_label} released. Prior revision obsoleted.`
    : `Revision ${revision.revision_label} released.`
  toast(msg)
  onClose()
},
```

---

### WR-02: Dead Class `AdvanceStatusPayload` and Mid-File Import in Router

**File:** `backend/app/modules/plum/router.py:273-280`

**Issue:** `AdvanceStatusPayload(dict)` at line 273 is never used — `AdvanceStatusBody(BaseModel)` is the actual request body class. The dead class also precedes a `from pydantic import BaseModel` import at line 278 that belongs at the top of the file with the other imports. Mid-module imports are not a Python error, but they signal unfinished cleanup and can confuse static analysis tools.

**Fix:** Delete `AdvanceStatusPayload` and move `from pydantic import BaseModel` to the top-level import block.

---

### WR-03: Duplicate Unique Enforcement on `part_number` in Migration

**File:** `backend/alembic/versions/0005_plum_tables.py:82,86`

**Issue:** The migration creates both a `UniqueConstraint("part_number", name="uq_plum_part_number")` (line 82, inside `create_table`) and then a separate unique index `ix_plum_part_part_number` with `unique=True` (line 86, via `create_index`). PostgreSQL will happily create both, resulting in two separate unique indexes backing the same constraint. This doubles the write overhead for any `INSERT` or `UPDATE` on `plum_part.part_number` and makes the `downgrade()` code awkward (the implicit index from `UniqueConstraint` and the explicit unique index are separate objects). The `IntegrityError` retry logic in `service.py` is unaffected, but the schema is redundant.

**Fix:** Remove the redundant `UniqueConstraint` from `create_table` — the unique index created separately is sufficient and more explicit:

```python
op.create_table(
    "plum_part",
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("part_number", sa.String(length=50), nullable=False),
    sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("created_at", ...),
    sa.Column("updated_at", ...),
    # Remove: sa.UniqueConstraint("part_number", name="uq_plum_part_number"),
)
op.create_index("ix_plum_part_part_number", "plum_part", ["part_number"], unique=True)
```

Also update the `downgrade()` to ensure the index drop handles only the explicit index (currently correct, but the implicit index from the UniqueConstraint would also need dropping in the old schema).

---

### WR-04: Hardcoded Tag ID-to-Name Mapping in Frontend Will Silently Break

**File:** `frontend/src/routes/plum/components/PartSheet.tsx:75-82`

**Issue:** `TAG_VOCABULARY` is a hardcoded array of `{ id, name }` pairs that maps seed tag IDs (1–6) to their display names. This array is used in two ways: (1) to render the checkbox list, and (2) to re-map tag *names* (from `PartRead.tags: string[]`) back to tag *IDs* for pre-selecting checkboxes in edit mode (lines 135–138). This coupling means:

- If the seed order ever changes (e.g., inserting a new tag before "Purchased"), the IDs will be wrong, silently submitting incorrect `tag_ids` on every edit.
- If a user-created tag (when `plum.tag_vocabulary_editable = "true"`) appears in `part.tags`, the `find()` returns `undefined`, which is filtered out — the tag is visually lost from the pre-selection on edit.

**Fix:** Add a `GET /api/v1/plum/tags` endpoint (or reuse the existing list endpoint if it exists) that returns the current tag vocabulary, and use `useQuery` to fetch it in `PartSheet`. Store the full `{ id, name }` records from the API response and use them for both rendering and ID resolution. If a full tags endpoint is out of scope for this phase, at minimum add a comment warning that `TAG_VOCABULARY` is order-sensitive and must be kept in sync with the seed.

---

### WR-05: `in_review` Immutability Is Not Covered by Tests

**File:** `backend/tests/plum/test_revisions.py` (missing test case)

**Issue:** `test_released_revision_immutable` verifies that PATCHing a Released revision returns 422, which is correct. Once CR-02 is fixed (making `in_review` also immutable), there is no corresponding test to enforce that boundary. The test suite would not catch a regression that re-opens the `in_review` edit path.

**Fix:** Add a `test_in_review_revision_immutable` test that creates a part, advances its revision to `in_review`, then attempts a PATCH with `description` and asserts 422. This mirrors the existing pattern in `test_released_revision_immutable`.

---

## Info

### IN-01: `create_revision` Writes Audit After `db.commit()` — Inconsistent with Part-Level Audit Pattern

**File:** `backend/app/modules/plum/service.py:692-703`

**Issue:** In `create_revision`, the main data commit happens at line 692, and `write_audit` is called at line 695 after the commit. `write_audit` itself calls `db.commit()` (auth/service.py:342), so the audit row is written in a second, separate transaction. If the process dies between the main commit and the audit commit, the revision exists with no audit trail. This is the same pattern used in `advance_revision_status` (line 791 commit, then line 802 audit). The inconsistency is that part-level audit events (`part.created`, `part.archived`) are written in the router handler *after* the service returns, creating a similar gap. Both patterns tolerate this as an accepted trade-off (audit loss vs. data rollback), but the service-level audit in `create_revision` should at minimum be documented as a known gap.

**Fix (minor):** This is acceptable for v1 but add a comment noting the two-transaction gap. The more robust fix (same transaction) would require passing the audit into the commit before calling `db.commit()`, which is a larger refactor.

---

### IN-02: `AdvanceStatusPayload` Docstring Is Wrong

**File:** `backend/app/modules/plum/router.py:273-276`

**Issue:** The docstring on the dead class says "Defined inline to avoid a separate schema file for a single-field body" — but `AdvanceStatusBody(BaseModel)` immediately follows and *is* that inline definition. The docstring was never updated when the approach changed from a plain dict to a Pydantic model.

**Fix:** Delete the class entirely (see WR-02); no separate fix needed if WR-02 is addressed.

---

### IN-03: `ArchivePartDialog` Body Copy Deviates from UI-SPEC

**File:** `frontend/src/routes/plum/components/ArchivePartDialog.tsx:81`

**Issue:** UI-SPEC line 207 specifies the archive dialog body as `"{part_number} — {description} will be hidden from the parts list."`. The current implementation renders only `"{part_number} will be hidden…"` without `— {description}`. This is a minor copy deviation, not a functional defect. It is partially caused by the same root issue as CR-03 (`PartRead` does not carry `description`), but even if description were available it is not included here.

**Fix:** Once CR-03 is resolved and `current_revision_description` is in `PartRead`, update the dialog body:

```tsx
? `${part.part_number}${part.current_revision_description ? ` — ${part.current_revision_description}` : ''} will be hidden from the parts list. …`
```

---

_Reviewed: 2026-06-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
