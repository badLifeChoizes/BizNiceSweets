---
status: partial
phase: 05-plum-parts-revisions
source: [05-VERIFICATION.md, 05-04-PLAN.md]
started: "2026-06-29"
updated: "2026-06-29"
---

# Phase 05 — Human Verification (PLUM Parts & Revisions)

All automated gates passed (build green, backend 31 pass / 77 skip, frontend 16 pass, schema-drift clean, regression clean, goal verifier 4/5 code-verified). The remaining gate is the manual lifecycle walkthrough from the 05-04 human-verify checkpoint.

**How to run:** live Postgres required (the revision lifecycle needs a real DB). Prod `:8000` serves a stale `dist`, so use the Vite dev server (`:5173`) + backend. Sign in as admin.

## Current Test

[awaiting human testing]

## Tests

### 1. PLUM nav landing
expected: Opening PLUM from the sidebar lands on `/plum/parts` (the Parts list).
result: [pending]

### 2. Create part
expected: Create Part → Part Number auto-prefilled and editable; add description + optional tags; save → part appears in the list with current revision "A" (ASME) or "0.1.0" (SemVer) and status Draft.
result: [pending]

### 3. Search and filter
expected: Search box filters by part number/description after ~300ms; Status select filters by current-revision status; "Show archived" toggle works.
result: [pending]

### 4. Navigate to detail
expected: Clicking a part row navigates to `/plum/parts/{id}` showing the header card and a revision timeline with one Draft revision.
result: [pending]

### 5. Advance Draft → In Review → Released
expected: Submit for Review (Draft→In Review), then Release → confirmation dialog appears; after confirming, the revision shows Released.
result: [pending]

### 6. Create new revision (copy-forward)
expected: New Revision → pick source, enter reason, create → a new Draft revision appears at the top of the timeline copying prior attributes.
result: [pending]

### 7. Supersede-on-release
expected: Advance the new revision to Released → the previously released revision becomes Obsolete; exactly one revision shows Released.
result: [pending]

### 8. Revision history visibility
expected: Timeline shows all revisions newest-first with correct status badges and snapshot attributes.
result: [pending]

### 9. Archive / restore
expected: Archive a part from row actions → toggle Show archived → it reappears → Restore works.
result: [pending]

### 10. Released immutability (server-enforced)
expected: Attempting to edit a Released revision's attributes returns 422 with an error toast (immutability enforced backend-side).
result: [pending]

## Summary

total: 10
passed: 0
issues: 0
pending: 10
skipped: 0
blocked: 0

## Gaps

(none yet — pending human testing)

## Notes — open code-review items (advisory, see 05-REVIEW.md)

These do not block UAT but are worth keeping in view while testing:
- **CR-02 (verify against D-07 spec):** In Review revisions may be editable via PATCH; spec check was deferred. Watch test step 5/10 behavior.
- **CR-03:** Parts list "Description" column always shows "—" (list response omits description). Search-by-description still works; the value just isn't shown in the column.
- **CR-01:** `released → obsolete` reachable directly — likely intended (part discontinuation), flagged for a domain call.
- **WR-01:** First-ever release shows a "Prior revision obsoleted" toast even when there was no prior released revision.
