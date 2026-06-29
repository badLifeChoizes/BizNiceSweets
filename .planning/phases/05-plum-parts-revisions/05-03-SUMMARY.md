---
phase: 05-plum-parts-revisions
plan: "03"
subsystem: frontend
tags:
  - plum
  - react
  - tanstack-query
  - shadcn
  - parts-list
dependency_graph:
  requires:
    - 05-02 (PLUM service + router: /api/v1/plum/parts endpoints live)
  provides:
    - PartsList screen (/plum/parts) with toolbar, table, empty/error states
    - PlumNav tab strip (PLUM sections nav)
    - PartSheet create/edit sheet with auto-prefilled part number, tag picker
    - ArchivePartDialog destructive confirmation dialog
    - Wave 0 frontend smoke test (2 tests passing)
    - Shared PartRead TypeScript interface (exported from PartSheet.tsx)
  affects:
    - 05-04 (PLUM part detail UI — will wire App.tsx routes and import PartsList)
tech_stack:
  added: []
  patterns:
    - PartRead interface exported from PartSheet.tsx (single source of truth, mirrors PartnerRead-in-PartnerSheet decision)
    - Status badge color map as Record<string,string> constant (draft/in_review/released/obsolete)
    - Debounced search via useRef + setTimeout (300ms, same pattern as Vendors.tsx)
    - useEffect form population with direct apiClient call for part number prefill (no TanStack Query for one-shot prefill)
    - Hardcoded seeded tag vocabulary in PartSheet (IDs 1-6 from seed.py; no GET /tags endpoint exists)
key_files:
  created:
    - frontend/src/routes/plum/PartsList.tsx
    - frontend/src/routes/plum/PartsList.test.tsx
    - frontend/src/routes/plum/components/PlumNav.tsx
    - frontend/src/routes/plum/components/PartSheet.tsx
    - frontend/src/routes/plum/components/ArchivePartDialog.tsx
  modified: []
decisions:
  - PartRead TypeScript interface exported from PartSheet.tsx — single source of truth consumed by PartsList and ArchivePartDialog (mirrors the PartnerRead-in-PartnerSheet decision from Phase 4, 04-03)
  - Tag vocabulary hardcoded in PartSheet (IDs 1-6 per seed.py) — no GET /tags endpoint exists; avoids an extra network request for static data
  - Description column shows "—" in PartsList table — PartRead list response does not include description (it is a revision-controlled field on PlumPartRevision, not on PlumPart); Part Detail (05-04) will show the full description from GET /plum/parts/{id}
  - Part number prefill uses direct apiClient call in useEffect (not useQuery) — one-shot fetch on sheet open, not a persistent cache entry
metrics:
  duration: ~20min
  completed: "2026-06-28"
  tasks: 2
  files: 5
---

# Phase 05 Plan 03: PLUM Parts List UI Summary

**One-liner:** PLUM Parts List screen with debounced search, status filter, archived toggle, PartSheet create/edit, ArchivePartDialog, PlumNav tab strip, and Wave 0 smoke tests — all consuming the 05-02 API.

---

## What Was Built

### Task 1 — PlumNav + ArchivePartDialog + PartSheet (`f2d988d`)

**frontend/src/routes/plum/components/PlumNav.tsx** — Tab strip mirroring SyerpNav:
- Single "Parts" tab with NavLink to `/plum/parts`
- `aria-label="PLUM sections"` (accessibility contract)
- Code comment reserving Phase 6 BOMs tab slot
- Active tab: `border-primary text-foreground border-b-2 -mb-px`

**frontend/src/routes/plum/components/ArchivePartDialog.tsx** — Destructive confirmation:
- Props: `{ open, part: PartRead | null, onClose }`
- `archiveMutation` PATCHes `/api/v1/plum/parts/${id}` with `{ active: false }`
- On success: invalidates `['plum','parts']`, toasts "Part archived."
- DialogTitle "Archive part?", DialogDescription using `part.part_number`
- Footer: "Keep Part" (outline) + "Archive Part" (destructive, `aria-label="Archive {part_number}"`)
- `<Loader2>` while archiving; `aria-labelledby` + `aria-describedby` accessibility

**frontend/src/routes/plum/components/PartSheet.tsx** — Create/edit sheet:
- Exports `PartRead` interface (single source of truth for PLUM part entity)
- Copies `getApiErrorMessage` verbatim from PartnerSheet.tsx
- Three Separator-divided sections:
  1. Identity: Part Number (auto-prefilled via `GET /api/v1/plum/parts/next-number` on create open), Description (required)
  2. Classification: Checkbox group over 6 seeded tags (IDs 1-6), writing `tag_ids: number[]`
  3. Revision seed (create mode only): "Reason for first revision" textarea, optional
- `createMutation` POSTs `/api/v1/plum/parts`; `updateMutation` PATCHes `/api/v1/plum/parts/{id}`
- Both mutations invalidate `['plum','parts']` and toast "Part created." / "Part saved."

### Task 2 — PartsList screen + Wave 0 smoke test (`38335e3`)

**frontend/src/routes/plum/PartsList.tsx** — Parts list screen:
- `fetchParts(q, status, includeArchived)` builds URLSearchParams and GETs `/api/v1/plum/parts`
- Debounced search (300ms useRef pattern, identical to Vendors.tsx)
- useQuery key `['plum','parts',{ q: searchFilter, status: statusFilter, includeArchived }]`
- Page wrapper `p-8 space-y-6` with PlumNav, h1 "Parts", subtitle
- Toolbar: search Input (`max-w-xs`), status `<Select>` (All Statuses | Draft | In Review | Released | Obsolete), Show-archived `<Switch>`+`<Label>`, Create Part `<Button variant="default" className="ml-auto">`
- Table: Part Number (`font-medium`), Description (—, see Known Stubs), Tags (comma-joined), Current Revision, Status (badge), Actions
- Row `onClick={() => navigate(\`/plum/parts/${part.id}\`)}` with `e.stopPropagation()` on Actions cell
- `RestoreMutation` PATCHes `{ active: true }`, toasts "Part restored."
- Three empty states (no parts / search active / status filter active) and error state per Copywriting Contract
- `STATUS_BADGE_CLASSES` map: draft gray, in_review yellow, released green, obsolete gray

**frontend/src/routes/plum/PartsList.test.tsx** — Wave 0 smoke tests:
- Mocks `@/api/client` (apiClient.get/post/patch)
- Renders PartsList inside QueryClientProvider + MemoryRouter
- Test 1: asserts "Parts" heading and "Create Part" button present
- Test 2: asserts "No parts yet" empty state when API returns `[]`
- 2 tests, 0 failures

---

## Verification Results

```
# Artifact checks:
export interface PartRead in PartSheet.tsx          OK
aria-label="PLUM sections" in PlumNav.tsx           OK
Archive part? in ArchivePartDialog.tsx              OK

# TypeScript:
cd frontend && npx tsc --noEmit                     CLEAN (no errors)

# Smoke tests:
cd frontend && npx vitest run src/routes/plum/PartsList.test.tsx
  Test Files  1 passed (1)
       Tests  2 passed (2)            OK

# Key acceptance criteria:
PartsList GETs /api/v1/plum/parts                   OK
queryKey ['plum','parts',...] present                OK
navigate(`/plum/parts/${part.id}`) row click         OK
Status badge color map (4 states)                   OK
No dangerouslySetInnerHTML anywhere                  OK
```

---

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Implementation Notes (non-deviations)

1. **Tag vocabulary hardcoded** — The plan specified "checkbox group over seeded tag vocabulary." No `GET /plum/tags` endpoint exists (not in the 05-02 API surface). Tags are hardcoded in PartSheet as `TAG_VOCABULARY` with IDs 1-6 matching `seed.py`. This avoids an extra network request for static data. When the vocabulary becomes user-editable (planned in a future phase), a tags endpoint can be added and the hardcoded list replaced.

2. **Part number prefill uses `apiClient` directly in `useEffect`** — The prefill is a one-shot fetch on sheet open, not a persistent cache entry worth adding to TanStack Query's cache. This matches the PartnerSheet.tsx pattern of using the settings query for a similar one-time form initialization.

3. **Description column shows "—" in the table** — `PartRead` (the list endpoint response) does not include `description` because description is a revision-controlled field on `PlumPartRevision`, not on `PlumPart`. The list API returns `current_revision_label` and `current_revision_status` but not `description`. The Part Detail screen (05-04) will show the full description from `GET /plum/parts/{id}`. This is a known intentional stub (see Known Stubs below).

---

## Known Stubs

| Stub | File | Notes |
|------|------|-------|
| Description column always "—" | `frontend/src/routes/plum/PartsList.tsx` line ~253 | `PartRead` list response does not carry `description` (revision-controlled field). 05-04 PartDetail shows it. Not a blocker for plan goal (list-level management surface). |
| Edit mode description field empty | `frontend/src/routes/plum/components/PartSheet.tsx` line ~139 | Edit sheet clears description because the list `PartRead` doesn't carry the current revision's description. A follow-on or 05-04 can fetch `GET /plum/parts/{id}` to pre-populate. |

---

## Threat Flags

No new threat surface beyond what is in the plan's `<threat_model>`. Mitigations implemented:
- T-05-10: React JSX auto-escapes all interpolated values — no `dangerouslySetInnerHTML` anywhere in the new components
- T-05-11: `includeArchived` defaults `false`; archived parts hidden by default; Show-archived Switch is explicit opt-in

---

## Self-Check

### Files exist:
- `/home/zack/Projects/BizNiceSweets/frontend/src/routes/plum/PartsList.tsx` — FOUND
- `/home/zack/Projects/BizNiceSweets/frontend/src/routes/plum/PartsList.test.tsx` — FOUND
- `/home/zack/Projects/BizNiceSweets/frontend/src/routes/plum/components/PlumNav.tsx` — FOUND
- `/home/zack/Projects/BizNiceSweets/frontend/src/routes/plum/components/PartSheet.tsx` — FOUND
- `/home/zack/Projects/BizNiceSweets/frontend/src/routes/plum/components/ArchivePartDialog.tsx` — FOUND

### Commits exist:
- `f2d988d` — Task 1: PlumNav + ArchivePartDialog + PartSheet
- `38335e3` — Task 2: PartsList screen + Wave 0 smoke tests

## Self-Check: PASSED
