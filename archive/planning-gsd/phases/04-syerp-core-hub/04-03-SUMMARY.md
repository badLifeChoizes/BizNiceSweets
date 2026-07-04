---
phase: 04-syerp-core-hub
plan: "03"
subsystem: frontend/syerp
tags: [react, tanstack-query, shadcn, partners, vendors, customers, forms]
dependency_graph:
  requires: ["04-02"]
  provides: ["04-04"]
  affects: ["frontend/src/routes/syerp/"]
tech_stack:
  added: []
  patterns:
    - TanStack Query useQuery with role-scoped cache keys
    - useMutation with role-scoped invalidateQueries on success
    - 300ms debounced server-side search (not client-side filter)
    - shadcn Sheet (side=right) for create/edit form
    - shadcn Dialog (destructive) for archive confirmation
    - sonner toast for save/archive/restore feedback
key_files:
  created:
    - frontend/src/routes/syerp/components/PartnerSheet.tsx
    - frontend/src/routes/syerp/components/PartnerArchiveDialog.tsx
    - frontend/src/routes/syerp/Vendors.tsx
    - frontend/src/routes/syerp/Customers.tsx
    - frontend/src/routes/syerp/Vendors.test.tsx
    - frontend/src/routes/syerp/Customers.test.tsx
  modified: []
decisions:
  - "PartnerSheet exports PartnerRead type so sibling components (Vendors, Customers, PartnerArchiveDialog) share a single canonical type definition without duplication"
  - "Currency Select defaults to 'USD' on initial render; corrects to settings default_currency on first cache hit — avoids flicker on controlled Select"
  - "formCurrency uses empty string guard — only sends currency to API when user has explicitly chosen one or settings default loaded"
metrics:
  duration: "312s (~5min)"
  completed_date: "2026-06-27"
  tasks_completed: 2
  files_created: 6
  files_modified: 0
---

# Phase 4 Plan 03: SYERP Partner UI — Vendors, Customers, PartnerSheet Summary

**One-liner:** React Vendor/Customer list screens with server-side debounced search, Show-archived toggle, archive/restore actions, and a shared 4-section PartnerSheet form with role validation and settings-seeded currency default.

---

## Objective Achieved

Built the SYERP frontend partner management layer: two list screens (Vendors, Customers) that fetch role-filtered, server-side-searched partner data, and a shared form+dialog layer (PartnerSheet, PartnerArchiveDialog) that handles create/edit/archive mutations with auditable PATCH semantics.

---

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Shared PartnerSheet + PartnerArchiveDialog | f539a85 | components/PartnerSheet.tsx, components/PartnerArchiveDialog.tsx |
| 2 | Vendors/Customers list screens + Wave 0 tests | 96c31a5 | Vendors.tsx, Customers.tsx, Vendors.test.tsx, Customers.test.tsx |

---

## Implementation Notes

### PartnerSheet (Task 1)

- Four `<Separator>`-divided sections: Identity, Address, Contact, Commerce.
- All fields per UI-SPEC with exact placeholders.
- Role validation: both switches off → inline `<p className="text-sm text-destructive">At least one role must be selected.</p>` + Save disabled.
- On create, pre-checks the Switch matching the `role` prop (vendor → is_vendor=true, customer → is_customer=true).
- Currency default: reads `locale.currency` from `['core','settings']` TanStack Query cache (5-min staleTime for AppShell cache hit); falls back to `'USD'`.
- Mutations: POST create / PATCH edit; both invalidate `['syerp','partners',role]` and toast per the Copywriting Contract.
- Accessibility: every input has `htmlFor`/`id` pairing; Sheet has `aria-labelledby` + `aria-describedby`.

### PartnerArchiveDialog (Task 1)

- Destructive `<Dialog>` with role-parameterized copy (Archive vendor? / Archive customer?).
- Confirm fires PATCH `{active: false}`, invalidates role-scoped query key, toasts per Copywriting Contract.
- `aria-label="Archive {partner.name}"` on confirm button; `aria-labelledby` + `aria-describedby` on DialogContent.

### Vendors / Customers screens (Task 2)

- Query key `['syerp', 'partners', 'vendor'|'customer', { q, includeArchived }]` for granular cache scoping.
- `fetchVendors`/`fetchCustomers`: constructs `?role=vendor|customer&q=...&include_archived=true|false` — no client-side filter.
- 300ms debounce: `searchValue` (controlled input) vs `searchFilter` (triggers re-fetch) — exact pattern from Users.tsx.
- Show archived: `<Switch>` + `<Label>` paired; `includeArchived` state drives the query param.
- Empty states: two variants — no-records ("No vendors yet") and no-match ("No vendors found") — copy exact to UI-SPEC Copywriting Contract.
- Error state: API failure message per UI-SPEC.
- Restore: direct PATCH `{active:true}` with sonner toast, no confirmation dialog (D-05 spec).
- StatusBadge: color + text (Active/Archived), never color alone.

### Wave 0 Tests (Task 2)

- `Vendors.test.tsx` + `Customers.test.tsx`: mirror `Users.test.tsx` mock pattern.
- Assertions: heading renders, Create button present, empty state text appears after API resolves.
- Both tests green: 2/2 passed.

---

## Verification Results

- `npm test -- --run src/routes/syerp/Vendors.test.tsx src/routes/syerp/Customers.test.tsx` — **2 passed**
- `npx tsc --noEmit` — **clean** (no errors in any syerp files)
- Search hits server via `?q=` param; no client-side `.filter()` call present in Vendors.tsx or Customers.tsx.

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Known Stubs

None. All data is fetched from real API endpoints. Currency Select defaults to `'USD'` as a controlled-input initialization value before the settings cache resolves; this is per-spec behavior (fallback to USD), not a stub.

---

## Self-Check: PASSED

Files created:
- `frontend/src/routes/syerp/components/PartnerSheet.tsx` — exists (commit f539a85)
- `frontend/src/routes/syerp/components/PartnerArchiveDialog.tsx` — exists (commit f539a85)
- `frontend/src/routes/syerp/Vendors.tsx` — exists (commit 96c31a5)
- `frontend/src/routes/syerp/Customers.tsx` — exists (commit 96c31a5)
- `frontend/src/routes/syerp/Vendors.test.tsx` — exists (commit 96c31a5)
- `frontend/src/routes/syerp/Customers.test.tsx` — exists (commit 96c31a5)
