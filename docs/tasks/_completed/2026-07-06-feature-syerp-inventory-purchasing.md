# SYERP Extended — Inventory & Purchasing (Phase 8)

**Branch:** `feature-syerp-inventory-purchasing`
**Created:** 2026-07-05
**Completed:** 2026-07-06
**Status:** Complete
**Requirements:** SYERP-10, SYERP-11 (PRD-7)

## Goal

Extend the existing `syerp` module so a shop can stock inventory items across named locations
with a moving-average-valued immutable ledger, and run purchase orders
(Draft→Approved→Receiving→Closed) whose receipts post inventory receipts at the PO line unit
cost — no AP, no bins, no negative stock, no over-receipt.

> **Authoritative tracker:** `.zj/phases/08-syerp-inventory-purchasing/PLAN.md` was the live
> build tracker (ZJ workflow uses PLAN.md checkboxes). This file is the CLAUDE.md-convention
> mirror, seeded complete at phase close. Testing reality per D-P7-4: the backend live-DB pytest
> harness is broken, so behavioral truth comes from standalone Postgres scripts in
> `backend/scripts/` + pure unit tests — not `pytest … green`.

## Checklist (all 25 tasks — one line + representative commit)

### Wave A — Inventory backend (SYERP-10)
- [x] 1. Inventory schema — migration `0007_syerp_inventory.py` + ORM models (`b5c5c31`)
- [x] 2. Inventory item CRUD + numeric-safe `ITEM-####` generator (`511d6ae`)
- [x] 3. Stock-location CRUD + idempotent `Main` seed wired into `run_seeds` (`06f318c`)
- [x] 4. On-hand & valuation read (derivation query) + txn-history read (`e35021e`)
- [x] 5. Receipt posting + pure-Decimal `compute_new_moving_avg` scale-6 ROUND_HALF_UP (`8e1b31f`)
- [x] 6. Adjustment posting + per-location negative-stock guard (`0074bf0`)
- [x] 7. Transfer posting — paired legs net-zero + source-underflow guard (`5f2a228`)
- [x] 8. Inventory unit tests + standalone `verify_inventory.py` — **14/14 PASS** (`e309260`)

### Wave B — Inventory UI (SYERP-10)
- [x] 9. Inventory Items screen (list + ItemSheet + archive) + route/nav (`1fd2423`)
- [x] 10. Stock Locations screen (list + LocationSheet + archive) (`8e75af9`)
- [x] 11. Item detail — on-hand-by-location + valuation + ledger (`8b2c748`)
- [x] 12. Stock Adjustment dialog (`c9d6952`)
- [x] 13. Stock Transfer dialog (`cdf0e6c`)

### Wave C — Purchasing backend (SYERP-11)
- [x] 14. Purchasing schema — migration `0008_syerp_purchasing.py` + ORM models (`cafa93f`)
- [x] 15. PO draft CRUD + numeric-safe `PO-####` generator + vendor-only guard (`b5d7882`)
- [x] 16. PO FSM approve/close — `PO_TRANSITIONS` stamps `approved_at`/`approved_by` (`92896ea`)
- [x] 17. PO receiving → real inventory receipt + over-receipt reject + status roll-up (`79181bd`)
- [x] 18. Vendor purchase-history read — per-PO total + received roll-up (`ce5f666`)
- [x] 19. Purchasing unit tests + standalone `verify_purchasing.py` — **18/18 PASS** (`451ec7d`)

### Wave D — Purchasing UI (SYERP-11)
- [x] 20. PO list screen (status + totals, vendor filter) + route/nav (`6d8afcc`)
- [x] 21. PO create / draft-edit screen (vendor picker + line editor) (`e21ac2a`)
- [x] 22. PO detail screen (roll-up + approve/close actions) (`cd03899`)
- [x] 23. Receiving dialog (per-line qty + location picker) (`8aa6b65`)

### Wave E — Verify
- [x] 24. Fresh-DB end-to-end integration proof — `verify_e2e_p8.py` **18/18 PASS** (`3703c51`)
- [x] 25. Update requirement statuses, progress, and UAT checklist (this commit)

## Acceptance Criteria

- Every SYERP-10 (1–8) and SYERP-11 (1–8) acceptance criterion in `.zj/SRD.md` covered by ≥1 task.
- Backend behavior proven against live Postgres by the three `backend/scripts/verify_*.py` scripts.
- Flow-level HUMAN UI confirmation deferred to the v2.0 milestone UAT (`.zj/UAT-v2.0.md`, D-P7-5).

## Notes

- Decisions: D-P8-8/9/10 (one phase / UI folded in / single `syerp:write`), D-P8-11..15 (branch,
  moving-avg stored column, code prefixes, `Main` seed, `qty_received` accumulator).
- Deviations & Noticed items recorded in the PLAN.md tail (ruff/eslint lint gates absent; Starlette
  422 deprecation; podman-compose `.env` non-substitution) — surface to owner before merge.

## Related

- Plan: `.zj/phases/08-syerp-inventory-purchasing/PLAN.md`
- Requirements: `.zj/SRD.md` (SYERP-10, SYERP-11); `docs/features/requirements-progress.md`
- UAT: `.zj/UAT-v2.0.md`
