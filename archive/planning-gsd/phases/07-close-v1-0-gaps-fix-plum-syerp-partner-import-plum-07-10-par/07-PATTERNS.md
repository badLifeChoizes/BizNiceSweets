# Phase 7: Close v1.0 Gaps - Pattern Map

**Mapped:** 2026-07-02
**Files analyzed:** 3 modified (2 code, 1 test) + 2 docs reconciliation targets
**Analogs found:** 5 / 5 (this is a same-file bug-fix phase — the "analog" for each fix is a sibling code path in the same or a neighboring file, not a different module)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `backend/app/modules/plum/service.py` (4 import sites: lines 1634, 2139, 2607, 2740) | service | request-response | Correct import already used everywhere else in the codebase: `backend/app/modules/syerp/models.py:39` (`class Partner(Base)`) and `backend/app/modules/syerp/service.py`/`router.py` (which import `Partner` correctly) | exact — same file, same bug pattern repeated 4x, fix is copy-paste identical at each site |
| `backend/app/modules/plum/service.py` (`generate_part_number`, lines 108-136) | service | CRUD | Same function, in place — no external analog needed; SQLAlchemy `cast`/`func` usage precedent exists via `func.max` already imported in this file (line 66) | role-match — self-contained query-shape fix, no other numeric-cast-ordering query exists elsewhere in the codebase to copy from |
| `frontend/src/routes/plum/ImportExport.tsx` (`commitImportMutation`, lines 164-185) | component (mutation hook) | request-response | `frontend/src/routes/plum/components/ArchivePartDialog.tsx` (full file, esp. lines 16, 42, 49-53) | exact — identical `useMutation` + `useQueryClient` + `invalidateQueries(['plum','parts'])` pattern, same route tree, same query key |
| `backend/tests/plum/test_parts.py` (new test: `test_generate_part_number_digit_boundary`) | test | CRUD | `backend/tests/plum/test_parts.py::test_create_duplicate_part_number` (lines 57-82) and `::test_update_part` (lines 85-125) for direct-DB-seed + assertion style | exact — same test file, same fixture conventions (`client`, `skip_if_no_db`, `create_access_token`) |
| `backend/tests/plum/test_avl.py::test_add_avl_link` (lines 26-76, existing — run only, not authored) | test | request-response | N/A — pre-existing, unmodified; run live per research Pitfall 1/2 | n/a — regression re-run, not a new pattern |
| `backend/tests/plum/test_import_export.py::test_export_json`, `::test_import_preview_unknown_vendor` (existing — run/possibly extend fixture) | test | file-I/O | Same file's other test functions for fixture-seeding style | n/a — regression re-run/fixture-extend, not a new pattern |
| `.planning/REQUIREMENTS.md`, `docs/features/requirements-progress.md` | config (docs) | transform | N/A — documentation edit, no code analog | n/a |

## Pattern Assignments

### `backend/app/modules/plum/service.py` — `SyerpPartner`→`Partner` import fix (4 sites: lines 1634, 2139, 2607, 2740)

**Analog:** `backend/app/modules/syerp/models.py:39` (the real class) — every other consumer of `Partner` in the codebase (e.g. `backend/app/modules/syerp/router.py`, `backend/app/modules/syerp/service.py`, `backend/tests/syerp/test_partners.py`) already imports it correctly as `Partner`.

**Current broken pattern** (identical at all 4 sites, e.g. lines 1632-1648):
```python
from app.modules.auth.service import write_audit
from app.modules.plum.models import PlumAvlLink
from app.modules.syerp.models import SyerpPartner   # BROKEN — class does not exist

# Validate vendor is_vendor=True (T-06-07)
vendor_result = await db.execute(
    select(SyerpPartner).where(
        SyerpPartner.id == data.vendor_id,
        SyerpPartner.is_vendor == True,  # noqa: E712
    )
)
```

**Fix pattern (verbatim at all 4 sites — function-local import, alias only, no other line touched):**
```python
from app.modules.syerp.models import Partner as SyerpPartner  # was: import SyerpPartner (nonexistent)
```

**Analog class definition** (`backend/app/modules/syerp/models.py:39-67`):
```python
class Partner(Base):
    __tablename__ = "syerp_partner"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    is_vendor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_customer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
```

**All 4 call sites and their local variable usage (confirmed via grep — all reference `SyerpPartner.*`, so aliasing is sufficient and no other line needs to change):**
| Line | Function | Usage |
|------|----------|-------|
| 1634 | `add_avl_link()` | `select(SyerpPartner).where(SyerpPartner.id == ..., SyerpPartner.is_vendor == True)` |
| 2139 | `build_json_export()` | `select(SyerpPartner.id, SyerpPartner.code).where(SyerpPartner.id.in_(...))` |
| 2607 | `validate_import()` | `select(SyerpPartner.code).where(SyerpPartner.is_vendor.is_(True), SyerpPartner.code.in_(...))` |
| 2740 | `commit_import()` | `select(SyerpPartner.id, SyerpPartner.code).where(SyerpPartner.is_vendor.is_(True), SyerpPartner.code.in_(...))` |

**Anti-pattern to avoid (per RESEARCH.md):** Do not touch `syerp/models.py` (the real class is correct) and do not widen/narrow the `WHERE` clause (`is_vendor` filter) while fixing the import — this is an import-only fix.

---

### `backend/app/modules/plum/service.py` — `generate_part_number()` numeric-ordering fix (lines 108-136)

**Analog:** none external — self-contained query-shape correction in the same function. The existing `create_part()` retry-on-`IntegrityError` wrapper (lines 273-327) is the caller and its contract (returns a `P#####` string; caller handles collision) must not change.

**Current broken pattern** (lines 108-136, full function):
```python
async def generate_part_number(db: AsyncSession) -> str:
    from app.modules.plum.models import PlumPart

    result = await db.execute(
        select(func.max(PlumPart.part_number)).where(PlumPart.part_number.like("P%"))
    )
    max_pn: str | None = result.scalar()

    if max_pn is None:
        return "P00001"

    try:
        suffix = int(max_pn[1:])
    except (IndexError, ValueError):
        suffix = 0

    return f"P{suffix + 1:05d}"
```
Bug: `func.max()` on a VARCHAR is lexicographic — `"P100000" < "P99999"` as strings, so past a 5-vs-6-digit boundary this silently returns a stale max, and the existing Python `try/except (IndexError, ValueError)` fallback does NOT catch this because parsing `"P99999"[1:]` succeeds fine, it's just the wrong row that was selected by SQL.

**Fix pattern (per RESEARCH.md Pattern 2 — filter to strictly-numeric-suffixed rows BEFORE casting, per Pitfall 3):**
```python
from sqlalchemy import cast, Integer

async def generate_part_number(db: AsyncSession) -> str:
    from app.modules.plum.models import PlumPart

    result = await db.execute(
        select(PlumPart.part_number)
        .where(PlumPart.part_number.op("~")(r"^P[0-9]+$"))  # Postgres regex: numeric suffix only
        .order_by(cast(func.substring(PlumPart.part_number, 2), Integer).desc())
        .limit(1)
    )
    max_pn: str | None = result.scalar()

    if max_pn is None:
        return "P00001"

    try:
        suffix = int(max_pn[1:])
    except (IndexError, ValueError):
        suffix = 0

    return f"P{suffix + 1:05d}"
```

**Critical constraint (Pitfall 3):** existing non-numeric-suffix part numbers are real, live data — e.g. `"P-DUPE-01"` (`backend/tests/plum/test_parts.py:69`, also live in the dev DB per RESEARCH.md's Runtime State Inventory) and explicit numeric overrides like `"P99901"` (`backend/tests/plum/test_parts.py:106`). The `.op("~")(r"^P[0-9]+$")` filter MUST run before the cast, or a bare `CAST(SUBSTRING(part_number,2) AS INTEGER)` over all `LIKE 'P%'` rows will throw a Postgres `invalid input syntax for type integer` on `"P-DUPE-01"` — a worse regression than the bug being fixed. Keep the Python-side `try/except (IndexError, ValueError)` as defense-in-depth (matches existing style, cheap).

**Import note:** `cast` and `Integer` are not currently imported in `service.py` (only `func, or_, select` from `sqlalchemy`, line 66) — add them to the existing import line: `from sqlalchemy import cast, func, Integer, or_, select`.

---

### `frontend/src/routes/plum/ImportExport.tsx` — cache invalidation fix (`commitImportMutation`, lines 164-185)

**Analog:** `frontend/src/routes/plum/components/ArchivePartDialog.tsx` (full file, 113 lines) — exact same route tree, exact same query key, exact same `useMutation`/`useQueryClient` combination.

**Imports pattern to copy** (`ArchivePartDialog.tsx:16`):
```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'
```
Current `ImportExport.tsx:30` only imports `useMutation` — must be widened to include `useQueryClient`.

**Hook-setup pattern to copy** (`ArchivePartDialog.tsx:41-42`):
```typescript
export function ArchivePartDialog({ open, part, onClose }: ArchivePartDialogProps) {
  const queryClient = useQueryClient()
```
`ImportExport.tsx`'s `export function ImportExport() {` body (line 103) needs an equivalent `const queryClient = useQueryClient()` added near the top, alongside existing `useState`/`useRef` calls (lines 105-109).

**onSuccess invalidation pattern to copy** (`ArchivePartDialog.tsx:49-53`):
```typescript
onSuccess: () => {
  void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })
  toast('Part archived.')
  onClose()
},
```

**Current broken `commitImportMutation.onSuccess`** (`ImportExport.tsx:175-179`):
```typescript
onSuccess: (data) => {
  setCommittedData(data)
  setImportStep('committed')
  toast(`Import complete. ${data.inserted} inserted, ${data.updated} updated.`)
},
```

**Fix — add exactly one line** (matches RESEARCH.md Pattern 3 verbatim):
```typescript
onSuccess: (data) => {
  setCommittedData(data)
  setImportStep('committed')
  toast(`Import complete. ${data.inserted} inserted, ${data.updated} updated.`)
  void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })  // ADD THIS LINE
},
```

**Scope note:** Only `commitImportMutation` needs this — `exportJsonMutation`, `exportExcelMutation`, and `uploadPreviewMutation` (preview-only, no commit) do not mutate visible Parts List rows and correctly have no invalidation today.

---

### `backend/tests/plum/test_parts.py` — new test `test_generate_part_number_digit_boundary`

**Analog:** `test_create_duplicate_part_number` (lines 57-82) for the "seed explicit part_number via API, then assert on a subsequent operation" shape; `test_update_part` (lines 85-125) for the direct-DB-session-read verification style (`AsyncSessionLocal`).

**Imports/fixture pattern to copy** (file header, lines 25-26 + per-test pattern lines 40-42):
```python
import pytest
import httpx

# inside a test function:
from app.modules.auth.service import create_access_token
token = create_access_token(subject="admin-user", permissions=["plum:write"])
```

**Seed-via-explicit-part_number pattern to copy** (lines 66-72, `test_create_duplicate_part_number`):
```python
first_resp = await client.post(
    "/api/v1/plum/parts",
    json={"part_number": "P-DUPE-01", "description": "Original part"},
    headers={"Authorization": f"Bearer {token}"},
)
assert first_resp.status_code == 201
```

**Recommended new test body** (per RESEARCH.md Wave 0 Gaps — seed `"P99999"` and `"P100000"` explicitly, then call the auto-generator via a part create with no `part_number`, assert result is `"P100001"`):
```python
async def test_generate_part_number_digit_boundary(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    """Auto-generated part_number is numerically correct past a digit-width
    boundary (5-digit vs 6-digit), not lexicographically stale (PLUM-01, D-06)."""
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="admin-user", permissions=["plum:write"])

    # Seed a 5-digit and a 6-digit explicit part_number directly via the API
    # (bypasses the generator; both are valid explicit overrides per D-06)
    for pn in ("P99999", "P100000"):
        resp = await client.post(
            "/api/v1/plum/parts",
            json={"part_number": pn, "description": f"Boundary seed {pn}"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, f"Seed {pn} failed: {resp.text}"

    # Auto-generate the next number — must be numerically P100001, not a
    # lexicographic-stale duplicate of an existing 5-digit-max row
    auto_resp = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Auto-generated after boundary"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert auto_resp.status_code == 201, f"Auto-create failed: {auto_resp.text}"
    assert auto_resp.json()["part_number"] == "P100001", (
        f"Expected P100001 past the digit-width boundary, got "
        f"{auto_resp.json()['part_number']}"
    )
```
`[Note to planner/executor: verify test DB isolation/ordering — if other tests in the same run seed part numbers above P100001, adjust the assertion to a monotonic ">=" check on the numeric suffix rather than an exact string match; RESEARCH.md flags the live dev DB already has data past this boundary, so exact-value assertions may need care in a shared, non-transactional test DB.]`

---

## Shared Patterns

### Cache invalidation on mutation (TanStack Query)
**Source:** `frontend/src/routes/plum/components/ArchivePartDialog.tsx:16,42,49-53` — also present identically in `PartSheet.tsx`, `AvlLinkSheet.tsx`, `BomLineSheet.tsx`, `NewRevisionDialog.tsx`, `AdvanceStatusDialog.tsx` (per RESEARCH.md verification).
**Apply to:** `ImportExport.tsx`'s `commitImportMutation` only (this phase's scope).
```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'
// ...
const queryClient = useQueryClient()
// ... inside the relevant mutation's onSuccess:
void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })
```

### Aliased import for a misnamed cross-module class reference
**Source:** correct usage pattern is the class definition itself, `backend/app/modules/syerp/models.py:39`.
**Apply to:** all 4 `SyerpPartner` import sites in `backend/app/modules/plum/service.py` (lines 1634, 2139, 2607, 2740) — identical one-line fix at each, do not consolidate into a module-level import (existing convention in this file is function-local imports to avoid circular-import risk between `plum` and `syerp` modules — preserve that convention, do not hoist to the top of the file).
```python
from app.modules.syerp.models import Partner as SyerpPartner
```

### Regex-filtered numeric CAST ordering for a formatted-string sequence column
**Source:** no existing analog in this codebase (net-new query shape) — RESEARCH.md Pattern 2, standard SQLAlchemy 2.0 Core / Postgres construct.
**Apply to:** `generate_part_number()` only, in this phase. Flagged MEDIUM confidence by RESEARCH.md (Assumption A1) — budget a test-verify cycle.
```python
from sqlalchemy import cast, Integer
select(PlumPart.part_number).where(PlumPart.part_number.op("~")(r"^P[0-9]+$")).order_by(
    cast(func.substring(PlumPart.part_number, 2), Integer).desc()
).limit(1)
```

### Live-DB test execution (process pattern, not code pattern)
**Source:** RESEARCH.md Pitfall 1 — `podman exec compose_api_1 pytest ...`, not host `backend/.venv/bin/pytest`.
**Apply to:** all Wave-0/regression test runs in this phase (`test_avl.py`, `test_import_export.py`, `test_parts.py`) — running from the host silently skips `skip_if_no_db` tests, which is exactly the failure mode that let PLUM-07/10 ship broken.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `generate_part_number()` numeric-ordering query | service (query fragment) | CRUD | No other "numeric MAX over a formatted-string sequence column" query exists anywhere else in the codebase to copy from — this is RESEARCH.md's own Pattern 2 (training-knowledge-derived SQLAlchemy/Postgres construct), not a codebase analog. Planner should treat RESEARCH.md Code Examples as the source of truth here, with a Wave-0 test-verify cycle budgeted (Assumption A1). |

## Metadata

**Analog search scope:** `backend/app/modules/plum/`, `backend/app/modules/syerp/`, `backend/tests/plum/`, `frontend/src/routes/plum/` (including `components/`)
**Files scanned:** `service.py` (plum, full grep + targeted reads), `models.py` (plum, syerp — targeted reads), `ImportExport.tsx` (full), `ArchivePartDialog.tsx` (full), `test_parts.py` (full), `test_avl.py` (partial, lines 1-80)
**Pattern extraction date:** 2026-07-02
