---
phase: 06-plum-bom-costing-integration
plan: 05
subsystem: plum
tags: [bom, avl, costing, import-export, react, typescript, shadcn, tailwind, plum]
dependency_graph:
  requires: ["06-02", "06-03", "06-04"]
  provides: []
  affects:
    - frontend/src/routes/plum/PartDetail.tsx
    - frontend/src/routes/plum/ImportExport.tsx
    - frontend/src/routes/plum/ImportExport.test.tsx
    - frontend/src/routes/plum/components/PlumNav.tsx
    - frontend/src/App.tsx
    - docs/features/requirements-progress.md
tech_stack:
  added: []
  patterns:
    - Four-card PartDetail extension pattern: section cards appended after revision history
    - saveCostMutation modeled on advanceMutation (PATCH /revisions/{revId}/cost)
    - isDraft gating pattern: Add Part + inline edit form hidden on Released revisions
    - D-14 dual-cost surface: frozenCostDisplay + liveCostDisplay on Released revision
    - D-07 effective-cost source label rendered inline ("vendor price" / "manual" / "roll-up" / "uncosted")
    - Select-for-costing: CheckCircle/Circle toggle per price-break row (Draft only)
    - AVL expandable rows: local Set<string> state for per-link expand/collapse
    - Blob download idiom: createObjectURL + anchor click + revokeObjectURL
    - FormData upload idiom: multipart/form-data POST for /import/preview and /import/commit
    - 3-step import flow: useState<'upload'|'preview'|'committed'> with inline step transitions
    - Confirm Import disabled when errors > 0 (T-06-24)
key_files:
  modified:
    - frontend/src/routes/plum/PartDetail.tsx
    - frontend/src/routes/plum/components/PlumNav.tsx
    - frontend/src/App.tsx
  created:
    - frontend/src/routes/plum/ImportExport.tsx
    - frontend/src/routes/plum/ImportExport.test.tsx
    - docs/features/requirements-progress.md
decisions:
  - "node_modules symlinked from main repo into worktree frontend/ — worktree shares packages; tsc run via symlinked node_modules. Symlink not committed (Rule 3 auto-fix)."
  - "BomLineRead uses qty/ref_des not quantity/reference_designators — existingLine mapping translated BomTreeNode fields to BomLineSheet prop type."
  - "requirements-progress.md created new (file did not exist in repo) — seeded with PLUM-01..03 (Phase 5) and PLUM-04..10 (Phase 6)."
  - "Task 4 (human-verify checkpoint) is pending human verification — no code written; executor halts here per checkpoint protocol."
metrics:
  duration: "~45 min"
  completed: "2026-07-01"
  tasks_completed: 3
  files_modified: 6
---

# Phase 6 Plan 05: PLUM Frontend Integration Summary

Extended PartDetail with four Phase-6 section cards (BOM, AVL, Cost & Margin, Where-Used), built the Import/Export page with 3-step import flow, added the PlumNav tab and App.tsx route, created requirements-progress.md marking PLUM-04..10 complete, and ran full frontend + backend suites. Task 4 (human-verify checkpoint) is pending user confirmation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | PartDetail — four section cards (BOM, AVL, Cost & Margin, Where-Used) | bad4dbe | `PartDetail.tsx` (+860 lines) |
| 2 | ImportExport page + PlumNav tab + App.tsx route + smoke test | e157a07 | `ImportExport.tsx`, `ImportExport.test.tsx`, `PlumNav.tsx`, `App.tsx` |
| 3 | Update requirements-progress.md; full frontend + backend suites | 970186e | `docs/features/requirements-progress.md` |
| 4 | Human-verify checkpoint (PENDING) | — | No code — pending human verification |

## What Was Built

### PartDetail.tsx Extensions (Task 1)

**Section 1 — Bill of Materials card (PLUM-04/05):**
- `<BomTree>` component wired with `partId`, `revisionId`, `isDraft`, `onEdit`, `onRemove` callbacks
- "Add Part" button visible only when `currentRevision.status === 'draft'` (D-01 immutability)
- Inline remove confirmation in card body: "Remove {part}?" / "Yes, Remove" (destructive) / "Keep {part}" (ghost) — no modal dialog
- `BomLineSheet` wired for create/edit with correct `qty`/`ref_des` field mapping to `BomLineRead`
- Remove via `DELETE /api/v1/plum/parts/{partId}/bom/{lineId}` + invalidate + toast "BOM line removed."

**Section 2 — Approved Vendor List card (PLUM-07):**
- Expandable vendor rows via local `Set<string>` state keyed by link ID
- Preferred badge: `bg-blue-50 text-blue-700` with `title="Preferred vendor"`
- Price-break sub-table with Select-for-Costing CheckCircle (green) / Circle toggle (Draft only)
- `selectForCostingMutation`: PATCH cost endpoint with `selected_vendor_link_id` + `selected_price_break_index`
- D-14 dual-cost notice on Released revision: "Released at: $X · Current would be $Y" in amber
- Remove vendor link via `Dialog` with "Keep Link" / "Remove Link" (destructive) pattern
- `AvlLinkSheet` wired for create/edit modes

**Section 3 — Cost & Margin card (PLUM-08/09):**
- Two-column cost grid: Material Cost, BOM Roll-up Cost, Effective Cost (with source label), Sale Price, Margin, Margin %
- D-07: both entered cost AND roll-up cost always surfaced (per spec)
- D-14: Released revision shows frozen "Released at" + current live cost with amber divergence notice
- Inline edit form (Draft only, always visible): Material Cost + Sale Price inputs + "Save Costs" button
- `saveCostMutation` targets `PATCH /api/v1/plum/parts/{partId}/revisions/{revId}/cost`, toasts "Costs saved."
- Negative margin: `text-destructive font-semibold` on Margin row and Margin % row
- Margin summary box rendered when both salePrice and effectiveCost are available
- Currency suffix (`USD`) from `locale.currency` Setting

**Section 4 — Where Used card (PLUM-06):**
- Flat `<ul aria-label="Where used">` list sorted: direct parents first, then indirect
- "Direct parent" / "Indirect via {part}" labels per entry
- >20 results notice per UI-SPEC
- Empty state: "This part is not used in any assembly."

### ImportExport.tsx (Task 2, PLUM-10)

**Export Card:**
- "Export as JSON" → `GET /api/v1/plum/export/json` with `responseType: 'blob'` + `createObjectURL` download
- "Export as Excel" → `GET /api/v1/plum/export/excel` + download as `.xlsx`
- Loader2 during export; toast "Export started — your download will begin shortly."

**Import Card — 3-step flow:**
- Step 1: dashed dropzone + hidden file input (`accept=".json,.xlsx"`) + selected filename display with X clear + "Upload and Preview" (disabled until file selected)
- Step 2: summary banner (new/updated/error counts), scrollable error table (`aria-label="Import validation errors"`), "Confirm Import" disabled when errors > 0 (T-06-24), "Back to Upload" ghost
- Step 3: CheckCircle (green), "Import complete", inserted/updated counts, "No records were deleted.", "Import Another File" reset
- Stateless re-parse: client sends file again on commit (same file ref from `useState<File>`)

### ImportExport.test.tsx (Task 2)

3 Vitest smoke tests (all pass): upload zone + both export buttons present.

### PlumNav.tsx + App.tsx (Task 2)

- PlumNav TABS: `{ to: '/plum/import-export', label: 'Import / Export' }`
- App.tsx: `<Route path="/plum/import-export" element={<ImportExport />} />`

### requirements-progress.md (Task 3)

Created `docs/features/requirements-progress.md` with PLUM-01..10 all marked Complete.

## Task 4 Status: PENDING HUMAN VERIFICATION

Task 4 is a `checkpoint:human-verify gate="blocking"` — no code written. The executor halts here.

The user must run the stack and verify the seven ROADMAP success criteria (see how-to-verify in PLAN.md):
1. BOM card — Add Part → child appears in tree; expand/collapse works
2. BOM card — Flat view → shared sub-assembly shows ONE row with summed Total Qty + Total BOM Cost footer
3. Where Used card → parent assemblies appear, labeled Direct / Indirect
4. AVL card — Add Vendor → link persists; mark Preferred
5. Cost & Margin — enter Material Cost, Save → Effective Cost shows "manual"; roll-up source on assembly; vendor price on select-for-costing
6. Sale Price → Margin and Margin % render; below-cost sale price shows margin in red
7. Import/Export → JSON + Excel downloads; re-import JSON → 0 errors → Confirm Import → success state; data not deleted; >10 MB rejected
8. Released revision: BOM and cost read-only (no Add Part, no edit form, frozen "Released at" cost shown)

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| `tsc --noEmit` passes (Tasks 1 + 2) | PASS (zero errors) |
| PartDetail contains "Bill of Materials" | PASS (3 occurrences) |
| PartDetail contains "Approved Vendor List" | PASS (3 occurrences) |
| PartDetail contains "Cost & Margin" | PASS (5 occurrences) |
| PartDetail contains "Where Used" | PASS (3 occurrences) |
| saveCostMutation targets /revisions/{revId}/cost, toasts "Costs saved." | PASS |
| "Add Part" gated on isDraft | PASS |
| Inline edit form gated on isDraft | PASS |
| PlumNav includes 'import-export' entry | PASS |
| App.tsx registers /plum/import-export route | PASS |
| ImportExport.tsx contains "Upload and Preview" | PASS |
| ImportExport.tsx contains "Confirm Import" | PASS |
| ImportExport.tsx contains "Export as JSON" | PASS |
| ImportExport.tsx contains "Export as Excel" | PASS |
| ImportExport.test.tsx — 3 smoke tests | PASS (3/3) |
| Full frontend suite (8 test files) | PASS (21/21 tests) |
| Full backend suite | PASS (31 passed, 94 skipped — clean) |
| PLUM-10 in requirements-progress.md | PASS |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] node_modules not present in worktree frontend/**
- **Found during:** Task 1 (tsc --noEmit would fail without node_modules)
- **Issue:** The worktree has no `node_modules/` — it shares the main project's packages but they are not symlinked automatically
- **Fix:** Created `frontend/node_modules -> /home/zack/Projects/BizNiceSweets/frontend/node_modules` symlink; also created `backend/.venv -> /home/zack/Projects/BizNiceSweets/backend/.venv` symlink for pytest
- **No files committed** (symlinks are runtime-only, not tracked by git)

**2. [Rule 1 - Bug] BomLineRead uses `qty`/`ref_des` not `quantity`/`reference_designators`**
- **Found during:** Task 1 (IDE diagnostic + tsc verification)
- **Issue:** BomTreeNode uses `quantity` and `reference_designators` but BomLineSheet's `BomLineRead` type uses `qty` and `ref_des`
- **Fix:** Correct field names used in existingLine mapping

**3. [Rule 2 - Missing Critical Functionality] requirements-progress.md did not exist**
- **Found during:** Task 3
- **Issue:** File did not exist in repo; plan said to mirror existing PLUM-01..03 rows
- **Fix:** Created file from scratch, seeding PLUM-01..03 from Phase 5 and adding PLUM-04..10 for Phase 6

## Known Stubs

None. All implemented surfaces are wired to real API calls (BomTree, AVL, cost, where-used, export, import).

## Threat Flags

No new threat surface beyond the plan's threat model. All four T-06-21 through T-06-24 mitigations implemented.

## Self-Check: PASSED

Files exist:
- `frontend/src/routes/plum/PartDetail.tsx` — FOUND (extended, +860 lines)
- `frontend/src/routes/plum/ImportExport.tsx` — FOUND (created)
- `frontend/src/routes/plum/ImportExport.test.tsx` — FOUND (created, 3/3 tests pass)
- `frontend/src/routes/plum/components/PlumNav.tsx` — FOUND (extended)
- `frontend/src/App.tsx` — FOUND (extended)
- `docs/features/requirements-progress.md` — FOUND (created)

Commits:
- `bad4dbe` feat(06-05): extend PartDetail with four Phase-6 section cards — FOUND
- `e157a07` feat(06-05): add ImportExport page, PlumNav tab, App route, and smoke test — FOUND
- `970186e` docs(06-05): create requirements-progress.md marking PLUM-04 through PLUM-10 complete — FOUND
