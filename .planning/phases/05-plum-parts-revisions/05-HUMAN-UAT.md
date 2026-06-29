---
status: passed
phase: 05-plum-parts-revisions
source: [05-VERIFICATION.md, 05-04-PLAN.md]
started: "2026-06-29"
updated: "2026-06-29"
---

# Phase 05 — Human Verification (PLUM Parts & Revisions)

All automated gates passed and the 10-step manual lifecycle walkthrough was completed in a live stack (Podman: db + api + Vite on :5174) signed in as admin. **All 10 steps PASS.**

Two integration/UI bugs were found and fixed during verification (gap closure):
- `fix(05) 37aeba1` — PLUM module never imported in main.py, so every /api/v1/plum/* route 404'd. Caught at runtime (unit tests never boot the full app).
- `fix(05) 2a75450` — Edit sheet blanked description and never sent it, so editing a Released part silently succeeded instead of returning the D-07 422 (step 10). Now loads the current description and sends it only when changed.
- `fix(05) f5cd61b` — pre-existing ProtectedRoute test-mock type error blocking the production build.

## Tests

### 1. PLUM nav landing
expected: Opening PLUM from the sidebar lands on /plum/parts.
result: pass

### 2. Create part
expected: Auto-prefilled editable Part Number; saved part appears with current revision A/0.1.0, status Draft.
result: pass

### 3. Search and filter
expected: Debounced search; status filter; show-archived toggle.
result: pass

### 4. Navigate to detail
expected: Row click → /plum/parts/{id} with header card + revision timeline.
result: pass

### 5. Advance Draft → In Review → Released
expected: Submit for Review then Release (confirm dialog) → Released.
result: pass

### 6. Create new revision (copy-forward)
expected: New Draft revision at top copying prior attributes.
result: pass

### 7. Supersede-on-release
expected: Releasing the new revision obsoletes the prior released one; exactly one Released.
result: pass

### 8. Revision history visibility
expected: Timeline newest-first with correct status badges.
result: pass

### 9. Archive / restore
expected: Archive → show archived → restore.
result: pass

### 10. Released immutability (server-enforced)
expected: Editing a Released revision's description returns 422 + error toast.
result: pass (after fix 2a75450)

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

None blocking. Closed during verification (see fixes above).

## Outstanding advisory review items (non-blocking — see 05-REVIEW.md)

Tracked for triage; did not block UAT or phase success criteria:
- **CR-02:** In Review revisions are editable via PATCH (confirmed via API). Bug only if D-07 mandates In Review = locked; needs a domain decision.
- **CR-03 (list column):** The Parts-list Description column still shows "—" (the list API omits description). The edit-form side was fixed in 2a75450; the list column itself was not.
- **CR-01 / WR-01..WR-05:** see 05-REVIEW.md.
