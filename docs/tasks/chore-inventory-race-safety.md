# chore-inventory-race-safety — Phase 4 verify/review fix-ups

Follow-up fixes for the gaps found by `/zj:verify 4` (VERIFICATION.md gap 1) and the
code review (REVIEW.md findings 1 and 3). Continues the same branch; the original
build checklist is archived at
`docs/tasks/_completed/2026-07-25-chore-inventory-race-safety.md`.

- [x] Fix 1 (REVIEW finding 1, major): restore the per-location floor beside the
      pool floor in MOUSSE `issue_components` (mirror `post_adjustment`'s
      accumulate-and-guard; defends legacy bin-split desync).
- [x] Fix 2 (REVIEW finding 3, minor): `post_transfer` refreshes the item under the
      FOR UPDATE lock before valuing the legs (mirror `post_receipt`'s refresh).
- [x] Fix 3a (VERIFICATION gap 1): `verify_gelato.py` scenario F — binned-source
      transfer NULL-422 + zero rows; named-bin transfer out-leg-binned /
      in-leg-unbinned (D-P4-5) Decimal-exact; positive adjust into a named bin
      raises that pool (D-P4-6).
- [ ] Fix 3b (VERIFICATION gap 1): `verify_mousse.py` binned-issue scenario —
      NULL-422 + zero rows at a fully-binned location; named-bin issue carries
      bin_id with WIP/JE unchanged; legacy-desync location-floor pin (RED without
      Fix 1 — mutation-verified once).
- [ ] Gates: ruff clean; in-container pytest green 0 skipped; verify_gelato /
      verify_mousse / verify_inventory_race exit 0; full non-API sweep exit 0;
      push + all four CI jobs green.
