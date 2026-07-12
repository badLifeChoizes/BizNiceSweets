# Task: feature-syerp-ap-bills (Phase 09b — AP bills, PO match & payments)

Plan: `.zj/phases/09b-ap-bills-match-payments/PLAN.md` (SYERP-12 AC4/AC5/AC8/AC9)
Branch base: `feature-syerp-gl-posting-engine` HEAD (verified 09a tip, tag `zj/good-09a-gl-posting-engine`).

Status: **BUILD COMPLETE** — all 16 tasks done + verified. Next: `/zj:verify 09b`.

- [x] 1. Pure Decimal AP helpers + unit tests (`c1b431b`) — 14/14 pytest
- [x] 2. Bill/BillLine/Payment/PaymentAllocation models (`1697973`)
- [x] 3. Migration 0010_syerp_ap_bills (`b91ed73`) — upgrade/downgrade/upgrade round-trip
- [x] 4. Seed 1111 Bank – Checking (`5502445`)
- [x] 5. Service: unbilled-receipts query + create bill (`52d9a83`) + dup-guard (`13ca4cd`)
- [x] 6. Service: post_bill → balanced JE + Draft→Posted (`3b8eb33`)
- [x] 7. Service: record_payment → JE + allocations + overpay guard (`be0a774`)
- [x] 8. AP Pydantic schemas (`ff39967`)
- [x] 9. Router: bill endpoints + RBAC + audit (`7ef302b`)
- [x] 10. Router: payment endpoint + RBAC + audit (`e7bb9b2`) + list_payments read (`99ef164`)
- [x] 11. verify_ap.py live-Postgres verification (`e2cd5f2`) — 22/22 PASS, GR/IR clears to zero
- [x] 12. verify_ap_api.py HTTP-level verification (`6aa86af`) — 24/24 PASS, audit + RBAC
- [x] 13. Regression: 9a + Phase-8 verify scripts (verify_gl/purchasing/inventory/e2e_p8 all PASS)
- [x] 14. Frontend: Bills list + create/match dialog (`4e25ab2`)
- [x] 15. Frontend: Bill detail + Post action + Pay dialog (`bb57463`)
- [x] 16. Frontend: register routes + SyerpNav "Bills" tab (`72cfd82`)

## Test evidence
- Backend pytest: 117 passed, 100 skipped (D-P7-4 DB-harness debt), 0 failed.
- Frontend: 72 passed (22 files), 0 failed.
- verify_ap.py: 22/22 PASS (crux — 2150 GR/IR pre-receipt -350 → post-bill -350, Decimal-exact).
- verify_ap_api.py: 24/24 PASS (bill.created/bill.posted/payment.recorded audit rows; 403/401/200 RBAC).
- Regression: verify_gl, verify_purchasing, verify_inventory, verify_e2e_p8 all exit 0, unchanged counts.
