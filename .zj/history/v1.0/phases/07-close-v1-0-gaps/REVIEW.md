# Review: Phase 07 — close v1.0 gaps (`3a5b9df..9134c17`, branch `bugfix-plum-v1-gaps`)
Date: 2026-07-09

Scope reviewed: 3 code commits (`5c33ed8` alias, `1b8bfa1` part-number, `37b5f97`
cache invalidation), 2 added test files, and the `5db8278` CLAUDE.md refresh.
Verified all three fixes are still intact at HEAD — Phase 8 did not regress them.

> **Disposition (2026-07-09 fix loop).** Finding 1 was reproduced end-to-end against the live stack
> (plant `P9999999999` → HTTP 201; next auto-number → HTTP 500, permanently) and **escalated to
> blocker**. Fixed in `7562a02` (`Integer` → `Numeric`) and pinned by
> `backend/scripts/verify_part_numbering.py` scenario 3, proven red/green. Both minor questions are
> resolved below. See `VERIFICATION.md` "## Fix loop".

## Findings

### 1. [major → BLOCKER, FIXED in 7562a02] `generate_part_number()` int4 overflow → 500 permanently disables auto-numbering
- **Where:** `backend/app/modules/plum/service.py:132`
  (`order_by(cast(func.substring(PlumPart.part_number, 2), Integer).desc())`)
- **Failure:** `part_number` on `PartCreate` is `Optional[str] = Field(None, max_length=50)`
  with **no pattern constraint** (`backend/app/modules/plum/schemas.py:122`), and import
  accepts arbitrary part numbers too. A user creates or imports a strictly-numeric P-series
  number whose suffix exceeds int4 max, e.g. `P9999999999` (value 9,999,999,999 > 2,147,483,647).
  That row **matches** the `^P[0-9]+$` WHERE filter, so the `ORDER BY CAST(... AS Integer)`
  evaluates the overflowing cast over it → Postgres `ERROR: integer out of range`. The whole
  `select` raises, so **every** subsequent `create_part` that omits `part_number` (and the
  IntegrityError retry at line 330) returns 500. One crafted row bricks auto-numbering for all
  users, indefinitely. This is a *new* failure mode: the previous lexicographic `MAX()` had no
  cast and could not overflow — the fix traded a duplicate-number bug for a hard 500.
- **Fix:** cast to a type that cannot overflow for a 50-char digit string —
  `cast(func.substring(PlumPart.part_number, 2), Numeric)` — or order by
  `(func.length(PlumPart.part_number), PlumPart.part_number)`. `BigInteger` only moves the
  cliff to 19 digits; `Numeric` is the safe choice given `String(50)`.

## Questions

- **Partial-commit staleness (minor):** `ImportExport.tsx:180` invalidates `['plum','parts']`
  only in `commitImportMutation.onSuccess`. Confirmed this prefix-matches PartsList's
  `['plum','parts',{...}]` key, so SC3 holds for the success path. But if `commit_import`
  ever returns non-2xx *after* having persisted some rows (partial write), axios routes to
  `onError` and the list is **not** invalidated → stale Parts List showing pre-import state.
  Needs confirmation that `commit_import` is strictly all-or-nothing in one transaction; if so,
  no issue.
  **ANSWERED — no issue.** `commit_import` only `flush()`es internally and calls a single
  `await db.commit()` as its last statement; `get_db` (`backend/app/core/db.py:22-25`) never commits,
  so any raise before that leaves the transaction uncommitted and the `async with` rolls it back.
  Partial writes cannot occur, so skipping invalidation on the error path is correct. A negative-path
  test now pins it (`ImportExport.test.tsx`, "does NOT invalidate when the commit fails").
- **Auto-number race, double collision (minor, pre-existing — not introduced here):**
  `create_part` (service.py:318-337) retries a collided auto-number exactly once; the retry's
  `await db.flush()` (line 337) is **not** guarded, so three concurrent no-part_number creates
  can still surface an unhandled `IntegrityError` → 500. Unchanged by this diff; noted because
  the part-number commit touches this path's correctness story.
- **Auto-number race, double collision — logged to BACKLOG** in the fix loop (pre-existing,
  not introduced by this diff).
- **Tests skip without a DB (minor):** both added tests take `skip_if_no_db`
  (`backend/tests/conftest.py:96`), which calls `pytest.skip` when no Postgres is reachable.
  When they *do* run they assert the right things (boundary test checks numeric successor +
  uniqueness; export/commit tests exercise the real vendor-code path). But in any CI runner
  without a live DB they are silent no-ops that read as regression coverage while proving
  nothing. This is acknowledged as deferred (D-P7-4); flagging the residual risk only.
  **ADDRESSED (mitigation, not cure):** the harness is still broken, but SC1/SC2 now have
  executable guards that DO run — `scripts/verify_plum_vendor_paths.py`,
  `scripts/verify_part_numbering.py`, and the pure `tests/plum/test_part_number.py`. The harness
  repair itself stays BACKLOG p1.

## Cleared (checked, not defects)
- **`Partner as SyerpPartner` alias (all 4 sites):** correct — `syerp/models.py:44` defines
  `class Partner`; no `SyerpPartner` class exists, which is exactly the ImportError being fixed.
  `is_vendor` filters are untouched by the diff, and no stray non-aliased `SyerpPartner`
  reference remains anywhere in `backend/app/`.
- **Regex-before-cast ordering:** valid. Postgres evaluates WHERE before the ORDER BY sort key,
  so non-numeric rows like `P-DUPE-01` are excluded before the cast runs — the PLUM-01 fix works.
  (Overflow in Finding 1 is orthogonal: it comes from *matching* rows, not filtered ones.)
- **`try/except (IndexError, ValueError)` fallback (service.py:141-144):** now dead/defensive —
  the `^P[0-9]+$` filter guarantees `max_pn` is `"P"` + ≥1 digit, so `int(max_pn[1:])` cannot
  raise; the `suffix = 0 → "P00001"` collision path can no longer fire.
- **`P100000` 6-char output:** column is `String(50)`, regex is variable-length, UI treats it as
  an opaque string; no fixed-5-digit parser found downstream. Not a defect.
- **CLAUDE.md stack refresh (`5db8278`):** every version claim matches the repo pins —
  FastAPI 0.138.0, SQLAlchemy 2.0.51, asyncpg 0.31.0, Alembic 1.18.4, React 19.2.7,
  TypeScript 6.0.3, Vite 8.1.0, Tailwind 4.3.1, TanStack Query 5.101.1, ruff 0.15.18,
  pytest 9.1.1. Commands and file paths check out. No factual findings.
