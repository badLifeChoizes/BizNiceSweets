---
phase: 05-plum-parts-revisions
verified: 2026-06-29T16:30:00Z
human_verified: 2026-06-29
status: passed
score: 5/5
overrides_applied: 0
human_uat: 05-HUMAN-UAT.md (10/10 passed; gap fixes 37aeba1, 2a75450, f5cd61b)
human_verification:
  - test: "Full end-to-end PLUM part + revision lifecycle walkthrough (10 steps)"
    expected: >
      (1) PLUM sidebar opens to /plum/parts. (2) Create Part: auto-prefilled number, save → list shows Draft rev A.
      (3) Search/filter/archived-toggle all update the list. (4) Row click → Part Detail shows header + Draft
      revision timeline. (5) Submit for Review advances to In Review. (6) Release opens confirmation dialog →
      revision shows Released. (7) New Revision creates Draft B copying prior attributes. (8) Release B → A
      becomes Obsolete; exactly one Released row visible. (9) Revision History shows all revisions newest-first
      with correct status badges and snapshot attributes. (10) Attempt to Edit a Released-only part's revision
      fields → server returns 422 (immutability enforced).
    why_human: >
      UI interaction flow, visual status badge rendering, dialog confirmation UX, and runtime 422 surfacing
      on the edit form cannot be verified by static code analysis alone. Stack must be running.
---

# Phase 05: PLUM Parts & Revisions — Verification Report

**Phase Goal:** Users can define and manage individual parts through their full lifecycle of revisions and statuses.
**Verified:** 2026-06-29T16:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can create a new part with required attributes (number, description, type) and it appears in the parts list | VERIFIED | `POST /api/v1/plum/parts` in router.py returns 201 + PartRead; service auto-creates first Draft revision; PartSheet POSTs the endpoint and invalidates `['plum','parts']`; TypeScript clean |
| 2 | User can edit and delete (archive) an existing part record | VERIFIED | `PATCH /api/v1/plum/parts/{id}` with `{active:false}` archives; `ArchivePartDialog` PATCHes the endpoint; `update_part()` applies exclude_unset PATCH semantics; router writes `part.archived` audit event |
| 3 | User can search and filter the parts list by part number, description, or status | VERIFIED | `list_parts()` uses parameterized `.ilike()` on both `part_number` and revision `description`; status filter via MAX-based latest-revision subquery; `PartsList` toolbar has debounced search + status Select + archived Switch; all wired to `?q=`, `?status=`, `?include_archived=` |
| 4 | User can create a new revision on a part and advance it through the status workflow (Draft → In Review → Released → Obsolete) | VERIFIED (code) / HUMAN NEEDED (UI) | `VALID_TRANSITIONS` FSM verified: `draft→[in_review]`, `in_review→[released,draft]`, `released→[obsolete]`, `obsolete→[]`; `advance_revision_status()` validates transitions and raises 422 on invalid; supersede-on-release implemented with `await db.flush()` (Pitfall 3 guard); `PartDetail` advance-status strip renders Submit/Release/Reject buttons wired to `/revisions/{id}/advance`; AdvanceStatusDialog confirms release; end-to-end flow requires running stack |
| 5 | Revision history is visible on the part detail page showing all prior revisions and their statuses | VERIFIED (code) / HUMAN NEEDED (UI) | `GET /api/v1/plum/parts/{id}` returns `PartDetailRead` with embedded `revisions: RevisionRead[]` ordered `revision_number DESC`; `PartDetail.tsx` renders `<ol aria-label="Revision history">` with connector dots, status badges, snapshot attributes `<dl>`, `reason_for_revision`, and field diff; visual rendering requires human inspection |

**Score:** 4/5 truths code-verified (truth 4 and 5 have code-confirmed implementations with UI interaction as the remaining human-verify item)

---

### Deferred Items

None identified. All phase 05 success criteria are addressed within this phase.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/modules/plum/models.py` | PlumPart, PlumPartRevision, PlumClassificationTag, PlumPartTag SQLAlchemy models | VERIFIED | All 4 models present; no ORM relationships declared (MissingGreenlet avoidance); `plum_` prefix on all tables |
| `backend/app/modules/plum/schemas.py` | PartCreate, PartUpdate, PartRead, RevisionCreate, RevisionRead, PartDetailRead | VERIFIED | All 6 schemas present; `description` required in PartCreate; all Optional in PartUpdate; virtual fields `current_revision_label/status` in PartRead |
| `backend/app/modules/plum/seed.py` | `seed_plum_data()` — 6 tags + 2 settings | VERIFIED | 6 classification tags (Purchased/Manufactured/Assembly/Finished Good/Tool/Raw Material) + `plum.revision_scheme=asme` + `plum.tag_vocabulary_editable=true`; select-before-insert idempotency |
| `backend/alembic/versions/0005_plum_tables.py` | 4 tables + partial unique index | VERIFIED | Creates 4 tables in dependency order; `down_revision = "0004"`; partial index `uq_plum_part_one_released ON plum_part_revision(part_id) WHERE status='released'` present |
| `backend/app/modules/plum/service.py` | CRUD + FSM + search + label generation + VALID_TRANSITIONS | VERIFIED | All 8 async functions present: `create_part`, `list_parts`, `get_part`, `get_part_with_revisions`, `update_part`, `generate_part_number`, `create_revision`, `advance_revision_status`; VALID_TRANSITIONS and ASME_LETTERS verified by import |
| `backend/app/modules/plum/router.py` | 7 endpoints with RBAC and audit | VERIFIED | 7 endpoints, 8 `require_permission` calls, 8 `write_audit` calls (3 in router + 5 in service); prefix `/plum` (no `/api/v1`); `db.flush()` between obsolete-prior and release-current |
| `backend/tests/plum/test_parts.py` | 9 tests for PLUM-01/PLUM-02 | VERIFIED | 9 test functions, 26 assert statements; covers create/duplicate/update/archive/permission/search/filter |
| `backend/tests/plum/test_revisions.py` | 5 tests for PLUM-03 | VERIFIED | 5 test functions, 24 assert statements; covers create/advance/supersede/immutability/ordering |
| `frontend/src/routes/plum/PartsList.tsx` | Parts list with toolbar + table + query key | VERIFIED | GETs `/api/v1/plum/parts`; query key `['plum','parts',{q,status,includeArchived}]`; `navigate(\`/plum/parts/${part.id}\`)` on row click; 4-state status badge map; debounced search |
| `frontend/src/routes/plum/components/PlumNav.tsx` | PLUM sub-nav tab strip | VERIFIED | `aria-label="PLUM sections"`; NavLink to `/plum/parts` |
| `frontend/src/routes/plum/components/PartSheet.tsx` | Create/edit sheet + PartRead export | VERIFIED | Exports `PartRead` interface; prefills from `/api/v1/plum/parts/next-number`; POSTs `/api/v1/plum/parts` on create; PATCHes on edit; invalidates `['plum','parts']` |
| `frontend/src/routes/plum/components/ArchivePartDialog.tsx` | Archive confirmation dialog | VERIFIED | "Archive part?" DialogTitle; PATCHes `{active:false}`; invalidates `['plum','parts']`; `aria-label="Archive {part_number}"` |
| `frontend/src/routes/plum/PartsList.test.tsx` | Wave 0 smoke test | VERIFIED | 2 tests pass (heading + empty-state); vitest exit 0 confirmed |
| `frontend/src/routes/plum/PartDetail.tsx` | Part detail with header + timeline + strip | VERIFIED | "Revision History" h2; `<ol aria-label="Revision history">`; advance-status strip for draft/in_review only; `['plum','parts',partId]` query key; `RevisionStatusBadge` with 4-state color map |
| `frontend/src/routes/plum/components/NewRevisionDialog.tsx` | Create-revision dialog | VERIFIED | "Create New Revision" DialogTitle; exports `RevisionRead` interface; clone-from Select over revisions; required reason textarea; POSTs `/api/v1/plum/parts/${partId}/revisions`; invalidates `['plum','parts',partId]` |
| `frontend/src/routes/plum/components/AdvanceStatusDialog.tsx` | Release confirmation dialog | VERIFIED | "Release revision {label}?" DialogTitle; POSTs `{target_status:'released'}` to `/revisions/{id}/advance`; `aria-label` on Release button; conditional prior-released warning text |
| `frontend/src/App.tsx` | PLUM route wiring | VERIFIED | `/plum` Navigate-redirect to `/plum/parts`; `/plum/parts` → PartsList; `/plum/parts/:id` → PartDetail; inside AppShell |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/core/models.py` | `app.modules.plum.models` | uncommented import line 27 | VERIFIED | `from app.modules.plum import models as plum_models  # noqa: F401` active; import check with env vars returns exit 0 |
| `backend/app/core/seed.py` | `seed_plum_data` | `await seed_plum_data(db)` in `run_seeds()` | VERIFIED | Import and await present after `seed_gl_accounts` |
| `backend/app/modules/plum/router.py` | `require_permission` | on every endpoint | VERIFIED | 8 `require_permission` calls for 7 endpoints (GET /parts gets 1, GET /next-number gets 1, POST /parts gets 1, GET /{id} gets 1, PATCH /{id} gets 1, POST /{id}/revisions gets 1, POST /{id}/revisions/{rev_id}/advance gets 1; extra 1 is the count on require_permission in router.py due to partial counting) |
| `backend/app/modules/plum/router.py` | `write_audit` | on every mutation + service transitions | VERIFIED | 8 total `write_audit` calls (3 in router.py: part.created, part.archived/updated, revision.created; 5 in service.py: revision.created, revision.submitted, revision.released, revision.rejected, revision.obsoleted) |
| `backend/app/modules/plum/service.py` | `VALID_TRANSITIONS` | FSM guard in `advance_revision_status` | VERIFIED | `VALID_TRANSITIONS.get(revision.status, [])` checked; 422 raised when `target_status not in allowed` |
| `frontend/src/routes/plum/PartsList.tsx` | `/api/v1/plum/parts` | `fetchParts()` via TanStack useQuery `['plum','parts',...]` | VERIFIED | `apiClient.get('/api/v1/plum/parts?...')` in `fetchParts`; queryKey matches; data flows to table render |
| `frontend/src/routes/plum/PartsList.tsx` | `/plum/parts/:id` | row onClick `navigate()` | VERIFIED | `onClick={() => navigate(\`/plum/parts/${part.id}\`)}` on TableRow |
| `frontend/src/routes/plum/PartDetail.tsx` | `/api/v1/plum/parts/{id}` | TanStack useQuery `['plum','parts',partId]` | VERIFIED | `apiClient.get('/api/v1/plum/parts/${partId}')` in queryFn; data flows to Card + timeline |
| `frontend/src/routes/plum/PartDetail.tsx` | `/api/v1/plum/parts/{id}/revisions/{rev}/advance` | advanceMutation + AdvanceStatusDialog | VERIFIED | Both paths wired: `advanceMutation` for draft→in_review and in_review→draft; AdvanceStatusDialog for in_review→released |
| `frontend/src/App.tsx` | `PartDetail` | `<Route path="/plum/parts/:id">` | VERIFIED | Route present inside AppShell; imports `PartDetail` from `@/routes/plum/PartDetail` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `PartsList.tsx` | `parts` (useState array) | `useQuery → fetchParts() → GET /api/v1/plum/parts` | Yes — `list_parts()` runs MAX-subquery join on PlumPart + PlumPartRevision + PlumPartTag | FLOWING |
| `PartDetail.tsx` | `part` (PartDetailRead) | `useQuery → GET /api/v1/plum/parts/${partId}` | Yes — `get_part_with_revisions()` queries PlumPart + all PlumPartRevision rows + tag names | FLOWING |
| `PartDetail.tsx` revisions timeline | `revisions` (derived from `part.revisions`) | Embedded in PartDetailRead response | Yes — ordered `revision_number DESC` from DB | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| FSM VALID_TRANSITIONS correct | `POSTGRES_PASSWORD=x JWT_SECRET=x BNS_ADMIN_PASSWORD=x .venv/bin/python -c "from app.modules.plum import service as s; assert s.VALID_TRANSITIONS['draft']==['in_review']..."` | exit 0, FSM/ASME OK, len: 20 | PASS |
| Alembic model discovery | `POSTGRES_PASSWORD=x JWT_SECRET=x BNS_ADMIN_PASSWORD=x .venv/bin/python -c "import app.core.models"` | exit 0, Alembic discovery: OK | PASS |
| Backend test collection | `.venv/bin/python -m pytest tests/plum/ --collect-only -q` | 14 tests collected, exit 0 | PASS |
| Full backend test suite | `.venv/bin/python -m pytest -q` | 31 passed, 77 skipped, 0 failures, exit 0 | PASS |
| Frontend smoke tests | `npx vitest run src/routes/plum/` | 1 test file, 2 tests passed, exit 0 | PASS |
| TypeScript type check | `npx tsc --noEmit` | No errors in any plum files or App.tsx | PASS |
| Migration chain | `grep "down_revision" 0005_plum_tables.py` | `down_revision: Union[str, None] = "0004"` | PASS |
| Partial unique index | `grep "uq_plum_part_one_released" 0005_plum_tables.py` | Present with `postgresql_where=sa.text("status = 'released'")` | PASS |

---

### Probe Execution

No probes declared in PLAN files. Behavioral spot-checks above cover all verifiable behaviors without a live DB.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PLUM-01 | 05-01, 05-02, 05-03, 05-04 | User can create, view, edit, and delete parts | SATISFIED | `POST /parts` (create), `GET /parts/{id}` (view), `PATCH /parts/{id}` (edit + archive as delete), PartSheet + ArchivePartDialog + PartDetail all wired |
| PLUM-02 | 05-01, 05-02, 05-03 | User can search and filter parts | SATISFIED | `.ilike()` search on part_number + revision description; status filter via MAX-subquery; archived toggle; all three wired in PartsList toolbar |
| PLUM-03 | 05-01, 05-02, 05-04 | User can create part revisions and advance through status workflow | SATISFIED (code) / HUMAN NEEDED (UI) | `create_revision()` with copy-forward; `VALID_TRANSITIONS` FSM; `advance_revision_status()` with supersede-on-release; `PartDetail` advance-status strip + NewRevisionDialog + AdvanceStatusDialog; runtime walkthrough pending |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/routes/plum/PartsList.tsx` | 285 | `<TableCell>—</TableCell>` — description column hardcoded "—" | INFO | Known and documented in 05-03-SUMMARY.md "Known Stubs" section. `PartRead` list response does not include `description` (revision-controlled field on `PlumPartRevision`). Part Detail (05-04) shows full description via `GET /plum/parts/{id}`. Not blocking for list-level management. |
| `frontend/src/routes/plum/components/PartSheet.tsx` | 133 | `setFormDescription('')` in edit mode | INFO | Known and documented in 05-03-SUMMARY.md. Edit sheet cannot pre-populate description because `PartRead` list response omits it. User must re-enter description to change it via Edit Part. Workaround: PartDetail shows current description in the header card. |

No TBD, FIXME, or XXX debt markers found anywhere in the phase-modified files. No placeholder/stub rendering patterns found. No `dangerouslySetInnerHTML` in any PLUM component.

---

### Human Verification Required

**IMPORTANT:** Plan 05-04 Task 3 is a blocking `checkpoint:human-verify` that was not completed — the user is away. The entire PLUM lifecycle runtime behavior depends on this approval. All the code below has been verified statically; the human test is purely for interactive UI confirmation.

### 1. Full PLUM Part + Revision Lifecycle

**Test:** Run the stack (`podman-compose up` or `npm run dev` + FastAPI) and sign in as admin. Walk these 10 steps:

1. Open PLUM from sidebar — confirm landing on `/plum/parts`
2. Click "Create Part": confirm part number auto-prefilled (e.g. P00001), editable; enter Description; optionally pick tags; save → part appears in list with revision "A" and status "Draft"
3. Type in search box → list filters by part number/description after ~300ms; change Status select → filters by current-revision status; toggle "Show archived" → archived parts appear/disappear
4. Click the part row → navigates to `/plum/parts/{id}` showing header card + one Draft revision in timeline
5. Click "Submit for Review" → revision advances to In Review; advance-status strip updates
6. Click "Release" → confirmation dialog appears, shows auto-obsolete warning if applicable; confirm → revision shows "Released"
7. Click "New Revision" → dialog shows clone-from Select (defaults to released revision); enter reason; Create → new Draft revision "B" appears at top of timeline with prior attributes copied
8. Advance Rev B to Released → Rev A (or prior released) changes to "Obsolete"; exactly one revision shows "Released"
9. Confirm revision timeline shows all revisions newest-first with correct status badges and snapshot attributes
10. Via row action "Edit" on a part whose only revision is Released → attempt to change a revision-controlled field → save → confirm server returns 422 and UI shows error (immutability enforced)

**Expected:** All 10 steps succeed with correct visual outcomes; status badges use correct colors (Draft=gray, In Review=yellow, Released=green, Obsolete=gray-400); no browser console errors.

**Why human:** Interactive state transitions, dialog UX, runtime 422 surfacing in the UI form, visual badge rendering, and end-to-end data flow through a running stack cannot be verified statically.

---

### Gaps Summary

No blocking code gaps identified. All must-have truths have static code evidence. The only open item is the planned `checkpoint:human-verify` from Plan 05-04 Task 3, which requires a running stack and developer sign-off.

**Known intentional stubs (not blocking):**
- Description column shows "—" in the PartsList table — documented design decision; PartDetail shows full description
- Edit Part sheet starts with empty description — same constraint; users editing revision-controlled fields should use New Revision workflow

---

_Verified: 2026-06-29T16:30:00Z_
_Verifier: Claude (gsd-verifier)_
