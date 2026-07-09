# Verification: 07 — Close v1.0 gaps
Date: 2026-07-09 | Commits: 3a5b9df..9134c17 (code: 5c33ed8, 1b8bfa1, 37b5f97, 5db8278) | Verified against HEAD 8975eeb (post-fix-loop)
Verdict: PASS

> **First pass returned GAPS** (1 blocker found in review + 3 majors). The blocker was fixed and
> every code criterion given executable, red/green-proven regression protection in the fix loop
> below; the full verification was then re-run from scratch. The two residuals (broken pytest
> harness, human-UAT) are owner-deferred by D-P7-4/D-P7-5 and homed in BACKLOG p1 / `/zj:milestone`.
> See "## Fix loop" at the bottom. The original GAPS findings are preserved verbatim below.

Scope note: the working tree ships at the Phase-8 tip, downstream of Phase 7. All "Exists/Wired"
checks are against current HEAD. "Works" was proven by driving the live functions against a
Postgres 17 container I brought up this session (podman available; stack up; schema 0008).

## Criteria

### SC1 — Partner alias, vendor import/export return 2xx not 500 — PASS (code+live), UNPROTECTED
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| 4 sites aliased `Partner as SyerpPartner` | yes | yes | yes | service.py:1644, 2149, 2617, 2750 — `grep -c "Partner as SyerpPartner"` == 4 |
| 0 bare `import SyerpPartner` | yes | — | — | `grep -c "import SyerpPartner$"` == 0 |
| `is_vendor` filters intact at all 4 sites | yes | yes | yes | service.py:1650, 2650, 2703, 2778 |
| `syerp/models.py` Partner untouched (Phase-7 constraint) | yes | — | yes | class Partner still at models.py:44; Phase-8 added new tables (+261 lines) but did not alter Partner; live `Partner(is_vendor=True)` constructed OK |
| `add_avl_link` (site 1644) runs, no ImportError/500 | yes | yes | yes | live: created vendor+part, `add_avl_link(...)` returned a link row (no ImportError) |
| `build_json_export` (site 2149) runs vendor lookup | yes | yes | yes | live: `build_json_export(db)` returned `{schema_version, exported_at, parts}` |

Sites 2617 (`validate_import`) / 2750 (`commit_import`) carry the identical alias and the module
imports clean (proven by every live call above executing); not separately driven end-to-end today.

### SC2 — generate_part_number numerically correct past digit boundary — PASS (code+live), UNPROTECTED
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| sqlalchemy import widened (Integer, cast) | yes | yes | yes | service.py:66 `from sqlalchemy import Integer, cast, func, or_, select` |
| regex-filter BEFORE cast | yes | yes | yes | service.py:130 `.op("~")(r"^P[0-9]+$")` then `cast(func.substring(...,2), Integer).desc()` |
| `return "P00001"` empty branch | yes | yes | yes | live: empty table returned `P00001` |
| try/except fallback + `f"P{suffix+1:05d}"` | yes | yes | yes | service.py:141-147 |
| numeric successor past 5→6 boundary, no crash on non-numeric | yes | yes | yes | live: seeded P99999+P100000+P-DUPE-01 → `generate_part_number` returned **P100001** (numeric MAX+1), did not throw on `P-DUPE-01` |

### SC3 — Parts List auto-refreshes after import commit — PASS (code), works=UI-deferred, NO TEST
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `useQueryClient` imported + called | yes | yes | n/a | ImportExport.tsx:30 import, :110 `const queryClient = useQueryClient()` |
| exactly one `invalidateQueries(['plum','parts'])` in `commitImportMutation.onSuccess` only | yes | yes | n/a | ImportExport.tsx:180, inside the commit mutation's onSuccess (lines 176-181); `grep -c invalidateQueries` == 1 |
| queryClient.ts staleTime unchanged | yes | — | — | src/lib/queryClient.ts staleTime 30_000 (untouched) |
| List actually refreshes without manual reload | — | — | DEFERRED | UI behavior is UAT check 11, deferred to milestone (D-P7-5); code is correct and mirrors working ArchivePartDialog analog |
No automated test asserts the invalidation call — see Gaps (major).

### SC4 — fixes proven by live-DB tests that RUN + consolidated human-verify — FAIL as written / relaxed by D-P7-4, D-P7-5
This is the crux. Both clauses of SC4 as written are UNMET; owner-approved deviations redefine it.
| Truth | Result | Evidence |
|---|---|---|
| `pytest tests/plum/` runs against Postgres, not silently skipped | **NO** | host `pytest tests/plum/` → **34 skipped** (DB probe fails). Root cause reproduced live: `_check_db_available` feeds a SQLAlchemy URL (`postgresql+psycopg2://...`) to `psycopg2.connect()`, which raises `invalid dsn: missing "="` — caught by bare `except` → silent skip (conftest.py:44-63). This is the exact defect D-P7-4 describes. |
| tests pass once probe forced on | **NO** | forced probe True + ran in-container against live DB → **10 failed** on `InterfaceError: another operation is in progress` (module-level async engine shared across event loops) + `ModuleNotFoundError: openpyxl` (Excel) — harness genuinely broken, confirming D-P7-4 second claim |
| pytest present in API container | **NO** | `podman exec compose_api_1 python -c "import pytest"` → ModuleNotFoundError (deps not in image) |
| the FIXES themselves work live (substitute proof) | **YES** | driven directly this session — SC1 add_avl_link/build_json_export execute; SC2 returns P100001 (above) |
| consolidated 12-check human-verify performed | **PARTIAL** | `.zj/UAT-v1.0.md`: checks 1 & 8 ran & passed (2026-07-04); checks 2-7, 9-12 = ⬜ todo, deferred to /zj:milestone (D-P7-5) |

Assessment: SC4's automated-test net does not exist (harness broken — a genuine infra blocker,
BACKLOG p1) and the human pass is 2/12. The fixes are real and I proved them live today, but the
criterion that would *protect* them from silently breaking again is unmet. Owner deviations
D-P7-4/D-P7-5 are recorded and legitimate; they redefine SC4 to "standalone/live proof + code-verify,
human-UAT to milestone." Even under that reading the durable regression protection is deferred to
backlog — so this cannot be reported as a clean PASS.

### SC5 — traceability reconciled to verified reality — PASS
| Truth | Result | Evidence |
|---|---|---|
| No PLUM-04..10 marked implemented/Complete on an unrun test | yes | SRD.md: PLUM-04..06/08/09 = `partial`, PLUM-07/10 = `partial (fix landed; UI UAT pending)`; requirements-progress.md rows 22-28 read "Code done; UI UAT pending", evidence explicitly says "test_bom.py pending harness" |
| PLUM-01 implemented is honest | yes | Phase-5 UAT 10/10 + Phase-7 fix proven live (I independently confirmed P100001) |
| CORE-01/CORE-09 implemented | yes | SRD.md:19, :67 |
| Counts footer reflects reality | yes | SRD.md:384-391 "partial 7 (PLUM-04..10 … flow-level UI confirmation deferred)" |

### SC6 — CLAUDE.md Technology Stack + Architecture describe live stack — PASS
| Truth | Result | Evidence |
|---|---|---|
| Tech Stack + Architecture describe FastAPI/SQLAlchemy/PG + React 19/Vite | yes | CLAUDE.md:58-76 (stack), :152-176 (architecture) |
| cites `.zj/codebase/MAP.md` | yes | CLAUDE.md:46, 153, 202 |
| legacy caveats scoped to plum/app, flan/app | yes | CLAUDE.md:48, 82-86, 194-198 (localStorage/no-server confined to "Legacy prototypes" subsections) |
| version/entry-point claims accurate (not confidently wrong) | yes | verified vs manifests: fastapi 0.138.0, sqlalchemy 2.0.51, alembic 1.18.4, asyncpg 0.31.0, pyjwt 2.13.0, openpyxl 3.1.5 (requirements.txt); react 19.2.7, vite 8.1.0, typescript 6.0.3 (package.json); app factory at main.py:65 |

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC1 (vendor path no-500) | test_avl.py::test_add_avl_link, test_import_export.py::test_import_commit_valid_vendor / test_export_json_with_avl_link — **all present but NON-EXECUTABLE** (harness broken; 34 skipped host / 10 fail on infra in-container). Effectively unprotected. |
| SC2 (numeric part#) | test_parts.py::test_generate_part_number_digit_boundary — present, **skipped/non-executable** (same harness). Unprotected. |
| SC3 (cache invalidation) | **MISSING (gap below)** — ImportExport.test.tsx sets up a QueryClient but never asserts invalidateQueries(['plum','parts']) was called. |
| SC4 | n/a (SC4 *is* the test/verify criterion) |
| SC5 (traceability honesty) | manual: doc-consistency review, not meaningfully automatable |
| SC6 (CLAUDE.md live stack) | manual: prose accuracy vs manifests, low-value to automate |

## Test suite
- Backend `pytest tests/plum/` (host, .venv): **34 skipped in 0.12s** — DB unreachable, silent skip (SC4 defect reproduced).
- Backend in-container after forcing the probe on: **10 failed** (async-engine/event-loop mismatch + missing openpyxl) — harness broken as D-P7-4 documents.
- Backend live-function drive (this session, against Postgres 17 @ schema 0008): SC1 add_avl_link + build_json_export execute clean; SC2 generate_part_number → P00001 (empty), P100001 (past boundary, non-numeric row present). PASS.
- Frontend `npm run test -- --run`: **47 passed (17 files)**. `npm run build`: **success** (dist built; only a chunk-size advisory).

## Gaps
1. **[major] PLUM live-DB test harness is broken — SC1/SC2 regression tests never execute.**
   Where: `backend/tests/conftest.py:44-63` (`_check_db_available` passes `postgresql+psycopg2://`
   to `psycopg2.connect`, which rejects it → every DB test silently skips) + module-level async
   engine reused across event loops (`InterfaceError: another operation is in progress`) + pytest &
   openpyxl absent from the API image. Effect: the committed regression tests for exactly the bugs
   this phase fixed cannot run — the fixes are unprotected against re-breaking. Owner-deferred
   (D-P7-4, BACKLOG p1). Suggested fix: strip `+psycopg2` in the probe DSN; give each test a
   function-scoped async engine/session with rollback isolation; add pytest+dev deps to the test
   image (or a dedicated test stage); seed `admin-user`.
2. **[major] SC3 has no automated regression test.** Where: `frontend/src/routes/plum/ImportExport.test.tsx`.
   A future edit removing the `invalidateQueries(['plum','parts'])` line would fail nothing.
   Suggested fix: mount ImportExport with a real QueryClient, spy on `queryClient.invalidateQueries`,
   drive a successful commit, assert it was called once with `{ queryKey: ['plum','parts'] }`.
3. **[major] SC4 human-verify is 2/12.** Checks 1 & 8 passed; 2-7 & 9-12 deferred to /zj:milestone
   (D-P7-5, owner-approved). Regression checks 9-12 (the ones that prove SC1/SC2/SC3 through the UI)
   remain unperformed. Where: `.zj/UAT-v1.0.md`.
4. **[minor] Stale API container image missing openpyxl.** Confirmed live: in-container Excel export
   raises `ModuleNotFoundError: openpyxl` though `backend/requirements.txt` pins openpyxl==3.1.5 —
   deployment-image staleness, not a code regression (matches the BACKLOG note). Suggested fix:
   rebuild the API image.

Note: I brought the podman stack up and left it running (compose_db_1/api_1/frontend_1); the dev DB
volume was fresh (0 plum rows) and now holds a handful of verification rows (P99999, P100000,
P-DUPE-01, P-AVL-VER, vendor V-VER-1). Harmless test data on a dev instance.

---

# Fix loop (2026-07-09) — blocker fixed, criteria turned into tests

## Blocker found in review, not in the first verification pass

**`generate_part_number` int4 overflow → persistent 500 (REVIEW.md finding 1).** Escalated from
`major` to **blocker** after reproducing it end-to-end against the live stack:

```
POST /api/v1/plum/parts {"part_number":"P9999999999"}   -> HTTP 201   (legal: String(50), no pattern)
POST /api/v1/plum/parts {"description":"..."}           -> HTTP 500   (auto-number, and forever after)
```

`part_number` has no format constraint (`schemas.py:122`), so `P9999999999` matches the `^P[0-9]+$`
filter and overflows `cast(..., Integer)` in the ORDER BY. Any authenticated `plum:write` user could
permanently disable part creation for everyone with one ordinary request; recovery required deleting
the row by hand. The Phase-7 SC2 fix *introduced* this — the old lexicographic `MAX()` had no cast.

Fixed in `7562a02`: cast target `Integer` → `Numeric`, which cannot overflow for any 50-char digit
string. Confirmed at the SQL level (`Integer` → `value "9999999999" is out of range`; `Numeric` →
returns the row) and end-to-end (poison row planted, auto-number 500s; row removed, auto-number 201s).

## Criteria became tests (each proven red/green)

| Criterion | Guard added | Red/green proof |
|---|---|---|
| SC1 vendor paths | `backend/scripts/verify_plum_vendor_paths.py` (8 assertions, live DB) — drives all **four** function-local alias sites independently | Reverting only the `commit_import` alias → `ImportError: cannot import name 'SyerpPartner'` on exactly that assertion, other three stay green |
| SC2 part numbering (SQL half) | `backend/scripts/verify_part_numbering.py` (7 assertions, live DB) incl. the `> int4` overflow scenario | Reverting the cast to `Integer` → exit 1, `NumericValueOutOfRangeError` |
| SC2 part numbering (Python half) | `backend/tests/plum/test_part_number.py` (4 pure tests) — **runs in the ordinary pytest suite**, no DB | n/a (pure); mirrors Phase 8's `_next_item_code` split |
| SC3 cache invalidation | `frontend/src/routes/plum/ImportExport.test.tsx` — drives choose-file → preview → Confirm Import against a real QueryClient; plus a negative test that a failed commit does **not** invalidate | Deleting the `invalidateQueries` line → the positive test fails, the negative one correctly stays green |

Why live scripts and not pytest: the DB-backed PLUM tests silently skip while the harness is broken
(gap 1, D-P7-4). The committed `tests/plum/test_avl.py` / `test_import_export.py` / `test_parts.py`
cases have **never executed** and would not catch a re-break. The `verify_*.py` pattern Phase 8
established does run, so the guards were built there. They are durable and committed, which is
strictly more than D-P7-4 contemplated ("standalone async scripts", uncommitted).

## Gap disposition

1. **[was major] Broken pytest harness** — NOT fixed (owner-deferred, D-P7-4, BACKLOG p1). Its
   *consequence* is mitigated: SC1 and SC2 now have executable, committed regression protection, so
   no Phase-7 criterion is left unprotected by it. The harness repair remains genuinely owed.
2. **[was major] SC3 had no test** — FIXED (`eab2107`).
3. **[was major] Human-UAT 2/12** — NOT fixed; owned by `/zj:milestone` per D-P7-5, tracked in
   `.zj/UAT-v1.0.md`. This is a real unpaid debt against **v1.0**, not against Phase 7.
4. **[minor] Stale API image missing openpyxl** — unchanged; BACKLOG.
5. **[review, minor] Partial-commit staleness** — RESOLVED as a non-issue: `commit_import` only
   `flush()`es and calls a single `db.commit()` at its end (`service.py`), and `get_db` never
   commits, so any raise leaves the transaction uncommitted and the context manager rolls it back.
   The commit is strictly all-or-nothing; not invalidating on failure is correct, and the new
   negative-path test pins that.
6. **[review, minor] Auto-number double-collision race** — pre-existing, not introduced here; logged
   to BACKLOG (three concurrent auto-numbered creates can still surface an unhandled IntegrityError).

## Full re-verification after the fix loop (source changed → everything re-run)

- Live-DB scripts, **66 assertions, 0 failures, all exit 0**: `verify_plum_vendor_paths` 8/8,
  `verify_part_numbering` 7/7, `verify_inventory` 15/15, `verify_purchasing` 18/18,
  `verify_e2e_p8` 18/18 (Phase-8 scripts re-run because the fix touched shared PLUM service code).
- Backend `pytest`: **90 passed, 98 skipped** (skips = the broken DB harness; the 4 new pure
  part-number tests run and pass).
- Frontend `npm run test -- --run`: **49 passed (17 files)**, up from 47. `npm run build`: clean.
- SC1–SC3 static invariants re-checked: 4 aliased sites / 0 bare imports / `is_vendor` intact /
  cast target `Numeric` / regex filter at `service.py:138` / `P00001` branch present /
  exactly 1 `invalidateQueries` / `queryClient.ts` staleTime untouched.

## Verdict rationale

SC1, SC2, SC3, SC5, SC6 pass on empirical evidence and now carry durable regression protection.
SC4 as literally written ("live-DB automated tests that actually RUN" + "one consolidated human
verify pass") is met only as **amended by the owner's recorded deviations**: D-P7-4 substitutes
standalone live-Postgres proof for the broken pytest harness — which now exists, committed and
red/green-proven — and D-P7-5 moves the 12-check human-UAT to `/zj:milestone`. Under the criteria
as amended, the phase delivers. The dev DB was left clean (poison row removed, auto-numbering
confirmed restored at HTTP 201).
