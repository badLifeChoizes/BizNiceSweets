# UAT — v1.0 milestone (PLUM)

Per **D-P7-5**, human click-through UAT is a milestone-close activity, run once at
`/zj:milestone` against the Vite dev server (**http://localhost:5173**, D-P7-1) with the
Podman stack up (`podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`;
API container `compose_api_1`, `alembic current` must == `0006`). Log in as admin.

Draft parts available for BOM/flow testing: **ITEST-ASM-01**, **P100000** (Released parts
P00001/P00002/P99999 correctly hide edit affordances).

## Checklist

| # | Flow (req) | Status | Notes |
|---|---|---|---|
| 1 | BOM card — Add Part on a Draft revision → child in tree; expand/collapse (PLUM-04) | ✅ pass | Verified 2026-07-04 on ITEST-ASM-01; Add Part shows only when current revision is Draft |
| 8 | Released revision — BOM + cost read-only; frozen "Released at" cost (PLUM-03/06) | ✅ pass | Verified 2026-07-04; Add Part correctly hidden on Released parts |
| 2 | BOM flat view — shared sub-assembly = ONE row, summed Total Qty + Total BOM Cost footer (PLUM-05) | ⬜ todo | |
| 3 | Where-Used card — parents labeled "Direct parent" / "Indirect via {part}" (PLUM-06) | ⬜ todo | |
| 4 | AVL card — Add Vendor → pick SYERP vendor → link persists after refresh; Preferred badge (PLUM-07) | ⬜ todo | Phase-7 fix landed & code-verified |
| 5 | Cost & Margin — manual / roll-up / vendor-price sources (PLUM-08) | ⬜ todo | vendor-price source now reachable (PLUM-07 fixed) |
| 6 | Sale Price → Margin + Margin %; below-cost shows red (PLUM-09) | ⬜ todo | |
| 7 | Import/Export — JSON+Excel export; re-import → 0 errors → Confirm "No records deleted"; >10 MB rejected (PLUM-10) | ⬜ todo | Excel export may 500 on stale image (missing openpyxl — BACKLOG), not a code regression |
| 9 | AVL add completes with NO 500 / error toast (SC1) | ⬜ todo | proves `SyerpPartner`→`Partner` fix (`5c33ed8`) |
| 10 | Import w/ vendor reference previews + commits with NO 500 (SC1) | ⬜ todo | same fix; commit path passed a manual per-test run |
| 11 | After Confirm Import, Parts List updates without manual refresh (SC3) | ⬜ todo | proves cache-invalidation fix (`37b5f97`) |
| 12 | New Part with no part_number → fresh unique `P#####`, no duplicate-key error (SC2) | ⬜ todo | proves numeric part# fix (`1b8bfa1`); code-verified live (P100000→P100001) |

## If a check fails
Bisect against the atomic Phase-7 commits (`git log --oneline`) — each fix is one commit — or
across the milestone's phase history. Record the failing flow + observations here and open a
gap-closure task rather than blocking the milestone on unrelated flows.
