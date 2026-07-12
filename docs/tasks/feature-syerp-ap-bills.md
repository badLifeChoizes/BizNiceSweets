# Task: feature-syerp-ap-bills (Phase 09b — AP bills, PO match & payments)

Plan: `.zj/phases/09b-ap-bills-match-payments/PLAN.md` (SYERP-12 AC4/AC5/AC8/AC9)
Branch base: `feature-syerp-gl-posting-engine` HEAD (verified 09a tip, tag `zj/good-09a-gl-posting-engine`).

- [ ] 1. Pure Decimal AP helpers + unit tests (service.py, test_ap.py)
- [ ] 2. Bill/BillLine/Payment/PaymentAllocation models (models.py)
- [ ] 3. Migration 0010_syerp_ap_bills (alembic)
- [ ] 4. Seed 1111 Bank – Checking (coa_seed.py)
- [x] 5. Service: unbilled-receipts query + create/edit bill (service.py)
- [x] 6. Service: post_bill → balanced JE + Draft→Posted (service.py)
- [x] 7. Service: record_payment → JE + allocations + overpay guard (service.py)
- [ ] 8. AP Pydantic schemas (schemas.py)
- [ ] 9. Router: bill endpoints + RBAC + audit (router.py)
- [ ] 10. Router: payment endpoint + RBAC + audit (router.py)
- [ ] 11. verify_ap.py live-Postgres verification (scripts)
- [ ] 12. verify_ap_api.py HTTP-level verification (scripts)
- [ ] 13. Regression: re-run 9a + Phase-8 verify scripts
- [ ] 14. Frontend: Bills list + create/match dialog
- [ ] 15. Frontend: Bill detail + Post action + Pay dialog
- [ ] 16. Frontend: register routes + SyerpNav "Bills" tab
