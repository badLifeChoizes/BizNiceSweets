# Plan: 07 — Close v1.0 gaps
Goal: PLUM AVL and vendor import/export work end-to-end with no runtime 500s, auto part-numbering is numerically correct, the Parts List auto-refreshes after import, and Phase 6's PLUM flows are human-verified with traceability reconciled — the last phase before v1.0 closes.
Status: draft
Branch: `bugfix-plum-v1-gaps` (branch off `chore-architecture-planning` per D-P7-3 — master lacks the code; per-branch checklist at `docs/tasks/bugfix-plum-v1-gaps.md`)

> This plan is a clean ZJ translation of the four adopted GSD plans (`archive/planning-gsd/phases/07-close-v1-0-gaps-fix-plum-syerp-partner-import-plum-07-10-par/07-01..04-PLAN.md`) per DECISION D-ADOPT-2 — the fixes are **not** re-derived. Line numbers below were re-verified in the live code on 2026-07-04.

## Success criteria
- **SC1** — `POST /api/v1/plum/parts/{id}/avl` and every vendor-referencing import/export path return 2xx (not HTTP 500 `ImportError`) for a valid `is_vendor` Partner. (PLUM-07, PLUM-10)
- **SC2** — `generate_part_number()` returns the numeric successor past the 5→6-digit boundary, never collides with an existing row, never integer-casts a non-numeric `part_number` (e.g. `"P-DUPE-01"`), and still returns `"P00001"` on an empty table. (PLUM-01 defect)
- **SC3** — After a successful import commit, the Parts List reflects imported data with no manual refresh. (PLUM-10 cache gap)
- **SC4** — Fixes are proven by live-DB automated tests that actually RUN against Postgres (not silently skipped), plus one consolidated human-verify pass covering 7 PLUM flows (PLUM-04..10) + 4 regression checks.
- **SC5** — Traceability is reconciled to verified reality: `.zj/SRD.md` and `docs/features/requirements-progress.md` mark PLUM-04..10 Complete only where 07-03 verified them; no requirement is Complete on the basis of a test that never ran. (CORE-01/CORE-09 checkbox reconciliation)
- **SC6** — Root `/home/zack/Projects/BizNiceSweets/CLAUDE.md` "Technology Stack" and "Architecture" sections describe the live FastAPI/React codebase, not the legacy vanilla-JS prototypes. (owner decision this session)

## Context

**Confirmed code sites (verified 2026-07-04):**
- `backend/app/modules/plum/service.py` — 4 broken function-local imports `from app.modules.syerp.models import SyerpPartner` at lines **1634** (`add_avl_link`), **2139** (`build_json_export`), **2607** (`validate_import`), **2740** (`commit_import`). Real class is `Partner` (`backend/app/modules/syerp/models.py:39`). Fix = alias `Partner as SyerpPartner` at each site.
- `backend/app/modules/plum/service.py:66` — `from sqlalchemy import func, or_, select` → widen to add `Integer, cast`.
- `backend/app/modules/plum/service.py:108` — `generate_part_number()`.
- `frontend/src/routes/plum/ImportExport.tsx` — line 30 imports only `useMutation`; `commitImportMutation` at line 164, its `onSuccess` at line 175. Working analog: `frontend/src/routes/plum/components/ArchivePartDialog.tsx` (import line 16, hook setup 41-42, onSuccess invalidation 49-53).
- Tests: `backend/tests/plum/{test_avl,test_import_export,test_parts}.py`. Reconciliation docs: `.zj/SRD.md`, `docs/features/requirements-progress.md`.

**Patterns to follow (from 07-PATTERNS.md — do not invent new ones):**
- Aliased function-local import (keep circular-import-avoiding local imports; do NOT hoist to module top; do NOT touch `syerp/models.py`; keep every `is_vendor` WHERE filter verbatim — T-06-07).
- Numeric-safe sequence: filter `part_number.op("~")(r"^P[0-9]+$")` BEFORE the cast, `order_by(cast(func.substring(PlumPart.part_number, 2), Integer).desc()).limit(1)`; keep the signature, the `return "P00001"` empty branch, the `try/except (IndexError, ValueError)` fallback, and the `f"P{suffix + 1:05d}"` format.
- Cache invalidation: `void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })` in `commitImportMutation.onSuccess` ONLY (not export/preview mutations); do NOT change `frontend/src/lib/queryClient.ts` staleTime.

**Environment (critical — the Podman stack is currently DOWN):**
- Live-DB tests MUST run inside the API container (`podman exec <api> pytest ...`); host `pytest` silently skips `skip_if_no_db` (Pitfall 1 — the exact failure that let these bugs ship). Warning sign of a silent skip: a large "skipped" count.
- Discover the container name at runtime — do NOT hardcode `compose_api_1` (Linux podman-compose may name it `compose-api-1`, `compose_api_1`, or a project-prefixed variant):
  `API=$(podman ps --format '{{.Names}}' | grep -E 'api' | head -1)`
- Bring the stack up: `pwsh scripts/uat.ps1` if `pwsh` is available, else `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`.
- Confirm schema before trusting any test: `podman exec "$API" alembic current` must report **0006**.
- Frontend verify target is the **Vite dev server at http://localhost:5173 only** (owner decision) — no `frontend/dist` / image rebuild task (the stale :8000 bundle is a separate backlog item).

**Prior decisions baked in:** D-ADOPT-2 (adopt GSD plans as-is), owner decisions this session (verify at :5173 only; add the CLAUDE.md refresh task; keep scope to the 4 plans + that one task; no CI — stays backlog).

## Decisions needed
None. Scope is fully adopted (D-ADOPT-2) and the two open owner decisions (:5173 verify target, CLAUDE.md refresh) are already resolved and baked into Tasks 4 and 6. If any Wave-1 verify surfaces that the Pattern-2 SQLAlchemy syntax (Assumption A1) needs adjustment, that is a normal repair cycle within Task 2, not a user decision.

## Tasks

### Wave 1 — the three independent code fixes (+ standalone CLAUDE.md refresh)

> Tasks 1 and 2 touch the SAME file (`service.py`) — sequence them (1 then 2), do NOT parallelize. Task 3 (frontend) and Task 4 (docs) are independent of everything in Wave 1. Wave-1 backend verifies require the stack up; if it is down, bring it up first via the Context procedure (formalized in Wave 2 Task 5).

### [x] 1. Alias Partner as SyerpPartner at all 4 sites + cover every vendor code path live
- **Serves:** SC1 · **FRs:** PLUM-07, PLUM-10, PLUM-08 (transitive)
- **Files:** `backend/app/modules/plum/service.py`, `backend/tests/plum/test_import_export.py`
- **Do:**
  - At each of the 4 function-local imports (service.py lines **1634, 2139, 2607, 2740**), replace `from app.modules.syerp.models import SyerpPartner` with `from app.modules.syerp.models import Partner as SyerpPartner`. Alias-only — touch no other line, do NOT hoist to module top, do NOT alter the `SyerpPartner.is_vendor == True` / `.is_vendor.is_(True)` WHERE filters, do NOT edit `backend/app/modules/syerp/models.py`.
  - Close the export/commit coverage gap in `test_import_export.py`: ensure at least one test seeds a `PlumAvlLink` row before hitting the JSON export (so `build_json_export` at 2139 runs its vendor lookup instead of the empty-`vendor_ids` short-circuit), and an import-commit case includes a valid existing vendor `code` in its `avl_links` payload (so `commit_import` at 2740 runs). Follow the file's existing fixture/seed style (`create_access_token`, `client`, API POST to seed). Sites 1634/2607 are already covered by `test_avl.py::test_add_avl_link` and `test_import_export.py::test_import_preview_unknown_vendor`.
- **Done when:**
  - `grep -c "Partner as SyerpPartner" backend/app/modules/plum/service.py` == 4; `grep -c "import SyerpPartner$" backend/app/modules/plum/service.py` == 0.
  - `git diff` shows `backend/app/modules/syerp/models.py` unchanged; `is_vendor` still present at all 4 sites.
  - `test_import_export.py` has a test that seeds a `PlumAvlLink` row before the JSON export, and a commit case with a valid vendor `code`.
  - The AVL and import/export live-DB tests exit 0 (not 500, not skipped).
- **Verify:** `API=$(podman ps --format '{{.Names}}' | grep -E 'api' | head -1); podman exec "$API" alembic current && podman exec "$API" pytest tests/plum/test_avl.py tests/plum/test_import_export.py -x -q`
- **Parallel-ok:** no (shares `service.py` with Task 2)

### [x] 2. Numeric-safe generate_part_number + digit-boundary regression test
- **Serves:** SC2 · **FRs:** PLUM-01 (defect)
- **Files:** `backend/app/modules/plum/service.py`, `backend/tests/plum/test_parts.py`
- **Do:**
  - Widen `service.py:66` to `from sqlalchemy import Integer, cast, func, or_, select`.
  - Rewrite only the SELECT inside `generate_part_number()` (line 108) to: `select(PlumPart.part_number).where(PlumPart.part_number.op("~")(r"^P[0-9]+$")).order_by(cast(func.substring(PlumPart.part_number, 2), Integer).desc()).limit(1)`, then `max_pn = result.scalar()`. The regex filter MUST precede the cast (Pitfall 3 — a bare cast over `LIKE 'P%'` throws on `"P-DUPE-01"`). Keep the signature `async def generate_part_number(db: AsyncSession) -> str`, the `if max_pn is None: return "P00001"` branch, the `try/except (IndexError, ValueError): suffix = 0` fallback, and the `f"P{suffix + 1:05d}"` return unchanged. The regex is a fixed literal (no injection/ReDoS surface).
  - Add `test_generate_part_number_digit_boundary` to `test_parts.py` (conventions: `skip_if_no_db`, `create_access_token(subject="admin-user", permissions=["plum:write"])`, `client`). Seed `"P99999"` and `"P100000"` via explicit-`part_number` POSTs, then POST a part with no `part_number`. Because the shared dev DB already holds rows past this boundary, assert robustly (not a hardcoded string): result matches `^P[0-9]+$`, its numeric suffix is strictly greater than every pre-existing `^P[0-9]+$` row's suffix (== true numeric MAX + 1), and it equals no existing row's `part_number`. Add an inline comment referencing the shared-DB caveat and the PLUM-01 defect.
- **Done when:**
  - `grep -c "from sqlalchemy import Integer, cast, func, or_, select" backend/app/modules/plum/service.py` == 1.
  - `generate_part_number` contains both `op("~")(r"^P[0-9]+$")` and `cast(func.substring`, still returns via `f"P{suffix + 1:05d}"`, still has the `return "P00001"` branch.
  - `test_parts.py` defines `test_generate_part_number_digit_boundary`, which RUNS (not skipped) and passes; existing part tests (incl. `test_create_duplicate_part_number` with `"P-DUPE-01"`) still pass with no cast error.
- **Verify:** `API=$(podman ps --format '{{.Names}}' | grep -E 'api' | head -1); podman exec "$API" pytest tests/plum/test_parts.py -x -q`
- **Parallel-ok:** no (shares `service.py` with Task 1; run after Task 1)

### [x] 3. Invalidate ['plum','parts'] on import commit success
- **Serves:** SC3 · **FRs:** PLUM-10 (cache gap)
- **Files:** `frontend/src/routes/plum/ImportExport.tsx`
- **Do:** Three edits matching the `ArchivePartDialog.tsx` analog verbatim: (1) widen line 30 to `import { useMutation, useQueryClient } from '@tanstack/react-query'`; (2) add `const queryClient = useQueryClient()` near the top of the `ImportExport()` body (~line 103, alongside existing useState/useRef); (3) inside `commitImportMutation`'s `onSuccess` (~line 175), after the existing `setCommittedData` / `setImportStep('committed')` / `toast(...)`, add `void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })`. Apply to `commitImportMutation` ONLY — not `exportJsonMutation`, `exportExcelMutation`, or `uploadPreviewMutation`. Do NOT change `frontend/src/lib/queryClient.ts` staleTime.
- **Done when:**
  - `grep -c "useQueryClient" frontend/src/routes/plum/ImportExport.tsx` >= 2; `grep -c "invalidateQueries" frontend/src/routes/plum/ImportExport.tsx` == 1, inside `commitImportMutation.onSuccess`.
  - `git diff` shows `frontend/src/lib/queryClient.ts` unchanged.
  - `npx tsc --noEmit` exits 0; existing ImportExport smoke tests pass.
- **Verify:** `cd frontend && npx tsc --noEmit && npm run test -- --run ImportExport`
- **Parallel-ok:** yes

### [x] 4. Refresh CLAUDE.md Technology Stack + Architecture to describe the live stack
- **Serves:** SC6 · **FRs:** none (owner decision — clearly outside the adopted 4-plan fix scope)
- **Files:** `/home/zack/Projects/BizNiceSweets/CLAUDE.md` (Technology Stack section starts line **43**; Architecture section starts line **146**)
- **Do:** Rewrite the "Technology Stack" and "Architecture" sections so they describe the LIVE codebase — FastAPI + SQLAlchemy 2.0 + PostgreSQL 17 backend (`backend/`), React 19 + TypeScript + Vite + Tailwind + shadcn/ui frontend (`frontend/`), Podman/podman-compose deployment, modular monolith over one shared Postgres DB with SYERP as hub — instead of the frozen vanilla-JS prototypes (which currently claim "No server-side runtime", "None — no npm", localStorage persistence). Point at `.zj/codebase/MAP.md` as the authoritative source of the current map/stack/commands. Keep the existing stale-section warning banner's spirit: note the legacy prototype details still apply only when reading `plum/app/` or `flan/app/`. Do NOT expand into CI (backlog). Do NOT touch the "Conventions", "Project Skills", or "Project-Specific Rules" sections.
- **Done when:** The Technology Stack and Architecture sections name FastAPI/SQLAlchemy/PostgreSQL and React 19/Vite/Tailwind, reference `backend/` and `frontend/`, cite `.zj/codebase/MAP.md`, and no longer present the vanilla-JS/localStorage/no-server description as the live reality; legacy-only caveats are scoped to `plum/app/` & `flan/app/`.
- **Verify:** `grep -nE "FastAPI|SQLAlchemy|React 19|Vite|codebase/MAP.md" CLAUDE.md` returns hits in both sections; `grep -n "No server-side runtime" CLAUDE.md` no longer appears as an unqualified live claim.
- **Parallel-ok:** yes

### Wave 2 — bring stack up, run full live-DB PLUM suite, then blocking human-verify

### [x] 5. Bring the Podman stack up, confirm the API container name, run the full live-DB PLUM suite
- **Serves:** SC4 · **FRs:** PLUM-01, PLUM-07, PLUM-08, PLUM-10
- **Files:** none (verification task)
- **Do:**
  - Bring the stack up: `pwsh scripts/uat.ps1` if `pwsh` is present, else `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`.
  - Discover and RECORD the actual container name: `podman ps --format '{{.Names}}'` (do NOT assume `compose_api_1`). Confirm db, api, and frontend containers are all running.
  - Confirm schema: `podman exec "$API" alembic current` reports **0006** — do NOT trust any test result until this passes (guards the Pitfall-1 silent-skip).
  - Run the full PLUM suite inside the container and inspect the skip count: `podman exec "$API" pytest tests/plum/ -q`. A large "skipped" number means the DB was not reachable (silent skip) — treat that as a FAIL, not a pass.
- **Done when:** Stack is up; the API container name is recorded; `alembic current` == 0006; `pytest tests/plum/` is green with 0 unexpected skips on `test_avl.py`, `test_import_export.py`, `test_parts.py` (the fix + new-test paths actually executed).
- **Verify:** `API=$(podman ps --format '{{.Names}}' | grep -E 'api' | head -1); podman exec "$API" alembic current && podman exec "$API" pytest tests/plum/ -q`
- **Parallel-ok:** no (gates Task 6; depends on Wave 1)

### [x] 6. Consolidated human-verify — 7 PLUM flows + 4 regression checks (deferred to milestone, D-P7-5)
- **Serves:** SC4 · **FRs:** PLUM-04, PLUM-05, PLUM-06, PLUM-07, PLUM-08, PLUM-09, PLUM-10
- **Files:** none (records outcome for Wave 3 to consume; the build PAUSES here for the user)
- **Do:** Precondition — the stack is up (Task 5), `alembic current` == 0006, and the **Vite dev server is reachable at http://localhost:5173** (owner-chosen target). Open :5173, log in as admin, and have the user exercise the 12 checks below, recording pass/fail + notes per flow. This single pass supersedes the never-run Phase-6 `06-05` Task 4 checkpoint (do NOT schedule a second manual pass — Pitfall 4). Any failure routes to a gap-closure re-plan; do NOT proceed to Wave 3 on a failed flow.

  Phase-6 success criteria (PLUM-04..09):
  1. BOM card (Draft revision) — Add Part → child appears in the tree; expand/collapse works. (PLUM-04)
  2. BOM flat view — a shared sub-assembly appears as ONE row with summed Total Qty and a Total BOM Cost footer. (PLUM-05)
  3. Where-Used card — parent assemblies appear, labeled "Direct parent" / "Indirect via {part}". (PLUM-06)
  4. AVL card — Add Vendor → select a SYERP vendor → link PERSISTS after refresh; mark Preferred shows the badge. (PLUM-07)
  5. Cost & Margin — enter Material Cost, Save → Effective Cost source "manual"; on an assembly source "roll-up"; select-for-costing on an AVL price break → source "vendor price". (PLUM-08)
  6. Sale Price → Margin and Margin % render; a below-cost sale price shows the margin in **red**. (PLUM-09)
  7. Import/Export — Export JSON and Export Excel both download; re-import the JSON → preview 0 errors → Confirm → success ("No records were deleted"); a >10 MB file is rejected. (PLUM-10)
  8. Released revision — BOM and cost are read-only (no Add Part, no cost edit form); frozen "Released at" cost shown. (PLUM-03/06 immutability)

  Phase-7 regression checks:
  9. AVL add (check 4) completes with NO 500 / error toast. (SC1)
  10. Import containing a vendor reference (check 7) previews and commits with NO 500. (SC1)
  11. After Confirm Import, the Parts List reflects imported/updated rows WITHOUT a manual page refresh. (SC3)
  12. Create a NEW part with auto-numbering (no part_number entered) on this instance (which has data past the P99999→P100000 boundary) → succeeds with a fresh unique `P#####`, NO duplicate-key error. (SC2)
- **Done when:** All 8 Phase-6 criteria observed working (or each failure recorded with specifics), and regression checks 9–12 explicitly confirmed. Per-flow outcome recorded for Wave 3.
- **Verify:** Manual — user types "approved" if all pass, or lists failing flow(s) with observations. Precondition self-check: `podman ps` shows the frontend container up and http://localhost:5173 loads.
- **Parallel-ok:** no (blocking; depends on Task 5)

### Wave 3 — traceability reconciliation (gated on the human-verify outcome)

### [x] 7. Reconcile .zj/SRD.md and requirements-progress.md against verified reality
- **Serves:** SC5 · **FRs:** PLUM-04..10 (status), CORE-01, CORE-09 (checkbox reconciliation)
- **Files:** `.zj/SRD.md`, `docs/features/requirements-progress.md`
- **Do:** Gate every status change on the Task 6 outcome. In `.zj/SRD.md`: for each PLUM-04..10 flow Task 6 recorded as PASSED, update its `**Status:**` from `partial (...)` to `implemented` (PLUM-07 → drop "broken at runtime"; PLUM-10 → drop "vendor path broken"; PLUM-01 → drop "(defect open)"); leave any FAILED flow at `partial` and do not mark it implemented. Update the traceability/counts footer (currently "PLUM-04..10 pending Phase-7 fixes/verify", counts dated 2026-07-04) to reflect the verified set. Confirm CORE-01 and CORE-09 read `implemented` (they passed Phase 1 and are only checkbox-lagged). In `docs/features/requirements-progress.md`: correct the evidence column so no PLUM-04..10 row claims Complete on an unrun test — cite the Phase-7 live-DB test results (Tasks 1–2, run via Task 5) and the Task 6 human-verify pass as evidence. Do NOT edit `CHANGELOG.md` (generated).
- **Done when:**
  - `.zj/SRD.md` marks PLUM-04..10 `implemented` only where Task 6 passed; PLUM-01/07/10 no longer carry defect/broken qualifiers if verified; CORE-01/CORE-09 are `implemented`; the counts/footer reflect the new reality.
  - `docs/features/requirements-progress.md` PLUM-07 and PLUM-10 evidence cites the Phase-7 fix/live-test + human-verify, not a previously-false "Complete".
  - `git diff CHANGELOG.md` is empty.
- **Verify:** `grep -nE "PLUM-0[4-9]|PLUM-10" .zj/SRD.md` shows `implemented` for verified reqs and no stale "broken"/"pending Phase-7" wording; `git diff --quiet CHANGELOG.md && echo "changelog untouched"`.
- **Parallel-ok:** no (depends on Task 6)

## Deviations
- **Branch base (material, owner-approved D-P7-3):** plan said branch off `master`; actually branched off `chore-architecture-planning` because master (2025-12-20) predates the re-platform and has no `backend/`/`frontend/`/`.zj/`. See DECISIONS.md D-P7-3.
- **Live-DB test harness deferred / SC4 relaxed (material, owner-approved D-P7-4):** the `skip_if_no_db` PLUM suite has never run (broken probe; once fixed, 33/33 fail on async-engine loop mismatch + no seeding + no isolation — BACKLOG.md p1). Owner deferred the repair. **SC4's "pytest tests/plum/ green" is superseded** — Tasks 1/2/5 are verified instead by (a) standalone async scripts against live Postgres and (b) the Task 6 human-verify at :5173 (regression checks 9–12). The new/updated tests are still committed so they pass once the harness is repaired. See DECISIONS.md D-P7-4.
- **Human-UAT moved to milestone / Task 6 unblocked (material, owner-approved D-P7-5):** rather than block Phase 7 on a full 12-flow manual pass, human-UAT becomes a `/zj:milestone` activity (bisectable commits make regressions cheap to localize). Checks 1 (BOM add on Draft) & 8 (Released read-only) ran and **passed**; checks 2–7 & 9–12 are captured as TODO in `.zj/UAT-v1.0.md`. Task 7 reconciles traceability to this — code fixes on proven evidence, UI flows annotated "UAT deferred to v1.0 milestone", nothing marked Complete on an unrun check (SC5 preserved). See DECISIONS.md D-P7-5.

## Noticed (unrelated to Phase 7 scope — for triage)
- **Frontend `npm run lint` is broken:** ESLint v10 requires a flat `eslint.config.js`, which the
  project lacks → lint errors out ("couldn't find eslint.config.(js|mjs|cjs)"). Frontend lint has
  effectively not been running. Discovered at Phase-7 wrap-up; unrelated to the fixes. Candidate
  BACKLOG item.
- **`ruff` absent from the API image:** backend lint can't run in-container (same stale-image /
  missing-dev-deps class as the pytest harness gap, BACKLOG p1). Backend ruff lint not run this
  phase.
- **Dev-DB data artifact:** part `P-COMMIT-AVL-1` (from an import-commit test) has no non-obsolete
  revision, so its PartDetail renders without the BOM card. Harmless data hygiene, not a code bug.

## Risks
- **Pattern-2 SQLAlchemy syntax (Assumption A1, MEDIUM):** `cast(func.substring(...), Integer)` + `.op("~")` may need a spelling tweak against Postgres 17. Early-warning: a SQL error at Task 2's verify. Mitigation: budget one repair cycle inside Task 2 — caught before merge by the live-DB test.
- **Silent-skip recurrence (Pitfall 1):** running tests from the host, or against a container at schema 0005, produces false green. Early-warning: a large "skipped" count or `alembic current` != 0006 in Task 5. Mitigation: Task 5 gates on both explicitly.
- **Container name drift:** GSD hardcoded `compose_api_1`; Linux podman-compose may differ. Early-warning: `podman exec compose_api_1 ...` errors "no such container". Mitigation: every verify discovers the name via `podman ps` (Context snippet).
- **Human-verify uncovers a Phase-6 logic gap (not just the 3 fixed bugs):** a PLUM-04/05/06/09 flow fails in the UI. Early-warning: Task 6 flow marked fail. Mitigation: that flow stays `partial` in Task 7 and routes to a new gap-closure phase — it does not block marking the verified flows Complete.
- **Stale :8000 bundle confusion:** verifying against the served bundle instead of :5173 would test old frontend code. Mitigation: Task 6 precondition pins :5173 (owner decision); dist rebuild is out of scope.

## Out of scope
- Rebuilding `frontend/dist` / the container image so the served :8000 bundle picks up the cache-invalidation fix (separate backlog item; verify at :5173 only).
- CI / automated pipeline for live-DB tests (stays backlog per owner decision).
- Any change to `backend/app/modules/syerp/models.py` (the `Partner` class is correct), hoisting the function-local imports, altering `is_vendor` filters, or changing `queryClient.ts` staleTime.
- A separate `/gsd:verify-work 6` retroactive pass — the Task 6 consolidated checkpoint supersedes it (Pitfall 4).
- New features, refactors of `add_avl_link`/`build_json_export`/`validate_import`/`commit_import` beyond the one-line alias, or any schema migration (none required).
- Editing `CHANGELOG.md` (generated from commits).
