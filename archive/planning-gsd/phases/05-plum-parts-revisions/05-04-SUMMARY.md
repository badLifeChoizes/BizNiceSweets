---
phase: 05-plum-parts-revisions
plan: "04"
subsystem: frontend
tags:
  - plum
  - react
  - tanstack-query
  - shadcn
  - part-detail
  - revision-workflow
  - dialogs
dependency_graph:
  requires:
    - 05-02 (PLUM service + router: advance/supersede FSM endpoints)
    - 05-03 (PLUM Parts List UI: PartRead interface, PartSheet, PlumNav, PartsList route)
  provides:
    - PartDetail route (/plum/parts/:id): header card, advance-status strip, revision timeline
    - NewRevisionDialog: clone-from Select, required reason textarea, POSTs to /revisions
    - AdvanceStatusDialog: release confirmation, warns about auto-obsolete, aria-label
    - RevisionRead TypeScript interface (exported from NewRevisionDialog.tsx)
    - App.tsx PLUM route wiring: /plum redirect, /plum/parts PartsList, /plum/parts/:id PartDetail
  affects:
    - End-to-end PLUM lifecycle (human-verify checkpoint — Task 3)
tech_stack:
  added: []
  patterns:
    - RevisionStatusBadge inline component with STATUS_BADGE_CLASSES Record<string,string>
    - Revision timeline <ol aria-label="Revision history"> with connector line + status dot
    - getCurrentRevision() helper — highest revision_number that is not obsolete
    - getDiffFromPrior() helper — field-level diff between two RevisionRead objects for the "Changed from prior" line
    - advanceMutation with per-targetStatus toast routing (in_review vs draft branch)
    - AdvanceStatusDialog conditionally rendered only when currentRevision.status === 'in_review' (avoids stale props when status changes)
key_files:
  created:
    - frontend/src/routes/plum/PartDetail.tsx
    - frontend/src/routes/plum/components/NewRevisionDialog.tsx
    - frontend/src/routes/plum/components/AdvanceStatusDialog.tsx
  modified:
    - frontend/src/App.tsx
decisions:
  - RevisionRead interface exported from NewRevisionDialog.tsx — PartDetail imports from there (avoids a separate types file; follows the PartRead-in-PartSheet pattern from 05-03)
  - AdvanceStatusDialog rendered conditionally inside PartDetail only when currentRevision.status === 'in_review' — prevents stale revision prop after status changes; simpler than passing null and guarding inside the dialog
  - getCurrentRevision helper uses highest revision_number among non-obsolete revisions — avoids timestamp ordering edge cases; matches the MAX-based approach used in the backend service
  - getDiffFromPrior computes diff only on the four revision-controlled fields (description, category, unit_of_measure, notes) — reason_for_revision is excluded because it is per-revision metadata, not an attribute snapshot
  - Advance-status strip renders a "Reject to Draft" ghost button (in_review only) and "Release" default button (opens AdvanceStatusDialog) — mirrors UI-SPEC exactly with no additional confirmation for the reject path (reversible/low-stakes)
metrics:
  duration: ~3min
  completed: "2026-06-29"
  tasks: 2
  files: 4
---

# Phase 05 Plan 04: PartDetail + Dialogs + App.tsx Wiring Summary

**One-liner:** Part Detail route with header card, revision timeline (newest-first with connector dots, snapshot dl, field diff), advance-status strip (Draft/InReview only), NewRevisionDialog (clone-from selector + required reason), AdvanceStatusDialog (release confirmation with auto-obsolete warning), and all PLUM routes wired into App.tsx.

---

## What Was Built

### Task 1 — NewRevisionDialog + AdvanceStatusDialog (`5435887`)

**frontend/src/routes/plum/components/NewRevisionDialog.tsx**
- Exports `RevisionRead` TypeScript interface (single source of truth for revision shape)
- Props: `open`, `partId`, `revisions: RevisionRead[]`, `onClose`
- `getDefaultSourceRevision()` helper — prefers latest Released revision, fallback to latest overall
- Clone-from `<Select>` listing all revisions by label + status; resets to default on open via `useEffect`
- Required "Reason for revision" `<textarea>` with validation toast
- `createRevisionMutation` POSTs to `/api/v1/plum/parts/${partId}/revisions` with `{ source_revision_id, reason_for_revision }`
- `onSuccess`: invalidates `['plum','parts',partId]`, toasts "New revision {label} created."
- `onError`: `getApiErrorMessage` helper surfacing FastAPI string/422-array detail
- Accessibility: `aria-labelledby="new-rev-dialog-title"` + `aria-describedby="new-rev-dialog-description"` (Contract 8)

**frontend/src/routes/plum/components/AdvanceStatusDialog.tsx**
- Props: `open`, `partId`, `revision: RevisionRead`, `priorReleasedLabel?: string`, `onClose`
- DialogTitle: "Release revision {revision.revision_label}?"
- DialogDescription: conditionally includes prior revision label or omits it when no prior released exists
- `releaseMutation` POSTs `{ target_status: 'released' }` to `/api/v1/plum/parts/${partId}/revisions/${revision.id}/advance`
- `onSuccess`: invalidates `['plum','parts',partId]`, toasts "Revision {label} released. Prior revision obsoleted."
- Release button: `variant="default"` (NOT destructive — confirmed by UI-SPEC), `aria-label="Release revision {label}"` (Contract 7)
- Accessibility: `aria-labelledby` + `aria-describedby` (Contract 8)

### Task 2 — PartDetail route + App.tsx wiring (`011308e`)

**frontend/src/routes/plum/PartDetail.tsx**

Part header `<Card>`:
- `CardHeader`: part_number (`text-xl font-semibold`) + current revision description (`text-base text-muted-foreground`)
- Header actions: "Edit Part" (outline, opens PartSheet in edit mode) + "New Revision" (default, opens NewRevisionDialog)
- `CardContent` 2-column grid: classification tags as `<Badge variant="secondary">` pills, current revision label + RevisionStatusBadge, created/updated timestamps

Advance-status strip (only when `currentRevision.status === 'draft' || 'in_review'`):
- Draft: "Submit for Review" button (variant="default") → advances target `in_review`, toast "Submitted for review."
- In Review: "Reject to Draft" (ghost) + "Release" (default, aria-label) → opens AdvanceStatusDialog
- Advance calls use `advanceMutation` POSTing to `/revisions/{id}/advance`
- Toast copy matches Copywriting Contract exactly

Revision History `<ol aria-label="Revision history" className="space-y-0">`:
- Revisions listed newest-first (API returns revision_number DESC)
- Each `<li>` has a connector column (2px vertical `bg-border` line, omitted above first / below last) and an 8px status-colored dot
- Row content: label (`font-medium text-sm`) + `RevisionStatusBadge` + date (released/obsoleted/created)
- Snapshot attributes as inline `<dl>` (description always shown, category/UOM/notes conditionally)
- Reason for revision as `italic text-muted-foreground`
- "Changed from prior: {field list}" diff line on non-last items (only fields that changed)

`RevisionStatusBadge` inline component with `STATUS_BADGE_CLASSES` map:
- draft: `bg-gray-100 text-gray-600`
- in_review: `bg-yellow-50 text-yellow-700`
- released: `bg-green-50 text-green-600`
- obsolete: `bg-gray-100 text-gray-400`

**frontend/src/App.tsx** (modified):
```tsx
// PLUM module routes — Sidebar nav lands on /plum → redirect to parts list
<Route path="/plum" element={<Navigate to="/plum/parts" replace />} />
<Route path="/plum/parts" element={<PartsList />} />
<Route path="/plum/parts/:id" element={<PartDetail />} />
```

---

## Verification Results

```
# Artifact content checks:
grep "Create New Revision" NewRevisionDialog.tsx     OK
grep "Release revision" AdvanceStatusDialog.tsx      OK
grep "/plum/parts/:id" App.tsx                       OK
grep "Revision History" PartDetail.tsx               OK

# TypeScript:
cd frontend && npx tsc --noEmit                      CLEAN (no errors)

# Smoke tests:
cd frontend && npx vitest run src/routes/plum/
  Test Files  1 passed (1)
       Tests  2 passed (2)                           OK

# Key acceptance criteria:
useQuery key ['plum','parts',partId]                 OK (PartDetail.tsx)
GET /api/v1/plum/parts/${partId}                     OK
advanceMutation POSTs to /revisions/${id}/advance    OK
AdvanceStatusDialog aria-label on Release button     OK
aria-labelledby + aria-describedby in both dialogs   OK
RevisionRead exported from NewRevisionDialog.tsx     OK
STATUS_BADGE_CLASSES matches UI-SPEC color map       OK
No dangerouslySetInnerHTML anywhere                  OK (T-05-12 mitigated)
```

---

## Deviations from Plan

None — plan executed exactly as written.

### Implementation Notes (non-deviations)

1. **RevisionRead exported from NewRevisionDialog.tsx** — The plan said "RevisionRead interface from 05-01 schemas." PartDetail.tsx imports it from `./components/NewRevisionDialog` (where it is defined for the dialog's own use), rather than defining it a second time. AdvanceStatusDialog.tsx imports it from the same location. This single-source pattern mirrors the PartRead-in-PartSheet decision from 05-03.

2. **AdvanceStatusDialog rendered conditionally** — The dialog is only mounted when `currentRevision.status === 'in_review'`. This ensures the `revision` prop is always a valid InReview revision (the dialog's required contract) and prevents stale data after a status change. When the status changes to released or draft, the dialog unmounts cleanly.

3. **Diff line skipped for the last (oldest) revision** — The plan says "no diff on first revision." In a newest-first list, the first item in the array is the newest revision, so `isLast` (oldest revision) has no prior to compare against. The diff is computed as `getDiffFromPrior(rev, revisions[index+1])` which is undefined for `isLast` — matches intent exactly.

---

## Known Stubs

None — all routes resolve to real backend data. The only known stub from 05-03 (description column showing "—" in the list) is resolved in 05-04: PartDetail calls `GET /plum/parts/{id}` which includes the full description via the first revision's snapshot.

---

## Threat Flags

No new threat surface beyond what is in the plan's `<threat_model>`. Mitigations implemented:
- T-05-12: No `dangerouslySetInnerHTML` in PartDetail, NewRevisionDialog, or AdvanceStatusDialog — all user-supplied content (description, notes, reason_for_revision) rendered via JSX interpolation (React auto-escape)
- T-05-14: AdvanceStatusDialog forces explicit confirmation before the irreversible release action; the supersede + audit happen server-side (05-02, T-05-08)

---

## Self-Check

### Files exist:
- `/home/zack/Projects/BizNiceSweets/frontend/src/routes/plum/PartDetail.tsx` — FOUND
- `/home/zack/Projects/BizNiceSweets/frontend/src/routes/plum/components/NewRevisionDialog.tsx` — FOUND
- `/home/zack/Projects/BizNiceSweets/frontend/src/routes/plum/components/AdvanceStatusDialog.tsx` — FOUND
- `/home/zack/Projects/BizNiceSweets/frontend/src/App.tsx` — FOUND (modified)

### Commits exist:
- `5435887` — Task 1: NewRevisionDialog + AdvanceStatusDialog
- `011308e` — Task 2: PartDetail route + App.tsx wiring

## Self-Check: PASSED
