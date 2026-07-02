# Phase 7: Close v1.0 Gaps (PLUM-07/10 Partner import, PLUM-01 part-number ordering, import cache invalidation, verify Phase 6) - Research

**Researched:** 2026-07-02
**Domain:** Bug-fix / verification phase on an existing FastAPI + SQLAlchemy 2.0 + React/TanStack Query codebase (no new libraries)
**Confidence:** HIGH

## Summary

This is a closure phase, not a greenfield build. Every "unknown" it contains was already root-caused by `.planning/v1.0-MILESTONE-AUDIT.md` on 2026-07-01 via live reproduction against a running Podman stack. This research independently re-verified each finding by reading the actual source at the cited line numbers — all three bugs are confirmed present, isolated, and mechanically simple to fix. No new packages, no new architecture, no schema migration is required for any of the three code fixes.

The three defects are: (1) `backend/app/modules/plum/service.py` imports a nonexistent class `SyerpPartner` at 4 call sites (the real class is `Partner` in `app/modules/syerp/models.py:39`) — this is a pure `ImportError`→HTTP 500 at runtime, not a logic bug, and the fix is a one-line aliased-import change at each site; (2) `generate_part_number()` (service.py:108-136) orders existing part numbers with `func.max()` on a VARCHAR column, which is lexicographic, not numeric — past a digit-width boundary (`"P100000" < "P99999"` as strings) it returns a stale max and hands out a duplicate number, causing a deterministic (not racy) unique-constraint 500 on create; the fix is a numeric-cast ORDER BY; (3) `frontend/src/routes/plum/ImportExport.tsx`'s `commitImportMutation` never calls `queryClient.invalidateQueries` after a successful import commit, so the Parts List can show stale data for up to the global 30s `staleTime` — the fix is a two-line addition matching the exact pattern already used in four sibling components in the same route tree.

Phase 7 additionally must close the process gap noted in the audit: Phase 6 has no `06-VERIFICATION.md` and the 06-05 Task 4 human-verify checkpoint (7 UI flows + Released-immutability check) was never run. Since the bug fixes touch the exact code paths that checkpoint exercises (AVL add, import/export, part creation), the most efficient sequencing is to land the 3 fixes first, then run one consolidated human-verify pass that satisfies both the Phase-6 checkpoint and Phase-7's own acceptance criteria — do not plan two separate manual verification passes.

**Primary recommendation:** Treat this as a single-wave bug-fix phase (fixes are independent of each other and touch disjoint files) followed by a verification wave: automated regression tests for all three bugs (the repo's live DB is reachable from inside `compose_api_1`, so Wave-0 tests need not stay `skip_if_no_db`-skipped for this phase), then the consolidated human-verify checkpoint, then reconciliation of `.planning/REQUIREMENTS.md` traceability and `docs/features/requirements-progress.md` (which currently and incorrectly marks PLUM-07/PLUM-10 "Complete").

<phase_requirements>
## Phase Requirements

No CONTEXT.md exists for this phase (user chose to proceed without discuss-phase) and ROADMAP.md lists `Requirements: TBD`. The following candidate requirement IDs are derived from the phase title and `.planning/v1.0-MILESTONE-AUDIT.md`'s gap list — the planner should treat these as the working requirement set unless the user redirects.

| ID | Description | Research Support |
|----|-------------|-------------------|
| PLUM-07 | User can link a part to one or more vendors (FK to SYERP vendors / AVL) | `SyerpPartner`→`Partner` fix at service.py:1634 (`add_avl_link`) restores this; regression test `test_avl.py::test_add_avl_link` run live |
| PLUM-10 | User can import and export PLUM data as JSON and Excel | `SyerpPartner`→`Partner` fix at service.py:2139/2607/2740 restores vendor cross-ref export/import; `ImportExport.tsx` cache-invalidation fix closes the stale-Parts-List gap; regression tests `test_import_export.py::test_export_json`, `::test_import_preview_unknown_vendor` run live |
| PLUM-01 | User can create, view, edit, and delete parts | `generate_part_number()` numeric-ordering fix (service.py:108-136) restores reliable auto part-numbering past a digit-width boundary; new Wave-0 test required (see Validation Architecture) |
| PLUM-04 | User can build a multi-level BOM and view it as an expandable tree | Not code-broken (audit: WIRED) — in scope only for the "verify Phase 6" human-verify checkpoint + traceability reconciliation, no code fix needed |
| PLUM-05 | User can view a flat BOM with quantity roll-up across levels | Same as PLUM-04 — verification only |
| PLUM-06 | User can run where-used analysis to see which assemblies consume a part | Same as PLUM-04 — verification only |
| PLUM-08 | User can set part pricing/cost and see cost roll-up across a BOM | Manual-cost path WIRED; vendor-price path was blocked only by the PLUM-07 bug (transitively fixed) — verification only, no separate code fix |
| PLUM-09 | User can view margin analysis for a product | Not code-broken (audit: WIRED) — verification only |

Out of scope for this phase (explicitly not part of the audit's gap list): CORE-01, CORE-09 traceability checkbox lag is a documentation-only fix the planner may bundle into the Wave-4 reconciliation task but is not a functional gap.
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| AVL vendor validation (`SyerpPartner`→`Partner` fix) | API / Backend | — | Pure service-layer import correction; no other tier touched |
| Import/export vendor cross-reference (`SyerpPartner`→`Partner` fix) | API / Backend | — | Same service.py file, same class rename, 3 more call sites |
| Part-number generation ordering | API / Backend | Database / Storage | Query-shape fix against existing VARCHAR column; no schema change |
| Import cache invalidation | Frontend Server (SSR: N/A, this is a CSR SPA) → Browser / Client | — | TanStack Query cache is client-side; fix is entirely in `ImportExport.tsx` |
| Phase 6 verification / human-verify | Browser / Client (manual UAT) | API / Backend (test suite) | Both automated backend tests and live-clicked UI flows are in scope |
| Requirements traceability reconciliation | Documentation (no tier) | — | `.planning/REQUIREMENTS.md` + `docs/features/requirements-progress.md` edits only |

## Standard Stack

No new libraries are introduced by this phase. Existing versions, confirmed against the running environment:

| Component | Version | Source |
|-----------|---------|--------|
| SQLAlchemy | 2.0.51 | `[VERIFIED: pip show, backend/.venv]` |
| FastAPI stack (unchanged) | — | not touched by these fixes |
| openpyxl | 3.1.5 | `[VERIFIED: pip show, backend/.venv]` — already used by the Excel import/export this phase touches indirectly (no version change) |
| @tanstack/react-query | 5.101.1 | `[VERIFIED: frontend/package.json]` |
| PostgreSQL | 17 (alpine) | `[VERIFIED: compose/compose.yml image tag; podman ps confirms postgres:17-alpine running]` |
| Alembic head | `0006` | `[VERIFIED: podman exec compose_api_1 alembic heads → 0006 (head), matches current` |

**Installation:** None — no new packages. `Package Legitimacy Audit` section below is N/A for this reason.

## Package Legitimacy Audit

**Not applicable.** This phase adds zero new third-party packages. All three fixes use libraries already installed and imported elsewhere in the same files (`sqlalchemy.func`/`cast`/`Integer` are stdlib-to-SQLAlchemy-core, already partially imported in `service.py`; `@tanstack/react-query`'s `useQueryClient`/`invalidateQueries` is already used in 5 sibling files in the same route tree). No `slopcheck`/registry verification is required.

## Architecture Patterns

### System Architecture Diagram (bug-fix data flow, not new architecture)

```
[Browser: AvlLinkSheet.tsx]                [Browser: ImportExport.tsx]
        │ POST /plum/parts/{id}/avl                │ POST /plum/import/commit
        ▼                                           ▼
[FastAPI router.py] ──────────────────────► [FastAPI router.py]
        │                                           │
        ▼                                           ▼
[plum/service.py: add_avl_link()]        [plum/service.py: commit_import()]
        │  imports SyerpPartner (BROKEN)            │  imports SyerpPartner (BROKEN)
        │  ── FIX: alias `Partner as SyerpPartner`──┘
        ▼
[SELECT ... FROM syerp_partner WHERE id=? AND is_vendor=true]
        │
        ▼
  200 OK / 422 (vendor not found)  ──vs currently──►  500 ImportError

[FastAPI: create_part() → generate_part_number()]
        │  SELECT MAX(part_number) WHERE part_number LIKE 'P%'  (lexicographic — BROKEN
        │  past digit-width boundary)
        │  ── FIX: CAST(SUBSTRING(part_number,2) AS INTEGER), numeric ORDER BY DESC LIMIT 1,
        │          filtered to rows matching ^P[0-9]+$ only
        ▼
  next unique "P#####"  ──vs currently──►  duplicate → 409/500 on next create

[Browser: ImportExport.tsx commitImportMutation.onSuccess]
        │  currently: setState only, no cache invalidation
        │  ── FIX: queryClient.invalidateQueries({queryKey:['plum','parts']})
        ▼
  Parts List refetches immediately  ──vs currently──►  stale up to 30s (global staleTime)
```

### Recommended Task Structure

```
Wave 1 (parallel — disjoint files):
  Task A: backend/app/modules/plum/service.py — SyerpPartner→Partner fix (4 sites)
  Task B: backend/app/modules/plum/service.py — generate_part_number() numeric ordering
    (same file as Task A — sequence A then B, or one task doing both; do NOT parallelize
     two executors on the same file)
  Task C: frontend/src/routes/plum/ImportExport.tsx — cache invalidation (independent file)

Wave 2 (depends on Wave 1):
  Task D: Wave-0 regression tests (backend: AVL/import live against compose_api_1 DB;
           part-number boundary test; frontend: no new test needed — cache invalidation
           is not practically unit-testable without a live query client harness, cover
           via human-verify instead)

Wave 3 (depends on Wave 2 — consolidated human-verify):
  Task E: checkpoint:human-verify — run the 8-item Phase-6 UAT list from 06-05-SUMMARY.md
           PLUS explicit re-check of: AVL add (no 500), import w/ vendor refs (no 500),
           part creation past a seeded high part_number, Parts List refresh <1s after
           import commit (no manual refresh)

Wave 4 (depends on Wave 3 — docs only):
  Task F: Reconcile .planning/REQUIREMENTS.md (check PLUM-04..10, CORE-01, CORE-09) and
           docs/features/requirements-progress.md evidence column
  Task G: Produce 06-VERIFICATION.md / 07-VERIFICATION.md (gsd-verifier / /gsd:verify-work
           territory — plan should include the step but the artifact itself is generated by
           the verifier agent, not hand-authored by an executor task)
```

### Pattern 1: Aliased import to fix wrong class name (minimal diff)
**What:** Replace `from app.modules.syerp.models import SyerpPartner` with `from app.modules.syerp.models import Partner as SyerpPartner` at all 4 call sites.
**When to use:** When every downstream reference in the function body already uses the name `SyerpPartner.*` (confirmed true at all 4 sites — see Code Examples) — aliasing avoids touching 12 additional lines of `SyerpPartner.id`/`SyerpPartner.code`/`SyerpPartner.is_vendor` references and minimizes diff/review surface.
**Example:**
```python
# Source: backend/app/modules/syerp/models.py:39 (class Partner(Base): ...)
# backend/app/modules/plum/service.py:1634 (inside add_avl_link)
from app.modules.syerp.models import Partner as SyerpPartner  # was: import SyerpPartner (nonexistent)
```
`[VERIFIED: codebase read, backend/app/modules/syerp/models.py:39 confirms class Partner(Base)]`

### Pattern 2: Numeric-safe MAX on a mixed-format VARCHAR sequence column
**What:** Replace `select(func.max(PlumPart.part_number)).where(PlumPart.part_number.like("P%"))` with a query that filters to strictly-numeric-suffixed rows and orders by the cast integer value, not the string.
**When to use:** Any time a "next sequence number" is derived from a VARCHAR column that can also contain user-supplied non-sequential values (e.g. `"P-DUPE-01"`, `"P99901"` explicit, `"SRCHPN001"` — all exist as valid part_numbers per `test_parts.py`). A naive `~ '^P[0-9]+$'` regex filter is required, not just `LIKE 'P%'`, because `LIKE 'P%'` also matches non-numeric suffixes that would break a blind `CAST(SUBSTRING(...) AS INTEGER)`.
**Example:**
```python
# Source: pattern based on SQLAlchemy 2.0 Core (sqlalchemy.cast, sqlalchemy.Integer) —
# [ASSUMED: standard SQLAlchemy/Postgres construct, not verified against a live query in
# this research session; MEDIUM confidence — verify with a Wave-0 test before merge]
from sqlalchemy import cast, Integer

result = await db.execute(
    select(PlumPart.part_number)
    .where(PlumPart.part_number.op("~")(r"^P[0-9]+$"))  # Postgres POSIX regex: numeric suffix only
    .order_by(cast(func.substring(PlumPart.part_number, 2), Integer).desc())
    .limit(1)
)
max_pn: str | None = result.scalar()
```
Note: `.op("~")` emits Postgres's native regex operator — this is Postgres-specific (acceptable; the project pins `postgres:17-alpine`, no other DB backend is supported per `compose/compose.yml`). Keep the existing Python-side `try/except (IndexError, ValueError)` fallback in `generate_part_number()` as defense-in-depth even after the SQL-side filter is added — cheap and matches existing style.

### Pattern 3: Cache invalidation after mutation (existing project convention)
**What:** Call `queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })` inside a mutation's `onSuccess`.
**When to use:** Any mutation that changes rows visible in the Parts List. Already the established pattern in this exact route tree — not a new pattern, just a missed application of an existing one.
**Example:**
```typescript
// Source: frontend/src/routes/plum/components/ArchivePartDialog.tsx:50 (existing, working pattern)
const archiveMutation = useMutation<PartRead, Error, string>({
  // ...
  onSuccess: () => {
    void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })
  },
})
```
```typescript
// FIX to apply verbatim-pattern in frontend/src/routes/plum/ImportExport.tsx
// 1. Add to imports: `useMutation, useQueryClient` (currently only `useMutation` imported, line 30)
// 2. Add inside ImportExport(): `const queryClient = useQueryClient()`
// 3. In commitImportMutation's onSuccess (line ~175-179), add:
onSuccess: (data) => {
  setCommittedData(data)
  setImportStep('committed')
  toast(`Import complete. ${data.inserted} inserted, ${data.updated} updated.`)
  void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })  // ADD THIS LINE
},
```
`[VERIFIED: codebase read, frontend/src/routes/plum/ImportExport.tsx:29-185 confirms useQueryClient is not currently imported or used; 4 sibling files (ArchivePartDialog.tsx, PartSheet.tsx, AvlLinkSheet.tsx, BomLineSheet.tsx, NewRevisionDialog.tsx, AdvanceStatusDialog.tsx) all invalidate ['plum','parts'] or ['plum','parts',partId] on success]`

### Anti-Patterns to Avoid
- **Renaming the real `Partner` class instead of fixing the import:** `Partner` is referenced correctly throughout `app/modules/syerp/` (router, schemas, tests) — do not touch `syerp/models.py`. The bug is 100% isolated to `plum/service.py`'s 4 import statements.
- **Fixing only `add_avl_link` and skipping the other 3 sites:** All 4 sites (1634, 2139, 2607, 2740) are independently broken and independently exercised by different user flows (AVL add, JSON export, import preview, import commit). A partial fix leaves PLUM-10 (import/export) broken while appearing to fix PLUM-07.
- **Adding a single-retry loop as a "fix" for the part-number bug:** The audit explicitly notes this was already tried and doesn't work — the bug is deterministic (the same stale max is returned every time), not a race condition. Retry logic is the wrong category of fix.
- **Global `staleTime: 0` or blanket `refetchOnWindowFocus: true` as a "fix" for the cache staleness gap:** This would mask the missing invalidation project-wide and defeat the deliberate 30s staleTime design decision (`frontend/src/lib/queryClient.ts:11`, chosen "to reduce noise for self-hosted deployments"). Fix the one missing `invalidateQueries` call instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-tab/cross-mutation cache freshness | A custom polling or manual-refresh button on Parts List | `queryClient.invalidateQueries` (already the project convention, 6 existing call sites) | Consistency; TanStack Query already owns this concern app-wide |
| Numeric ordering of a formatted string sequence | A Python-side full-table scan + sort | SQL-side `CAST(...AS INTEGER) ORDER BY ... DESC LIMIT 1` | Scales correctly with table growth; matches existing query-in-DB style (`func.max` was already DB-side, just wrong) |

**Key insight:** All three fixes should be the smallest possible diff that closes the gap the audit found — this phase's job is precision correction of already-diagnosed bugs, not redesign. Resist the temptation to refactor `add_avl_link`/`build_json_export`/`validate_import`/`commit_import` beyond the one-line import fix, or to change `generate_part_number`'s external contract (still returns `"P00001"`-style zero-padded 5-digit strings).

## Runtime State Inventory

This phase is a bug-fix/verification phase, not a rename/refactor/migration phase — the Runtime State Inventory trigger does not apply. Noting explicitly per protocol: no strings are being renamed, no data migration is needed, and the part-number fix changes *query logic* only, not the stored `part_number` VARCHAR values themselves (existing data such as `"P-DUPE-01"`, `"P99901"` is untouched).

One related runtime-state fact worth flagging to the planner: **the live dev environment currently has actual data past the part-number digit-width boundary** (the audit states "live-reproduced on the current instance, which has prototype data past the threshold"). This means the bug is not just theoretically reproducible — it will reproduce immediately on the current `compose_db_1` volume without needing synthetic seed data, and the fix must be verified against that existing data, not just fresh test rows.

## Common Pitfalls

### Pitfall 1: DB not reachable from host — but IS reachable from inside the API container
**What goes wrong:** Running `pytest` from the host machine's `backend/.venv` against default settings connects to `postgres_host: str = "db"` (`app/core/config.py:20`), which does not resolve outside the Podman compose network — `db_available()` will return `False` and all `skip_if_no_db` tests silently skip, giving false confidence that "tests pass" when they never ran.
**Why it happens:** `compose/compose.yml` deliberately does not publish the `db` service's port to the host (`T-01-12` — DB not exposed for security). The API container's `POSTGRES_HOST=db` env var is only valid inside the compose network.
**How to avoid:** Run the Wave-0 regression tests via `podman exec compose_api_1 pytest ...` (or an equivalent exec-into-container step) so `POSTGRES_HOST=db` resolves correctly, rather than `backend/.venv/bin/pytest` from the host. Confirmed in this research session: `compose_db_1` and `compose_api_1` are both currently running and healthy, alembic is at head (`0006`), so this path is available right now.
**Warning signs:** `31 passed, 94 skipped` in a test run (the exact figure reported in `06-05-SUMMARY.md`) — 94 skips is the `skip_if_no_db` count; if the fix's new regression tests land in that skip bucket, they were never actually exercised.

### Pitfall 2: Verifying only via unit tests, not the actual HTTP flow
**What goes wrong:** The audit notes that Wave-0 tests for exactly this bug (`test_avl.py::test_add_avl_link`, `test_import_export.py::test_import_preview_unknown_vendor`) already existed and were "written to catch this but are skip_if_no_db and were never run against a live database" — meaning a passing test suite alone did NOT catch this regression before it shipped.
**Why it happens:** Function-scoped `import` statements inside `add_avl_link()` etc. mean the `ImportError` only fires when the function actually executes, not at module import time / app startup — so `python -c "import app.main"` and even FastAPI's route registration succeed cleanly. Static analysis (mypy/ruff without type-checking imports inside function bodies at the right strictness) would not necessarily catch this either.
**How to avoid:** After the fix, run the specific tests against the live DB (Pitfall 1) AND perform the manual click-through (`checkpoint:human-verify`) for AVL add + import-with-vendor-refs — do not consider PLUM-07/PLUM-10 closed on unit-test-green alone, given this exact failure mode already slipped through unit tests once.
**Warning signs:** `docs/features/requirements-progress.md` marking a requirement "Complete" with only `test_avl.py` cited as evidence, when that test was never executed (this is precisely what happened in Phase 6 and must not repeat in Phase 7).

### Pitfall 3: Part-number fix breaking existing non-numeric part_number values
**What goes wrong:** A naive fix (`CAST(SUBSTRING(part_number,2) AS INTEGER)` on ALL rows matching `LIKE 'P%'`) will throw a Postgres cast error (`invalid input syntax for type integer`) the moment it hits a row like `"P-DUPE-01"` (confirmed to exist via `test_parts.py::test_create_duplicate_part_number`, which creates `"P-DUPE-01"` explicitly) — this is worse than the original bug (500 on every create, not just past a threshold).
**Why it happens:** `part_number` accepts arbitrary user-supplied strings (D-06 allows explicit override), not just auto-generated `P#####` values. The existing Python code handles this with `try/except (IndexError, ValueError): suffix = 0` but a naive SQL cast has no equivalent fallback.
**How to avoid:** Filter with a strict regex (`part_number.op("~")(r"^P[0-9]+$")`) BEFORE casting, so only well-formed auto-generated numbers participate in the MAX computation. Test explicitly against a DB row set containing both `"P-DUPE-01"`-style and `"P99999"`/`"P100000"`-style values (mirrors real seeded data).
**Warning signs:** Any Postgres `DataError: invalid input syntax for type integer` surfacing from `generate_part_number()`.

### Pitfall 4: Treating Phase-6 human-verify and Phase-7 human-verify as two separate checkpoints
**What goes wrong:** Planning two full manual UAT passes (one to "close out Phase 6" and a second "for Phase 7's own acceptance") wastes the user's time re-clicking through identical flows (AVL add, BOM tree, import/export) twice within the same session.
**Why it happens:** The phase title literally says "...verify Phase 6," and Phase 6's own plan (`06-05-PLAN.md`) has an unrun Task 4 checkpoint — it's tempting to treat these as two checklist items to satisfy mechanically.
**How to avoid:** Design Phase 7's human-verify checkpoint as a superset that satisfies both: the 8-item list already documented in `06-05-SUMMARY.md` (Known Stubs/Acceptance section, lines 130-138) PLUS the 3 Phase-7-specific regression checks (AVL no-500, import-with-vendor no-500, Parts List auto-refresh, part-number-past-boundary create). One checkpoint, one pass.

## Code Examples

### Exact bug locations (verified 2026-07-02)
```python
# Source: backend/app/modules/plum/service.py — grep-confirmed line numbers
# ALL 4 SITES use the identical broken import; ALL 4 need the identical fix.
# Line 1634 — inside add_avl_link()
# Line 2139 — inside build_json_export()
# Line 2607 — inside validate_import()
# Line 2740 — inside commit_import()
from app.modules.syerp.models import SyerpPartner  # BROKEN — class does not exist
```
```python
# Source: backend/app/modules/syerp/models.py:39 — the actual class
class Partner(Base):
    """... (dual-role entity, is_vendor / is_customer boolean role flags) ..."""
    id: Mapped[str] = mapped_column(...)      # line 55
    is_vendor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # line 63
```
`[VERIFIED: codebase read]`

### Existing generate_part_number() to be fixed
```python
# Source: backend/app/modules/plum/service.py:108-136 (current, broken)
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
`[VERIFIED: codebase read]` — the fix keeps the same function signature and return format (`P#####`, 5-digit zero-padded), only changes the query used to find `max_pn`.

## State of the Art

Not applicable in the usual "ecosystem moved on" sense — this is an internal bug fix, not a library/framework currency question. No deprecated APIs are involved; SQLAlchemy 2.0.51 and TanStack Query 5.101.1 are both current, already-pinned versions.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `cast(func.substring(PlumPart.part_number, 2), Integer)` combined with `.op("~")(r"^P[0-9]+$")` is valid, correct SQLAlchemy 2.0 Core syntax against Postgres 17 that produces the intended numeric ordering | Architecture Patterns, Pattern 2 | If the exact syntax is wrong (e.g. `func.substring` argument order, or the regex operator needs a different SQLAlchemy spelling), the executor will hit a SQL error immediately at test time — low actual risk since it's caught by Wave-0 tests before merge, but the plan should budget a `node_repair` cycle for this task rather than assuming first-try success |
| A2 | Running Wave-0 regression tests via `podman exec compose_api_1 pytest ...` is the correct way to get live-DB test execution in this environment, rather than some other mechanism (e.g. a test-specific compose profile) | Common Pitfalls, Pitfall 1 | If wrong, the planner might design a test task that silently skips again (repeating the exact Phase-6 failure mode) — moderate risk, should be explicitly confirmed by the executor at task start (`podman exec compose_api_1 alembic current` before running tests, mirroring what this research session did) |

**If this table is empty:** N/A — see above, 2 assumptions logged.

## Open Questions

1. **Should `06-VERIFICATION.md` be produced as a Phase-6 retroactive artifact, or should Phase 7 produce its own `07-VERIFICATION.md` covering both the gap-closure and the original Phase-6 success criteria?**
   - What we know: Phase 6 has zero `*-VERIFICATION.md` (confirmed: only phases 01-05 have one). The GSD verifier (`/gsd:verify-work`) is the tool that produces this artifact, not a hand-written executor task.
   - What's unclear: Whether the planner should schedule a `/gsd:verify-work 6` invocation, a `/gsd:verify-work 7` invocation, or both, and in what order relative to the human-verify checkpoint.
   - Recommendation: Plan Phase 7 to end with a single verification step that produces whichever artifact the GSD workflow naturally generates for "phase 7, which fixes and closes phase 6" — leave the exact artifact-naming mechanics to the planner's knowledge of the current GSD command surface rather than this research guessing at it.

2. **Does `docs/features/requirements-progress.md`'s evidence column need updating beyond the two false "Complete" rows (PLUM-07, PLUM-10)?**
   - What we know: PLUM-04/05/06/08/09 are also marked "Complete" in that file despite the audit calling them "partial (verification gap)" — no VERIFICATION.md, no human-verify run.
   - What's unclear: Whether Phase 7's scope (per its title) extends to formally re-verifying and correcting all 7 PLUM-04..10 rows, or only the 2 that were runtime-broken (07, 10) plus the numbering bug (01).
   - Recommendation: Given the phase title explicitly says "...verify Phase 6" (not just "fix PLUM-07/10"), treat the full PLUM-04..10 reconciliation as in-scope — the human-verify checkpoint (Pitfall 4 above) already covers exercising all 7 UI flows, so the marginal cost of also correcting the traceability doc for all 7 is low.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Podman + podman-compose | Running the live stack to verify fixes | ✓ | podman + podman-compose present | — |
| `compose_db_1` (Postgres) | DB-backed Wave-0 tests, live human-verify | ✓ (healthy, alembic head=0006) | postgres:17-alpine | — |
| `compose_api_1` (FastAPI) | Backend fixes, `pytest` execution via `podman exec` | ✓ (running) | — | — |
| `compose_frontend_1` (Vite dev) | Frontend fix, human-verify | ✓ (running, port 5174→5173) | node:22-slim | — |
| `backend/.venv` | Local tooling (ruff, mypy, IDE) | ✓ | pytest present | Use `podman exec compose_api_1` for anything requiring live DB (Pitfall 1) |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — full live stack is already up and migrated to head as of this research session (2026-07-02).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (backend, `asyncio_mode = "auto"`, `testpaths = ["tests"]` — `backend/pyproject.toml`); Vitest (frontend, `npm run test`) |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]`; frontend `package.json` `"test": "vitest"` |
| Quick run command | `podman exec compose_api_1 pytest tests/plum/test_avl.py tests/plum/test_import_export.py tests/plum/test_parts.py -x` |
| Full suite command | `podman exec compose_api_1 pytest` (backend); `cd frontend && npm run test` (frontend, no live DB needed) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLUM-07 | AVL link add no longer 500s | integration (live DB) | `podman exec compose_api_1 pytest tests/plum/test_avl.py::test_add_avl_link -x` | ✅ (test file exists, was never run against live DB) |
| PLUM-10 | Import preview/commit with vendor refs no longer 500s | integration (live DB) | `podman exec compose_api_1 pytest tests/plum/test_import_export.py::test_import_preview_unknown_vendor -x` | ✅ (exists, never run live) |
| PLUM-10 | Export with AVL rows present no longer 500s | integration (live DB) | `podman exec compose_api_1 pytest tests/plum/test_import_export.py::test_export_json -x` | ✅ (exists — should also assert AVL rows are present in the fixture, verify during planning) |
| PLUM-01 | Part-number generator returns correct next value past a digit-width boundary | unit/integration (live DB) | new test, e.g. `tests/plum/test_parts.py::test_generate_part_number_digit_boundary` | ❌ Wave 0 — needs to be written |
| PLUM-10 (cache) | Parts List reflects import commit without manual refresh | manual (human-verify) — not practically automatable without a query-client test harness not currently present in the project | — | N/A — cover via human-verify checkpoint |

### Sampling Rate
- **Per task commit:** targeted test file for the touched code (e.g. `test_avl.py` after Task A, `test_parts.py` after Task B)
- **Per wave merge:** `podman exec compose_api_1 pytest tests/plum/` (full PLUM suite) + `cd frontend && npm run test`
- **Phase gate:** full backend suite (`podman exec compose_api_1 pytest`) green with 0 unexpected skips on the 3 newly-relevant test files, before human-verify checkpoint

### Wave 0 Gaps
- [ ] `tests/plum/test_parts.py::test_generate_part_number_digit_boundary` (or similar) — seed rows `"P99999"` and `"P100000"` directly (bypassing the generator), call `generate_part_number()`, assert the returned value is `"P100001"` and is not a duplicate of any existing row. This is the one net-new test this phase needs; everything else re-runs existing tests that were written but never executed against a live DB.
- [ ] Confirm `test_export_json` (or add a new case) seeds at least one `PlumAvlLink` row so the export path actually exercises the broken `SyerpPartner` code path at line 2139 — re-read the fixture during planning to confirm AVL data is present, since the audit's evidence for this call site was a live click-through, not necessarily an existing automated test.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Not touched by these fixes — existing RBAC (`require_permission`) already gates the AVL/import endpoints per Phase 4/5/6 work; unchanged |
| V3 Session Management | No | Not touched |
| V4 Access Control | No | Unchanged — the fix is inside already-permission-gated service functions |
| V5 Input Validation | Yes (incidentally) | The part-number regex filter (`^P[0-9]+$`) is itself an input-validation-adjacent safeguard against malformed cast input — use parameterized SQLAlchemy constructs (`.op("~")` with a Python string literal, never raw string interpolation) to avoid SQL injection in the regex pattern itself, though the pattern here is a fixed literal, not user input, so injection risk is effectively nil |
| V6 Cryptography | No | Not touched |

### Known Threat Patterns for this stack (fixes-specific, not new surface)

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Regressing a previously-fixed vulnerability while doing a "minimal diff" fix (e.g. accidentally widening the AVL vendor lookup to include non-vendor Partners) | Tampering / Elevation of Privilege | Keep `SyerpPartner.is_vendor == True` filter intact at all 4 sites — the fix must be import-only, not touch the `WHERE` clause logic, per `T-06-07` already documented in the `add_avl_link` docstring |
| DoS via a crafted `part_number` regex input | Denial of Service | N/A here — the regex pattern is a fixed literal (`r"^P[0-9]+$"`), not derived from request input, so no ReDoS surface is introduced |

This phase does not introduce new attack surface — it is closing runtime-availability bugs (500s), not adding new endpoints or altering the trust boundary. `security_enforcement` gate is satisfied trivially: confirm during code review that the fix diffs touch only the import statement (Fix 1) and the query construction (Fix 2), not the existing permission/validation logic around them.

## Sources

### Primary (HIGH confidence)
- Direct codebase reads (this research session, 2026-07-02): `backend/app/modules/plum/service.py` (lines 108-136, 1610-1660, 2120-2160, 2595-2650, 2730-2775), `backend/app/modules/syerp/models.py` (lines 1-70), `backend/app/modules/plum/models.py` (part_number column def), `backend/alembic/versions/0005_plum_tables.py` (unique constraint/index confirmation), `frontend/src/routes/plum/ImportExport.tsx` (full file), `frontend/src/lib/queryClient.ts`, `backend/tests/conftest.py`, `backend/tests/plum/test_avl.py`, `test_import_export.py`, `test_parts.py`, `test_bom.py` (grep for existing test names)
- Live environment probes (this session): `podman ps`, `podman exec compose_api_1 alembic current`/`alembic heads` (confirmed head=0006), `podman inspect compose_api_1` (env vars), `pip show sqlalchemy openpyxl` in `backend/.venv`
- `.planning/v1.0-MILESTONE-AUDIT.md` (2026-07-01) — the authoritative root-cause diagnosis this research verified against source
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` — project requirement definitions and Phase 6 plan/decision history
- `.planning/phases/06-plum-bom-costing-integration/06-05-SUMMARY.md` — the pending human-verify checklist this phase must incorporate

### Secondary (MEDIUM confidence)
- SQLAlchemy 2.0 `cast`/`func.substring`/Postgres `~` operator syntax (Pattern 2) — based on training knowledge of SQLAlchemy Core, cross-checked against the fact that SQLAlchemy 2.0.51 is confirmed installed and `func`/`select` are already imported in the target file, but not independently verified via Context7 or official docs in this session (Context7/WebSearch were not available/used — this is training-data knowledge). Flagged in Assumptions Log (A1).

### Tertiary (LOW confidence)
- None used as load-bearing claims.

## Metadata

**Confidence breakdown:**
- Bug diagnosis (all 3): HIGH — independently re-verified against live source code and a live running environment, not just the audit's word
- Fix approach for Fix 1 (import alias) and Fix 3 (cache invalidation): HIGH — both are copy-of-existing-pattern fixes already proven correct elsewhere in the same codebase
- Fix approach for Fix 2 (numeric ordering): MEDIUM — syntax is standard SQLAlchemy/Postgres but not verified via official docs in this session; budget a Wave-0 test iteration
- Verification/testing environment (live DB reachability, alembic state): HIGH — directly probed in this session, not assumed

**Research date:** 2026-07-02
**Valid until:** Effectively indefinite for the bug diagnoses (they are fixed facts about the current code); ~7 days for the "live environment currently running and at head" claims, since the dev stack could be restarted/rebuilt/torn down between now and plan execution — the planner/executor should re-confirm `podman ps` and `alembic current` at execution time rather than trusting this snapshot.
