# Task: feature-syerp-gl-posting-engine (Phase 9a — GL posting engine + receipt auto-post)

Plan source of truth: `.zj/phases/09a-gl-posting-engine/PLAN.md`. SYERP-12 AC1/AC2/AC3/AC8/AC9.

- [ ] 1. Add pure Decimal JE-balance helpers + unit tests
- [ ] 2. Add JournalEntry + JournalLine models (AC1)
- [ ] 3. Add migration 0009_syerp_gl_journal (AC1)
- [ ] 4. Seed GR/IR account 2150 in the standard CoA
- [ ] 5. Add GL posting/reversal/query service functions (AC1, AC2)
- [ ] 6. Add GL Pydantic schemas
- [ ] 7. Add GL router endpoints with RBAC + audit (AC1, AC8, AC9)
- [ ] 8. Wire receipt auto-post into receive_line, atomically (AC3, SC3 crux)
- [x] 9. Write verify_gl.py live-Postgres verification script (19/19 PASS, re-runnable; caught + fixed a NULL-propagation bug in derive_account_balance / register opening_balance for one-sided accounts)
- [ ] 10. Regression: re-run Phase-8 verify scripts unchanged (SC3 gate)
- [ ] 11. Frontend: manual Journal Entry list + post dialog (SC4, AC1)
- [ ] 12. Frontend: reverse action + Account Register screen (SC4, SC2)
- [ ] 13. Frontend: register routes in App.tsx + SyerpNav tabs (SC4)
