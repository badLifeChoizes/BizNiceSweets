# UAT — v1.0 milestone (PLUM)

Per **D-P7-5**, human click-through UAT is a milestone-close activity, run once at
`/zj:milestone` against the Vite dev server (**http://localhost:5173**, D-P7-1) with the
Podman stack up (`podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`;
API container `compose_api_1`, `alembic current` == `0008 (head)`). Log in as admin.

Draft parts available for BOM/flow testing: **ITEST-ASM-01**, **P100000** (Released parts
P00001/P00002/P99999 correctly hide edit affordances).

> **Both known blockers are cleared as of the 2026-07-09 milestone audit:**
> - Check 3 was guaranteed to fail — the Where-Used card labelled *every* parent "Direct parent"
>   (gap **G1**, fixed `63ea954`; backend now returns `via_part_number`). Proven live.
> - Check 7's Excel export 500'd — the API image lacked `openpyxl` (gap **G2**, fixed by rebuilding
>   `compose_api`). `/plum/export/excel` now returns 200 with a real `.xlsx`. **Rebuild the image if
>   you recreate the stack:** `podman-compose -f compose/compose.yml -f compose/compose.dev.yml build api`
>
> Everything below is now a genuine visual/affordance check — no known defect should block any of them.
> If a check fails, that is new information worth stopping for.

## Checklist

| # | Flow (req) | Status | Notes |
|---|---|---|---|
| 1 | BOM card — Add Part on a Draft revision → child in tree; expand/collapse (PLUM-04) | ✅ pass | Verified 2026-07-04 on ITEST-ASM-01; Add Part shows only when current revision is Draft |
| 8 | Released revision — BOM + cost read-only; frozen "Released at" cost (PLUM-03/06) | ✅ pass | Verified 2026-07-04; Add Part correctly hidden on Released parts |
| 2 | BOM flat view — shared sub-assembly = ONE row, summed Total Qty + Total BOM Cost footer (PLUM-05) | ⬜ todo | |
| 3 | Where-Used card — parents labeled "Direct parent" / "Indirect via {part}" (PLUM-06) | ⬜ todo | **G1 fixed `63ea954`** — was guaranteed to fail. Needs a 3-level BOM (A→B→C); open C, expect B "Direct parent" **above** A "Indirect via B" |
| 4 | AVL card — Add Vendor → pick SYERP vendor → link persists after refresh; Preferred badge (PLUM-07) | ⬜ todo | Phase-7 fix landed & code-verified |
| 5 | Cost & Margin — manual / roll-up / vendor-price sources (PLUM-08) | ⬜ todo | vendor-price source now reachable (PLUM-07 fixed) |
| 6 | Sale Price → Margin + Margin %; below-cost shows red (PLUM-09) | ⬜ todo | |
| 7 | Import/Export — JSON+Excel export; re-import → 0 errors → Confirm "No records deleted"; >10 MB rejected (PLUM-10) | ⬜ todo | **G2 fixed** — image rebuilt, `openpyxl 3.1.5` present; Excel export verified 200 + valid `.xlsx`. JSON round-trip and 10 MB guard already proven via API |
| 9 | AVL add completes with NO 500 / error toast (SC1) | ⬜ todo | proves `SyerpPartner`→`Partner` fix (`5c33ed8`) |
| 10 | Import w/ vendor reference previews + commits with NO 500 (SC1) | ⬜ todo | same fix; commit path passed a manual per-test run |
| 11 | After Confirm Import, Parts List updates without manual refresh (SC3) | ⬜ todo | proves cache-invalidation fix (`37b5f97`) |
| 12 | New Part with no part_number → fresh unique `P#####`, no duplicate-key error (SC2) | ⬜ todo | proves numeric part# fix (`1b8bfa1`); code-verified live (P100000→P100001) |

## What the machine already proved (2026-07-09 milestone audit)

The API-layer behaviour behind every check below is proven — see `.zj/MILESTONE-v1.0-AUDIT.md`
(66 live-DB assertions, 0 failures; 3-level BOM, flat dedup, exact Decimal roll-up `110.000000`,
margin 40 / −60, AVL persistence, JSON round-trip, 11 MB → 413). What remains is **the part a
machine cannot see**:

| Check | Residue only a human can confirm |
|---|---|
| 2 | shared sub-assembly is **one row**; the Total-BOM-Cost **footer** renders |
| 3 | the two labels read correctly and sort direct-above-indirect |
| 4 | the **Preferred badge** is visibly present |
| 6 | below-cost margin is actually **red** |
| 9, 10 | **no error toast appears** (absence is unobservable via API) |
| 11 | the Parts List visibly updates **without a manual refresh** (mechanism pinned by vitest) |
| 12 | essentially closable by machine — proven live (`P100000` → `P100001`) |

## If a check fails
Bisect against the atomic Phase-7 commits (`git log --oneline`) — each fix is one commit — or
across the milestone's phase history. Record the failing flow + observations here and open a
gap-closure task rather than blocking the milestone on unrelated flows.
