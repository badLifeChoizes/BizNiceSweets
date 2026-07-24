# Task: chore-port-verify-cruxes (v4.0 Phase 2b)

Port the DoD-named `verify_*` cruxes into the repaired pytest suite (NFR-5, 2b half of the
D-P2a-2 split) so reverting a crux turns a *pytest* test RED — not only a `verify_*` script.
TEST-ONLY phase: zero `backend/app/` change expected.

Plan: `.zj/phases/02b-port-verify-cruxes/PLAN.md`

## Checklist

- [x] 0. Cut branch `chore-port-verify-cruxes` and open this checklist
- [ ] 1. Scaffold new packages (mousse/crumb/gelato) + shared `seeded_ledger_db` fixture
- [ ] 2. Port inventory moving-average SERVICE crux (SC1a) — `tests/syerp/test_inventory_service.py`
- [ ] 3. Port GL posting-ties crux (SC1b) — `tests/syerp/test_gl_posting.py`
- [ ] 4. Port AP posting-ties crux incl. GR/IR-clears-to-zero (SC1c) — `tests/syerp/test_ap_posting.py`
- [ ] 5. Port AR posting-ties crux incl. aging↔1120 tie-out (SC1d) — `tests/syerp/test_ar.py`
- [ ] 6. Port MOUSSE WIP-clears crux (SC1e) — `tests/mousse/test_work_orders.py`
- [ ] 7. Port CRUMB reservation crux (SC1f) — `tests/crumb/test_sales_orders.py`
- [ ] 8. Port GELATO ship-COGS crux (SC1g) — `tests/gelato/test_shipments.py`
- [ ] 9. MOUSSE HTTP audit/RBAC test (SC3) — `tests/mousse/test_api.py`
- [ ] 10. CRUMB HTTP audit/RBAC test (SC3) — `tests/crumb/test_api.py`
- [ ] 11. GELATO HTTP audit/RBAC test (SC3) — `tests/gelato/test_api.py`
- [ ] 12. AR HTTP audit/RBAC test (SC3) — `tests/syerp/test_ar_api.py`
- [ ] 13. Confirm/add inventory audit/RBAC HTTP test (SC3) — `tests/syerp/test_inventory_api.py`
- [ ] 14. Prove non-vacuity per crux (SC2) — 7 mutations each flip a NAMED pytest RED, revert green
- [ ] 15. Full-suite regression + verify_* still-green + selfcheck (SC4 + SC5)
- [ ] 16. Drop the SRD caveats + update requirements-progress + record D-P2b (SC6)

## Non-vacuity table (Task 14)

| Crux | File + mutation | RED test name | Revert → green |
|---|---|---|---|
| inventory | | | |
| GL | | | |
| AP | | | |
| AR | | | |
| MOUSSE | | | |
| CRUMB | | | |
| GELATO | | | |

## Deviations

- **Task 0 branch point:** plan Task 0 names `f97b21a`, but PLAN.md was committed in the
  later plan-doc commit `3f71900` (the actual current tip). Cut off `3f71900` instead so
  PLAN.md travels onto the build branch — honoring the plan's own Context rationale ("cut
  the tip, not the bare tag, so PLAN.md travels"; 12a/12b/13/2a precedent). Trivial.

## Noticed

- (populate during Wave A/B)
