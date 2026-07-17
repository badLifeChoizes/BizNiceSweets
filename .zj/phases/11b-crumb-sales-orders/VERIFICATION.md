# Verification: Phase 11b — CRUMB sales orders + soft-reservation
Date: 2026-07-17 | Commits: a8191cf..9503880 (branch feature-crumb-sales-orders)
Verdict: PASS

All six success criteria are empirically true at HEAD: 17/17 verify_*.py exit 0, the
concurrency crux is load-bearing and green, the frontend build + colocated tests pass, and
trial balance still nets zero (11b posts no GL / no InventoryTxn — confirmed by source read).
The only open items are documentation staleness (manager close-out stamps) and two
pre-recorded, by-design/cosmetic REVIEW-task8 findings — none blocks the phase goal.

## Criteria

### SC1 — SO model + migration + wiring — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `crumb_sales_order` + `crumb_sales_order_line` ORM | ✓ | ✓ | ✓ | models.py:320-431; both tables created, migration applied |
| migration 0014 chains off 0013 | ✓ | ✓ | ✓ | 0014_crumb_sales_orders.py:61-62 (`revision="0014"`, `down_revision="0013"`); `alembic current` → `0014 (head)`, `alembic heads` → `0014 (head)` |
| line item_id FK→syerp_inventory_item.id String(36) nullable | ✓ | ✓ | ✓ | models.py:408-410; migration:139,160-164 |
| qty_ordered/unit_price/qty_reserved Numeric(18,6) | ✓ | ✓ | ✓ | models.py:420-429; migration:147-150 |
| plum_part_id/description/sort_order | ✓ | ✓ | ✓ | models.py:412-417,430 |
| header auto-numbers SO-#### numeric-safe | ✓ | ✓ | ✓ | sales_orders.py:73-95 (regex `^SO-[0-9]+$` + `cast(substring(...,4), Integer).desc()`); verify_crumb_so.py scenario A boundary SO-0009→SO-0010 |

### SC2 — Direct SO CRUD + FSM — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| create SO in Draft | ✓ | ✓ | ✓ | sales_orders.py:141-200; router create endpoint (crumb:write) |
| lines editable only while Draft (409) | ✓ | ✓ | ✓ | `_get_draft_sales_order` 409 (sales_orders.py:401-408); verify_crumb_so.py scenario B |
| FSM Draft→Confirmed→Fulfilling→Closed +Cancelled from Draft/Confirmed | ✓ | ✓ | ✓ | SO_TRANSITIONS in _common.py; advance_sales_order_status:506-527 |
| invalid transitions → 422 | ✓ | ✓ | ✓ | :507-514; verify scenario C asserts draft→fulfilling skip, off-closed, fulfilling→cancelled all 422 |

### SC3 — Accepted-quote→SO conversion — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Accepted quote → Draft SO copying lines | ✓ | ✓ | ✓ | convert_quote_to_sales_order:233-320; verify scenario D asserts exact qty/price copy |
| item_id resolved from plum_part_id via InventoryItem | ✓ | ✓ | ✓ | `_resolve_item_id_for_part`:208-230 (first match ORDER BY id); scenario D asserts resolution |
| free-text/unlinked → item_id NULL | ✓ | ✓ | ✓ | :219-220 returns None; scenario D asserts part-less line item_id NULL |
| requires quote.status=="accepted" else 422 | ✓ | ✓ | ✓ | :260-267; scenario D asserts draft-quote convert → 422 |
| stamps source_quote_id + source_opportunity_id | ✓ | ✓ | ✓ | :275-276; scenario D asserts both stamped |

### SC4 — Soft-reservation crux — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| qty_reserved = min(qty_ordered, available) | ✓ | ✓ | ✓ | confirm_sales_order:624 `take = qty_ordered if qty_ordered < avail else avail` |
| available = on_hand − Σ qty_reserved across open (confirmed/fulfilling) SO lines | ✓ | ✓ | ✓ | :614-616; `_reserved_by_other_open_sos` filters `status.in_(("confirmed","fulfilling"))` and `SalesOrder.id != exclude_so_id` (:554-556) |
| never drives available negative | ✓ | ✓ | ✓ | :617 clamp `available if >0 else 0`; :625-626 `take` clamped ≥0; scenario E asserts 10−(6+4)==0 |
| over-ordered line confirms with derived shortage (not blocked) | ✓ | ✓ | ✓ | shortage derived in get_sales_order_detail:373; scenario E asserts min(8,4) cap + shortage 4, still confirms |
| non-stock line reserves 0 | ✓ | ✓ | ✓ | :620-622; scenario E asserts NULL line qty_reserved==0 |
| cancel of Confirmed SO releases reservations | ✓ | ✓ | ✓ | cancel_sales_order:660-662 zeroes each line; scenario E asserts release frees available back |
| concurrency: FOR UPDATE lock in sorted-id order BEFORE read | ✓ | ✓ | ✓ | :603-607 lock loop precedes :613-616 availability read; **scenario F** (asyncio.gather + Barrier, 2 independent sessions, on-hand 10 / each orders 7, ×5 iterations) asserts combined qty_reserved == 10 EXACTLY, never over, never negative — load-bearing (removing the lock fails it) |

Confirmed by source read: confirm/cancel write only `qty_reserved` + `status` — no InventoryTxn,
no journal entry (grep for InventoryTxn/journal/JournalEntry in sales_orders.py → empty). 11b
posts no GL, consistent with SC6 trial balance.

### SC5 — Audit + RBAC — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| every mutation writes attributable crumb.* audit at router | ✓ | ✓ | ✓ | router.py: sales_order.created/.line_added/.line_updated/.line_deleted/.confirmed/.cancelled/.status_changed, quote.converted_to_sales_order — all `write_audit` after commit with target_type="sales_order" |
| endpoints gated crumb:read/crumb:write | ✓ | ✓ | ✓ | every SO endpoint `require_permission("crumb:read"|"crumb:write")` |
| refused server-side (401/403), proven at HTTP | ✓ | ✓ | ✓ | verify_crumb_so_api.py: mutations 2xx writer / 403 reader / 401 anon; reads 200 reader / 403 noperm / 401 anon; audit rows for created/confirmed/cancelled/convert attributable to actor + target the SO |

### SC6 — Frontend + regression — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| SO list + create (Draft line editor) | ✓ | ✓ | ✓ | SalesOrders.tsx, SalesOrderCreateDialog.tsx, SalesOrderLineEditor.tsx |
| detail with ordered/reserved/shortage cols + FSM buttons | ✓ | ✓ | ✓ | SalesOrderDetail.tsx (reserved/shortage grid, Confirm/Cancel/Fulfill/Close gated by valid transitions) |
| Convert-to-SO on Accepted quote | ✓ | ✓ | ✓ | QuoteDetail.tsx:151 `{isAccepted && (...)}` + useConvertQuoteToSalesOrder |
| colocated Vitest green | ✓ | ✓ | ✓ | `npm run test -- routes/crumb --run` → 6 files, 9 tests passed |
| npm run build clean | ✓ | ✓ | ✓ | `tsc -b && vite build` → built in 531ms, exit 0 (only a chunk-size advisory) |
| all 17 verify_*.py exit 0 | ✓ | ✓ | ✓ | see Test suite below — OK ×17 |
| trial balance still nets zero | ✓ | ✓ | ✓ | verify_reports.py (trial-balance debits==credits, in_balance) + verify_gl.py both PASS; SO service posts no GL |

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC1 model/migration/numbering | verify_crumb_so.py scenario A + `alembic current`=0014 |
| SC2 CRUD + FSM | verify_crumb_so.py scenarios B, C |
| SC3 conversion | verify_crumb_so.py scenario D + verify_crumb_so_api.py convert case |
| SC4 reservation math | verify_crumb_so.py scenario E |
| SC4 concurrency crux | verify_crumb_so.py scenario F (asyncio.gather + Barrier, load-bearing) |
| SC5 audit + RBAC | verify_crumb_so_api.py (40 HTTP asserts) |
| SC6 frontend | routes/crumb/*.test.tsx (Vitest) + `npm run build` |
| SC6 no-GL / trial balance | verify_reports.py + verify_gl.py |

Every criterion is pinned by an automated check that a future phase's run would trip. No
feasible-but-missing test identified.

## Test suite
`for s in inventory purchasing e2e_p8 gl ap reports gl_api ap_api reports_api mousse mousse_api
part_numbering plum_vendor_paths crumb crumb_api crumb_so crumb_so_api; do
podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_$s.py; done`
→ OK inventory, purchasing, e2e_p8, gl, ap, reports, gl_api, ap_api, reports_api, mousse,
mousse_api, part_numbering, plum_vendor_paths, crumb, crumb_api, crumb_so, crumb_so_api = **17/17**.

Frontend: `npm run test -- routes/crumb --run` → 6 files / 9 tests passed.
`npm run build` → exit 0.

REVIEW-task8 follow-ups re-checked at HEAD:
- **#2 (was Low — "no SO router"): RESOLVED.** SO router now exists and is wired — 8 SO routes +
  `/crumb/quotes/{id}/convert` present (router introspection), each audited + RBAC-gated, proven
  by verify_crumb_so_api.py.
- **#1 (Medium, by-design D-V3-18): STILL TRUE, intentional.** Confirm locks only InventoryItem
  rows; a concurrent `post_adjustment(-N)` does not contend that lock, so availability can go
  negative along the stock-write-off axis. Explicitly out of scope (broader floor-guard lock →
  Phase 12). Recorded, not a phase-11b defect.
- **#3 (Low, cosmetic): STILL TRUE.** `fulfilling→closed` (advance_sales_order_status:524-527) does
  not zero qty_reserved; Closed is excluded from the OPEN sum so availability is correct, but a
  closed line's stored qty_reserved/shortage is stale. Cosmetic; no invariant impact.

## Gaps
1. **[minor] Documentation staleness (manager close-out).** SRD CRUMB-01 status still reads
   "partially verified (Phase 11a done; AC4 + AC3-tail pending Phase 11b)" (.zj/SRD.md:535);
   requirements-progress.md:72 still lists CRUMB-01 as inventory-free with AC4 deferred;
   MAP.md:39 says "Head is 0013" and its CRUMB service list omits `sales_orders`; CLAUDE.md
   suite table says "soft-reservation deferred to 11b." All now false — AC4 + AC3-tail delivered
   and verified. These are the standard post-verify close-out stamps the manager applies.
2. **[minor] Closed SOs retain stale qty_reserved** (sales_orders.py:524-527). Cosmetic — Closed
   excluded from availability sum, so no invariant impact; suggested fix: zero qty_reserved on
   close or add a comment that closed reserved values are intentionally frozen/uncounted. Matches
   REVIEW-task8 Finding #3.
3. **[minor / by-design] Soft-reservation not serialized against raw stock write-offs**
   (sales_orders.py confirm vs syerp inventory post_adjustment/post_transfer, no with_for_update).
   Explicitly D-V3-18 by-design; deferred to Phase 12 (GELATO issue path). No action for 11b.

No blocker or major gaps.

---

## Manager fix-loop (2026-07-17) — a blocker the verifier missed, now fixed

The verifier's PASS above was premature: it read the source and ran 17/17 green, but the
**code review (REVIEW.md) caught a BLOCKER the verify harness structurally hid** — the exact
"green-but-broken" pattern the 11a retro banked as the keeper.

**Blocker (FIXED, `fec334f`):** the direct SO create/add/update line paths copied `item_id`
verbatim and never bridged `plum_part_id → item_id`, while the frontend line editor sends a part
line as `plum_part_id` ONLY. Every UI-created SO line therefore persisted `item_id=NULL`, reserved
0 on confirm, and showed a false "Non-stock" badge + full shortage even with stock on hand — the
headline soft-reservation feature was dead through the UI (SC4 + SC6 broken for direct SOs, which
are first-class scope per D-V3-17). Conversion-created SOs were unaffected (they already resolved).
**Root cause of the blind spot:** `verify_crumb_so.py` passed `item_id=` directly, bypassing the UI
shape. **Fix:** folded resolution into `_resolve_and_validate_item_id` (reuses conversion's
`_resolve_item_id_for_part`), used by create/add/update. **Regression protection added:** new
load-bearing `(D2)` assertions drive a `plum_part_id`-only line through `create_sales_order` and
assert it resolves to the linked stock item (would have failed pre-fix).

**Re-verification after the fix (source changed → full re-run):** all **17/17** verify_*.py exit 0
(`verify_crumb_so.py` now 27 asserts incl. D2); trial balance still nets zero (verify_gl /
verify_reports green); frontend untouched by the backend-only fix.

**Open question, owner-decided:** convert has no idempotency guard (an Accepted quote converts to
unlimited duplicate SOs). Owner chose **fix-blocker-only**; logged to BACKLOG p3 + PLAN `## Noticed`.

**Minor doc-staleness gaps (verifier-flagged) — resolved at close-out:** SRD CRUMB-01 status +
Verified stamp, requirements-progress.md (new 11b row), ROADMAP 11b `[verified]`, MAP.md (CRUMB
`sales_orders` submodule + migration head 0014), CLAUDE.md suite table.

### Verdict (post-fix): PASS — CRUMB-01 complete (all ACs). Tag `zj/good-11b-crumb-sales-orders`.
