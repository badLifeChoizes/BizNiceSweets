# Task: chore-human-uat

**Branch:** `chore-human-uat` (cut off `c02d80b` per D-P5-9, then fast-forwarded to the
plan-carrying tip `4171605` — docs-only, code-identical to `c02d80b`; trivial deviation,
same pattern as Phases 3/4/13)
**Phase:** v4.0 Phase 5 — Human click-through UAT (NFR-8) — **final v4.0 phase**
**Plan:** `.zj/phases/05-human-uat/PLAN.md`

Every shipped UI flow — CORE, PLUM, SYERP (inventory/purchasing/GL/AP/AR/reports), MOUSSE,
CRUMB, GELATO — passes a documented human click-through against the hardened v4.0 stack,
with every defect fixed (blocker/major, pinned by an automated test) or homed to BACKLOG
with a `U#` ID.

**[OWNER]** tasks are click-through sittings run by the owner, not the engineer. Per the
plan's hand-back protocol, an engineer must never tick an owner check or infer a pass.

## Checklist

### Fixtures (SC2)

- [x] 0. Cut branch and checklist
- [x] 1. Seed-script skeleton: idempotency contract + manifest (`seed_uat_fixtures.py`)
- [x] 2. Seed the CORE + partners fixture layer
- [x] 3. Seed the PLUM fixture layer
- [x] 4. Seed the SYERP inventory + purchasing fixture layer
- [ ] 5. Seed the GELATO bins fixture layer
- [ ] 6. Seed the MOUSSE + CRUMB fixture layer
- [ ] 7. Seed the SYERP GL / AP / AR fixture layer
- [ ] 8. Prove the seed idempotent on a genuinely fresh volume

### Pre-flight (SC3)

- [ ] 9. Write the check → machine-assertion map (`PREFLIGHT.md`)
- [ ] 10. Add probes for the machine-unproven surfaces worth probing

### The checklist (SC1)

- [ ] 11. Author `.zj/UAT-v4.0.md`: preamble, fixture table, ordering rule, defect ledger
- [ ] 12. Author the CORE + PLUM checks
- [ ] 13. Author the SYERP checks
- [ ] 14. Author the MOUSSE, CRUMB and GELATO checks
- [ ] 15. Author the SC6 bin-picker checks, including the GELATO-off degraded path
- [ ] 16. Execute every command in the runbook once, at build time
- [ ] 17. Add pointer lines to the v1.0 and v2.0 UAT docs

### The SC8 validation check

- [ ] 18. Add the positive-adjust bin existence + membership check
- [ ] 19. Pin the membership check with a new `verify_gelato.py` scenario (G)

### The owner run (SC4/SC6) — read-only before mutating

- [ ] 20. **[OWNER]** CORE platform click-through
- [ ] 21. **[OWNER]** PLUM read-only click-through
- [ ] 22. **[OWNER]** PLUM mutating click-through
- [ ] 23. **[OWNER]** SYERP financial read-only click-through (GL, AP, AR, reports)
- [ ] 24. **[OWNER]** SYERP inventory read-only click-through
- [ ] 25. **[OWNER]** SYERP inventory mutating click-through + adjust/transfer bin pickers
- [ ] 26. **[OWNER]** Module-toggle propagation and the GELATO-off degraded path
- [ ] 27. **[OWNER]** SYERP purchasing click-through
- [ ] 28. **[OWNER]** MOUSSE click-through + the per-line issue bin picker
- [ ] 29. **[OWNER]** CRUMB click-through
- [ ] 30. **[OWNER]** GELATO click-through
- [ ] 31. **[OWNER]** SYERP money-loop tail click-through

### Close-out

- [ ] 32. Reconcile the checklist: zero `todo`, every defect homed
- [ ] 33. Run the full regression gate
- [ ] 34. Rebuild `frontend/dist` and the API container image
- [ ] 35. Bring the prod stack up on a fresh volume at :8000
- [ ] 36. **[OWNER]** Prod-stack deploy smoke at :8000
- [ ] 37. Bookkeeping: SRD NFR-8 and requirements-progress
- [ ] 38. Bookkeeping: ROADMAP, BACKLOG, DECISIONS, and archive the checklist

## Records

### Task 8 — fresh-volume idempotency manifests

*(pending)*

### Task 16 — runbook command execution log

*(pending)*

### Task 19 — scenario (G) RED signature

*(pending)*

### Task 33 — full regression gate results

*(pending)*
