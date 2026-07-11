# Task: feature-syerp-gl-posting-engine (Phase 9a — GL posting engine + receipt auto-post)

Plan source of truth: `.zj/phases/09a-gl-posting-engine/PLAN.md`. SYERP-12 AC1/AC2/AC3/AC8/AC9.
All 13 tasks complete. Backend proven by `verify_gl.py` (19/19) + Phase-8 regression (3/3);
frontend full suite 64/64; `tsc -b` clean. Next: `/zj:verify 09a`.

- [x] 1. Add pure Decimal JE-balance helpers + unit tests (`9844b3e`, 13 tests pass)
- [x] 2. Add JournalEntry + JournalLine models (AC1) (`f570f68`)
- [x] 3. Add migration 0009_syerp_gl_journal (AC1) (`343b334`, round-trips clean)
- [x] 4. Seed GR/IR account 2150 in the standard CoA (`8b97fc2`)
- [x] 5. Add GL posting/reversal/query service functions (AC1, AC2) (`fd9adf1`; NULL-balance bug fixed `69ab54e`)
- [x] 6. Add GL Pydantic schemas (`5679510`; uuid id-type fix `89daadc`)
- [x] 7. Add GL router endpoints with RBAC + audit (AC1, AC8, AC9) (`dee9820`, 5 routes, no PUT/DELETE)
- [x] 8. Wire receipt auto-post into receive_line, atomically (AC3, SC3 crux) (`0d9eb98`)
- [x] 9. Write verify_gl.py live-Postgres verification script (`69ab54e`, 19/19 PASS, re-runnable)
- [x] 10. Regression: re-run Phase-8 verify scripts unchanged (SC3 gate) — 3/3 green, on-hand/moving-avg unchanged
- [x] 11. Frontend: manual Journal Entry list + post dialog (SC4, AC1) (`38d65b1`, 3 tests)
- [x] 12. Frontend: reverse action + Account Register screen (SC4, SC2) (`c2bde3d`, 2 tests)
- [x] 13. Frontend: register routes in App.tsx + SyerpNav tabs (SC4) (`706432c`, full suite 64/64)
