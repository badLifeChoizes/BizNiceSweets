# DECISIONS — BizNiceSweets
Updated: 2026-07-16 (v3.0 "Customer & logistics" spec — D-V3-1..9)

Recovered decisions are marked `(recovered)` with their original source (now archived).
Numbering is append-only.


## Index

One line per decision, newest last. Entries below are append-only — regenerate this index
at milestone close, never hand-edit it. 73 decisions.

- **D-1:** Business domain = hybrid open-source business suite of 7 integrated suites (SYERP, PLUM, FLAN, MOUSSE, CRUMB, GELATO, CRISP), each usable…
- **D-2:** Manufacturing (facilities, work centers, routings) lives in MOUSSE, not PLUM — PLUM is product development; released products hand off to MOUSSE.…
- **D-3:** Modular monolith over one shared PostgreSQL database, SYERP as hub, modules integrate via foreign keys — simpler ops than microservices at this scale
- **D-4:** Full rewrite of all suites onto FastAPI + SQLAlchemy 2.0 + PostgreSQL / React + TypeScript + Tailwind + shadcn/ui, deployed via Podman Compose
- **D-5:** Self-hosted + offline-capable + open-core licensing — user ownership, no SaaS lock-in, permissive deps only.
- **D-6:** Dependency-first phase order (Foundation → Product Dev → Operations → Customer/Logistics → Quality); a value-first reorder was considered and…
- **D-7:** Milestone 1 = thin foundation + the PLUM port together, so the milestone ends with a usable tool, not just plumbing.
- **D-8:** Auth = PyJWT 2.13 + pwdlib[argon2] — not python-jose (CVEs), not passlib (abandoned)
- **D-9:** RBAC = User↔Role↔Permission M2M with module:action permission codes; UI gating is convenience only — backend 403 is the authz boundary.
- **D-10:** Seeds are idempotent select-before-insert, run at startup lifespan; migrations auto-apply on container boot (backend/entrypoint.sh).
- **D-11:** All PLUM cost/qty math uses Numeric(18,6)/Python Decimal — never float; export serializes Decimal as string.
- **D-12:** One-Released-revision-per-part enforced at DB level (partial unique index), not just in service code.
- **D-13:** Effective-cost resolution order = vendor price → manual cost → BOM roll-up → uncosted; cost snapshot frozen at release time.
- **D-14:** Import is two-step preview/commit, upsert-never-delete, stateless re-parse on commit, 10MB guard.
- **D-15:** Tailwind v4 requires shadcn color tokens registered via @theme inline in src/index.css, or panels render transparent app-wide.
- **D-ADOPT-1:** Project adopted into ZJ. .zj/ is the sole planning source of truth; the GSD system (.planning/) and the superseded program-planning docs…
- **D-ADOPT-2:** Phase 7 (close v1.0 gaps) adopted as-is from the GSD plans — same 4-plan scope; /zj:plan 7 translates rather than re-derives.
- **D-ADOPT-3:** Next milestone after v1.0 = SYERP extended + MOUSSE (dependency-first confirmed), ahead of the FLAN port and PLUM advanced.
- **D-ADOPT-4:** HTML prototypes (plum/app/plm_v54.html, flan/app/prj-mgmt-v24.html) are frozen reference only — no further development or bug fixes; they exist as…
- **D-ADOPT-5:** The unfinished suite-documentation and integration-spec items from docs/tasks/chore-architecture-planning.md are kept as backlog, not abandoned.
- **D-ADOPT-6:** Requirement-status corrections at adoption: docs/features/requirements-progress.md claims PLUM-04..10 "Complete" — contradicted by the live audit…
- **D-P7-1:** Phase-7 human-verify runs against the Vite dev server (http://localhost:5173) only — no frontend/dist / container-image rebuild task
- **D-P7-2:** Phase 7 stays scoped to the adopted 4 GSD plans plus one task to correct the root CLAUDE.md "Technology Stack" / "Architecture" sections (they…
- **D-P7-3:** bugfix-plum-v1-gaps is branched off chore-architecture-planning, not master as the PLAN originally stated
- **D-P7-4:** The PLUM live-DB test harness is fundamentally broken and its repair is deferred ("until it becomes blocking or it's asked for")
- **D-P7-5:** Human-UAT moves from a per-phase blocking gate to a milestone-close activity
- **D-P7-6:** part_number keeps no format constraint — String(50) / Field(None, max_length=50) stands; no regex pattern is added to PartCreate
- **D-P8-1:** Inventory and purchasing are SYERP, not MOUSSE or GELATO — reaffirmed when the owner questioned suite ownership at spec time
- **D-P8-2:** Hybrid item↔PLUM identity
- **D-P8-3:** Flat named stock locations only in SYERP inventory for v2.0; bins, zones, warehouse hierarchy, pick/pack/ship, and lot/serial are deferred to…
- **D-P8-4:** Moving weighted-average valuation
- **D-P8-5:** PO depth = Draft → Approve → Receive-into-inventory, no AP. Receiving posts SYERP-10 receipt transactions at PO unit cost; the workflow stops…
- **D-P8-6:** Both the inventory-item code and the PO number use a numeric-safe auto-generator (order by integer cast, never lexicographic MAX) — carrying…
- **D-P8-7:** v2.0 rejects issues/adjustments/transfers that would drive a location negative, and rejects PO over-receipt beyond ordered qty (both HTTP 4xx)
- **D-P8-8:** Phase 8 is one full-stack phase, delivered in wave order: inventory backend → inventory UI → purchasing backend → purchasing UI → verify
- **D-P8-9:** UI folded into the plan — no separate DESIGN.md
- **D-P8-10:** A single syerp:write gates all mutations, including PO approval (Draft→Approved); reads use syerp:read
- **D-P8-11:** Phase 8 branch = feature-syerp-inventory-purchasing cut from the current bugfix-plum-v1-gaps tip, NOT from master
- **D-P8-12:** Moving-average valuation is stored as a moving_avg_cost Numeric(18,6) column on syerp_inventory_item, recomputed transactionally on each receipt
- **D-P8-13:** Auto-generated code prefixes — inventory items ITEM-0001, purchase orders PO-0001 — both via the numeric-safe generator (regex-filter then…
- **D-P8-14:** A fresh deploy seeds one idempotent Main stock location (upsert-by-name, mirroring coa_seed.py) so receiving/adjustments work out-of-the-box
- **D-P8-15:** PO line qty_received is a stored accumulator on the line (POs are mutable working documents, not the immutable ledger), cross-checkable against…
- **D-M1-1:** The v1.0 tag is applied at the milestone HEAD, which contains Phase 8 (v2.0) work
- **D-M1-2:** Gaps G1 and G2 were fixed at milestone close rather than deferred (63ea954 + API image rebuild); G3 (broken live-DB pytest harness) stays deferred…
- **D-M1-3:** The v1.0 human UAT is run in rounds; round-1 defects are fixed before the tag rather than deferred
- **D-P9-1:** SYERP-12 GL goes to full subledger auto-posting (inventory receipts + AP docs post balanced JEs; statements derive from posted activity), not document-only aging — the largest of three options
- **D-P9-2:** AP depth = vendor bill matched to PO receipts with payments (Draft→Posted→Paid FSM, partial payments, overpayment rejected 4xx)
- **D-P9-3:** Posting model = GR/IR clearing (receipt Dr Inventory/Cr GR-IR; bill Dr GR-IR/Cr AP; payment Dr AP/Cr Cash) — receipt path gains an atomic JE side-effect; exact CoA account codes confirmed at /zj:plan
- **D-P9-4:** Accounts receivable deferred to the CRUMB milestone — SYERP-12 narrowed to AP+GL+reporting, AR split to new append-only SYERP-13
- **D-P9-5:** v2.0 definition of done unchanged — all three clauses kept, MOUSSE (Phase 10) still required to close; MOUSSE-01 expanded at Phase-10 planning
- **D-P9a-1:** JournalEntry/JournalLine are append-only immutable (no status column, mirror InventoryTxn); reversal = new entry via self-FK reversal_of_id; money Numeric(18,6); one of debit/credit per line
- **D-P9a-2:** Phase 9a branches `feature-syerp-gl-posting-engine` off master (not the Phase-8 branch) — the D-P8-11 "master behind" trap was resolved at the v1.0 ship (PR #1 FF-merged to master)
- **D-P9a-3:** GL endpoint paths = /syerp/gl/journal-entries[/{id}][/reverse] + /syerp/gl/accounts/{id}/register?from=&to=
- **D-P9a-4:** JE reversal swaps debit⇄credit, sets reversal_of_id, dated today (current period), optional memo — not a same-period reversal
- **D-P9a-5:** Receipt auto-post writes both po.received and gl.journal_posted audit rows so the GR/IR JE is attributable (AC8)
- **D-P9b-1:** Bill creation is receipt-driven — pick a vendor, system lists that vendor's unbilled received PO-line qty; user selects lines to bill (match at PO-line grain: unbilled qty = qty_received − Σ already-billed)
- **D-P9b-2:** Matched bill lines require exact match (billed = received qty × PO unit cost) so Dr GR/IR 2150 == Cr AP 2110 and GR/IR clears to zero; any variance is rejected 4xx (no PPV account in 9b)
- **D-P9b-3:** Bills also support non-PO lines (freight/services/direct expense) with a user-chosen EXPENSE/ASSET account per line, posting Dr <account> / Cr AP 2110
- **D-P9b-4:** Payments credit a selectable cash/bank asset account (default 1110 Cash); seed a second 1111 Bank – Checking so the choice is real; posting Dr AP 2110 / Cr <chosen>
- **D-P9b-5:** Bills auto-number BILL-#### (mirror _next_po_number) and capture the vendor's invoice reference; Draft→Posted→Paid FSM enforced server-side (PO_TRANSITIONS pattern); overpayment rejected 4xx (D-P8-7 guard)
- **D-P9b-6:** Payments modelled as Payment header + PaymentAllocation (one payment settles N bills); Payment.amount == Σ allocations; per-bill open balance = total − Σ allocation.amount
- **D-P9b-7:** AP endpoint paths = /syerp/ap/bills[/{id}][/post], /syerp/ap/unbilled-receipts?vendor_id=, /syerp/ap/payments (mirrors /syerp/gl/… of D-P9a-3)
- **D-P9b-8:** Phase 9b branches fresh `feature-syerp-ap-bills` off the verified 09a tip (tag zj/good-09a-gl-posting-engine), not continuing the 9a branch — each sub-phase its own branch/PR
- **D-P9c-1:** Add a real `Bill.bill_date` (Date, NOT NULL) via migration 0011 (add-nullable → backfill `created_at::date` → alter NOT NULL); `create_bill` accepts it (defaults to today), and the bill's posted JE `entry_date` is set from `bill.bill_date` so the AP subledger (aged by bill_date) and the 2110 control account (aged by entry_date) reconcile — AP aging buckets from bill_date
- **D-P9c-2:** Reports UI = one **Financial Reports** SYERP nav item (tabbed Trial Balance / P&L / Balance Sheet sharing date controls) + **AP Aging** as its own nav item near Bills
- **D-P9c-3:** Phase 9c branches fresh `feature-syerp-financial-reports` off the verified 09b tip (tag zj/good-09b-ap-bills-match-payments), per the per-sub-phase branch precedent (D-P9a-2/D-P9b-8)
- **D-P10-1:** Phase 10 = MOUSSE **materials-only work-order core**; routing/work-centers, labor/overhead costing (5120/5130), and the shop-floor execution view deferred to a follow-on MOUSSE phase — this core closes the v2.0 DoD
- **D-P10-2:** WO costing = **actual moving-average cost**, WIP account **1140 clears to zero** (Dr 1140/Cr 1130 on issue at each item's moving_avg; Dr 1130/Cr 1140 on finished-goods receipt at accumulated WIP); no standard-cost/variance account
- **D-P10-3:** Components consumed via an **explicit issue action** (distinct from completion), posting signed `issue` InventoryTxn rows under the per-location negative-stock floor guard
- **D-P10-4:** The `syerp/service.py` split (into cohesive submodules behind unchanged public functions) + MAP.md refresh are done as a **separate chore branch first**, verified green against existing verify scripts, BEFORE the MOUSSE build — kept out of the MOUSSE feature diff
- **D-P10-5:** A WO snapshots the **single-level (direct) BOM** of the part's Released revision into WO component lines at release (not a multi-level leaf explosion) — materials-only core has no nested WOs; each assembly level is its own WO; avoids the `load_flat_bom` sub-assembly/leaf ambiguity *(flagged for confirmation at handoff)*
- **D-P10-6:** MOUSSE is a **new module** (`backend/app/modules/mousse/`), self-registered in the registry, own router prefix `/mousse`, RBAC codes `mousse:read`/`mousse:write` (mirror syerp); it imports SYERP inventory/GL service functions rather than duplicating them
- **D-P10-7:** A component whose PLUM part has **no linked InventoryItem** (nullable `plum_part_id`) makes a WO unbuildable → reject at WO **release** (4xx), so an unissuable WO can't reach In-Progress
- **D-P10-8:** Chore branch and then `feature-mousse-work-orders` branch both cut off the **verified 09c tip** (tag `zj/good-09c-ap-aging-financial-statements`) — Phase 9 remains unmerged and the MOUSSE line stacks on it, per the per-phase branch precedent
- **D-P10-9:** WO completion requires every component fully issued (issued ≥ qty_required) UNLESS an explicit **manual override** flag is passed (audited); and the FSM adds an **On Hold** state — In Progress ⇄ On Hold — so a build can be paused mid-flight and resumed (owner requirement at plan handoff)
- **D-M2-1:** v2.0 milestone closed — DoD audited goal-backward against the running stack (13/13 live verify scripts, TB nets zero, subledgers tie); verdict clean bar one minor gap (G1, P&L empty-from 422) fixed at close (`2578ca5`); tagged `v2.0` at the `feature-mousse-work-orders` HEAD, which is still unmerged to master (the master-merge is the standing `/zj:ship` debt, per D-M1-1)
- **D-M2-2:** Human click-through UAT (`.zj/UAT-v2.0.md` + owed v1.0 round-2) deferred to a tracked post-tag BACKLOG task rather than blocking the tag — backend behavior is live-proven and the UI is wired + contract-checked by the milestone audit (D-P7-5 precedent); UAT becomes a pre-public-release gate
- **D-M2-3:** Version = `v2.0` (matches the roadmap milestone name "v2.0 Operations"; a major operations increment over v1.0)
- **D-M2-4:** Next milestone = Customer & logistics — CRUMB (CRM) + GELATO (WMS) + SYERP-13 (accounts receivable, split here at D-P9-4) — chosen over the FLAN port and PLUM-advanced
- **D-V3-1:** v3.0 DoD = three clauses — CRM & sales pipeline (CRUMB-01), warehouse fulfillment (GELATO-01), accounts receivable & sell-side books (SYERP-13)
- **D-V3-2:** Sell-side GL = two-event real books (ship Dr 5100 COGS/Cr 1130 Inventory at moving-avg; invoice Dr 1120 AR/Cr 4110 Revenue; receipt Dr Cash/Cr 1120 AR); all accounts already seeded, no clearing account (disjoint accounts, unlike buy-side GR/IR)
- **D-V3-3:** Customer invoices are shipment-driven (bill what shipped, matched at SO-line grain), mirroring the receipt-driven AP bill (D-P9b-1); partial shipments → partial invoices
- **D-V3-4:** Lot/serial tracking deferred to a follow-on GELATO phase — v3.0 fulfillment is quantity + cost only (mirrors carving routing out of MOUSSE, D-P10-1)
- **D-V3-5:** CRUMB depth = full lean chain (leads → opportunities → quotes → sales orders + customer communication log); no email integration or analytics
- **D-V3-6:** Quote/order line pricing = PLUM-derived default (part's released cost + editable markup), editable per line; no price-list entity (that is PLUM-16 territory)
- **D-V3-7:** GELATO scope = inbound (directed putaway-to-bin on receipts) + outbound (pick/pack/ship); bins introduced as a sub-level within SYERP's flat stock locations (realizes the D-P8-3 deferral)
- **D-V3-8:** A confirmed CRUMB sales order soft-reserves inventory (available = on-hand − reserved, never negative); shipping converts the reservation to an issue — chosen over decrement-only-at-ship
- **D-V3-9:** Module ownership — leads/opps/quotes/orders = CRUMB; bins/putaway/pick/pack/ship = GELATO; AR invoices/receipts/aging + all GL JEs = SYERP; CRUMB & GELATO are new modules importing SYERP inventory/GL service fns (D-P10-6 precedent)
- **D-V3-10:** Phase 11 (CRUMB-01) splits into 11a (CRM pipeline: leads/opps/quotes + comm log, no inventory) + 11b (sales orders + soft-reservation + accepted-quote→SO conversion), each planned/built/verified independently (9a/9b/9c precedent); 11a planned first
- **D-V3-11:** Soft-reservation stored as a `qty_reserved` accumulator on the sales-order line (11b), mirroring PO qty_received (D-P8-15); available(item) = derived on-hand − Σ open SO-line reservations; GELATO ship decrements it and posts the real issue txn — chosen over a separate append-only reservation ledger
- **D-V3-12:** CRUMB UI folded into the plan, no separate DESIGN.md (D-P8-9 precedent); opportunity pipeline is a per-stage grouped list (AC2), not a kanban; screens reuse the SYERP list/sheet/archive + FSM-detail template
- **D-V3-13:** Phase 11a branch = `feature-crumb-crm-pipeline` off master (master is the working tip since v2.0 shipped via PR #2, D-P9a-2 discipline); the docs-only `chore-spec-v3-customer-logistics` spec branch fast-forwards to master first
- **D-V3-14:** Quote-line markup default = a module constant `DEFAULT_MARKUP_PCT = Decimal("30")` in `crumb/service/_common.py`, per-line editable; no settings entity (D-V3-6 excludes a config/price-list surface)
- **D-V3-15:** `spawn_quote` (opportunity→quote) requires the opportunity to be in stage `won` (else 422) — mirrors AC2's "a Won opportunity can spawn a quote"; qualify/proposal/lost cannot spawn
- **D-V3-16:** Unlinked/free-text SO lines are non-stock — confirm with `qty_reserved=0` + a backorder indicator; the SO still confirms (D-V3-8 "not hard-blocked"), NOT a MOUSSE-D-P10-7-style hard reject
- **D-V3-17:** Phase 11b delivers BOTH direct SO creation (header+lines, editable while Draft) and accepted-quote→SO conversion — the SO is a first-class document (SRD AC4), not merely a conversion artifact
- **D-V3-18:** Reservation locking is narrow — lock only the contended `InventoryItem` row(s) FOR UPDATE (sorted-id order) on confirm; the broader shared SYERP floor-guard ledger lock (BACKLOG p2) defers to Phase 12 when GELATO ship writes real issue txns
- **D-V3-19:** Phase 11b branch = `feature-crumb-sales-orders` off the verified 11a tip (tag `zj/good-11a-crumb-crm-pipeline`, `efcf2e6`) — 11a is unmerged; 11b stacks on it (per-sub-phase branch precedent D-P10-8/D-P9b-8)
- **D-V3-20:** Verify-11b fix loop — fix the reservation blocker (direct-create SO lines never resolved `plum_part_id→item_id` → UI orders reserved 0; fixed `fec334f`); defer the quote→SO convert idempotency guard (non-idempotent for now, BACKLOG p3, revisit at Phase 13 invoicing)

## Product & Architecture

- **D-1 (recovered, 2025-12-20):** Business domain = hybrid open-source business suite of 7
  integrated suites (SYERP, PLUM, FLAN, MOUSSE, CRUMB, GELATO, CRISP), each usable standalone
  but integrating when present. *Source: archived `docs/decisions.md` #1.*
- **D-2 (recovered, 2025-12-20):** Manufacturing (facilities, work centers, routings) lives
  in MOUSSE, not PLUM — PLUM is product *development*; released products hand off to MOUSSE.
  *Source: archived `docs/decisions.md` #2.*
- **D-3 (recovered, 2025-12-21):** Modular monolith over one shared PostgreSQL database,
  **SYERP as hub**, modules integrate via foreign keys — simpler ops than microservices at
  this scale. *Source: archived `docs/ROADMAP.md`; realized in `backend/app/core/registry.py`.*
- **D-4 (recovered, 2025-12-21):** Full rewrite of all suites onto FastAPI + SQLAlchemy 2.0 +
  PostgreSQL / React + TypeScript + Tailwind + shadcn/ui, deployed via Podman Compose.
  Supersedes the earlier client-side DataService/localStorage plan (archived
  `docs/decisions.md` #4) — prototypes can't scale to a shared team system.
- **D-5 (recovered, 2025-12-21):** Self-hosted + offline-capable + open-core licensing —
  user ownership, no SaaS lock-in, permissive deps only.
- **D-6 (recovered, 2026-06-22):** Dependency-first phase order (Foundation → Product Dev →
  Operations → Customer/Logistics → Quality); a value-first reorder was considered and
  explicitly rejected. *Source: archived `.planning/PROJECT.md`.*
- **D-7 (recovered, 2026-06-22):** Milestone 1 = thin foundation + the PLUM port together,
  so the milestone ends with a usable tool, not just plumbing.

## Technical (recovered from GSD phase work, June 2026)

- **D-8 (recovered):** Auth = PyJWT 2.13 + pwdlib[argon2] — not python-jose (CVEs), not
  passlib (abandoned). Access token lives only in a module-level JS variable
  (`frontend/src/auth/token.ts`), never web storage; refresh via httpOnly cookie with
  single-flight axios 401 interceptor.
- **D-9 (recovered):** RBAC = User↔Role↔Permission M2M with `module:action` permission codes;
  UI gating is convenience only — backend 403 is the authz boundary.
- **D-10 (recovered):** Seeds are idempotent select-before-insert, run at startup lifespan;
  migrations auto-apply on container boot (`backend/entrypoint.sh`).
- **D-11 (recovered):** All PLUM cost/qty math uses `Numeric(18,6)`/Python `Decimal` — never
  float; export serializes Decimal as string.
- **D-12 (recovered):** One-Released-revision-per-part enforced at DB level (partial unique
  index), not just in service code.
- **D-13 (recovered):** Effective-cost resolution order = vendor price → manual cost → BOM
  roll-up → uncosted; cost snapshot frozen at release time.
- **D-14 (recovered):** Import is two-step preview/commit, upsert-never-delete, stateless
  re-parse on commit, 10MB guard.
- **D-15 (recovered):** Tailwind v4 requires shadcn color tokens registered via
  `@theme inline` in `src/index.css`, or panels render transparent app-wide.

## Adoption decisions (2026-07-04)

- **D-ADOPT-1:** Project adopted into ZJ. `.zj/` is the sole planning source of truth; the
  GSD system (`.planning/`) and the superseded program-planning docs (`docs/ROADMAP.md`,
  `docs/decisions.md`) are archived under `archive/`. Requirement IDs (CORE/SYERP/PLUM/FLAN)
  carried over verbatim into `.zj/SRD.md`.
- **D-ADOPT-2 (owner):** Phase 7 (close v1.0 gaps) adopted **as-is** from the GSD plans —
  same 4-plan scope; `/zj:plan 7` translates rather than re-derives.
- **D-ADOPT-3 (owner):** Next milestone after v1.0 = **SYERP extended + MOUSSE**
  (dependency-first confirmed), ahead of the FLAN port and PLUM advanced.
- **D-ADOPT-4 (owner):** HTML prototypes (`plum/app/plm_v54.html`, `flan/app/prj-mgmt-v24.html`)
  are **frozen reference only** — no further development or bug fixes; they exist as
  domain-logic reference for porting.
- **D-ADOPT-5 (owner):** The unfinished suite-documentation and integration-spec items from
  `docs/tasks/chore-architecture-planning.md` are kept as backlog, not abandoned.
- **D-ADOPT-6:** Requirement-status corrections at adoption: `docs/features/requirements-progress.md`
  claims PLUM-04..10 "Complete" — contradicted by the live audit (PLUM-07/10 broken at
  runtime, rest unverified). SRD statuses follow the code/audit, not the progress doc;
  reconciliation is Phase 7 scope.

## Phase 7 planning (2026-07-04)

- **D-P7-1 (owner):** Phase-7 human-verify runs against the **Vite dev server (http://localhost:5173)
  only** — no `frontend/dist` / container-image rebuild task. *Why:* the served :8000 bundle
  predates Phase 3 (stale UI), but Vite dev always reflects current source, so it verifies the
  fixes without build work; the stale production bundle stays a separate backlog item
  ("Rebuild frontend/dist + container image").
- **D-P7-2 (owner):** Phase 7 stays scoped to the adopted 4 GSD plans **plus one task** to
  correct the root `CLAUDE.md` "Technology Stack" / "Architecture" sections (they still describe
  the frozen vanilla-JS prototypes — "No server-side runtime", "no npm"). *Why:* cheap, sits
  right next to the work, and reduces future-agent confusion. CI (the process gap that let the
  `SyerpPartner` bug ship) was explicitly **not** folded in — it stays a p1 backlog item for
  its own phase, honoring D-ADOPT-2 (adopt Phase 7 as-is).

## Phase 7 build (2026-07-04)

- **D-P7-3 (owner, at build):** `bugfix-plum-v1-gaps` is branched off
  **`chore-architecture-planning`**, not `master` as the PLAN originally stated. *Why:* `master`
  (HEAD `f4e2bd3`, 2025-12-20) predates the entire re-platform — it contains only the legacy
  prototypes and has **no `backend/`, `frontend/`, or `.zj/`**. All 212 commits of real work,
  including the code Phase 7 fixes and the plan itself, live on `chore-architecture-planning`
  (a strict superset of master). Branching off master would give an empty tree with nothing to
  fix. Eventual integration of `chore-architecture-planning` → `master` is a separate concern
  outside Phase 7. The plan's dedicated-branch intent is preserved; only the base changed.

- **D-P7-4 (owner, at build):** The PLUM live-DB test harness is **fundamentally broken and its
  repair is deferred** ("until it becomes blocking or it's asked for"). Discovered at build: the
  `skip_if_no_db` suite has always silently skipped (broken psycopg2-URL probe), and once the
  probe is fixed all 33 PLUM tests fail on a module-level async-engine/event-loop mismatch, plus
  missing `admin-user` seeding and no per-test isolation (full root-cause list in BACKLOG.md p1).
  Fixing it is real test-infra work outside the adopted 4-plan scope. *Consequence:* **SC4 is
  relaxed** for Phase 7 — the PLUM fixes are proven by the Task 6 human-verify at :5173 (D-P7-1,
  regression checks 9–12 cover SC1/SC2/SC3 end-to-end) plus lightweight standalone async scripts
  run against live Postgres, **not** by the pytest suite. The `pytest tests/plum/` "green" clause
  in Tasks 1/2/5 Done-when is superseded by these. Harness repair tracked as BACKLOG p1.

- **D-P7-5 (owner, at build):** **Human-UAT moves from a per-phase blocking gate to a
  milestone-close activity.** Under the ZJ workflow the atomic, bisectable commit history makes
  regressions cheap to localize, so full click-through UAT runs once at `/zj:milestone` rather
  than blocking each phase. *Consequence for Phase 7:* Task 6 is unblocked — the two checks run
  (check 1 BOM-add-on-Draft, check 8 Released-read-only) **passed**; the remaining checks
  (2–7, 9–12) are captured as TODO in `.zj/UAT-v1.0.md` for the v1.0 milestone UAT. Task 7
  reconciles traceability honestly against this: the code fixes are marked on their
  automated/standalone-verified evidence, and flow-level UI confirmation is annotated
  "human-UAT deferred to v1.0 milestone" rather than claimed complete (preserves SC5 — nothing
  marked Complete on an unrun check).

## Phase 7 retro (2026-07-09)

- **D-P7-6 (owner):** **`part_number` keeps no format constraint** — `String(50)` /
  `Field(None, max_length=50)` stands; no regex pattern is added to `PartCreate`. A pattern would
  reject part numbers real users legitimately rely on. *Consequence:* the auto-numbering ORDER BY
  must stay `cast(..., Numeric)`, which cannot overflow for any 50-char digit string. **Do not
  "simplify" the cast back to `Integer` or `BigInteger`** — that reintroduces the persistent-500 DoS
  fixed in `7562a02`. Pinned by `backend/scripts/verify_part_numbering.py` scenario 3 and stated in
  the `generate_part_number` docstring.

- **Won't fix (Phase 7 `Noticed`):** dev-DB row `P-COMMIT-AVL-1` (left by an import-commit test) has
  no non-obsolete revision, so its PartDetail renders without the BOM card. This is dev-database data
  hygiene on a disposable volume, not a code defect — no backlog entry, no fix.

## v2.0 / Phase 8 spec — SYERP-10/11 expansion (2026-07-05)

- **D-P8-1 (owner):** **Inventory and purchasing are SYERP, not MOUSSE or GELATO** — reaffirmed
  when the owner questioned suite ownership at spec time. SYERP is the ERP hub and owns the
  inventory *ledger* (what is stocked, how much, what it's worth) and *procurement* (POs to
  vendors); MOUSSE *consumes* inventory + PLUM BOMs to build (later); GELATO adds *physical*
  warehouse detail (bins, receiving floor, pick/pack/ship, lot/serial) on top of SYERP inventory
  (later). Both MOUSSE and GELATO depend on SYERP inventory existing first — hence the
  dependency-first sequencing (D-6). *Source: PROJECT.md ("SYERP … inventory — the hub"), PRD-7.*
- **D-P8-2 (owner):** **Hybrid item↔PLUM identity.** An inventory item is its own SYERP record
  with a **nullable** FK to a PLUM part. Rationale: a real shop stocks non-designed goods (raw
  materials, packaging, consumables) that are not PLUM parts, and SYERP inventory should not
  hard-depend on the PLUM module being enabled. Rejected: "every item is a PLUM part" (can't
  stock non-parts; hard PLUM coupling) and "independent item master" (duplicates part data,
  weakens the MOUSSE BOM-consumption story).
- **D-P8-3 (owner):** **Flat named stock locations only** in SYERP inventory for v2.0; bins,
  zones, warehouse hierarchy, pick/pack/ship, and lot/serial are **deferred to GELATO-01** to
  avoid building the warehouse layer twice. Rejected: single implicit location (needs a schema
  change the moment locations arrive) and a full bin hierarchy now (overlaps GELATO scope).
- **D-P8-4 (owner):** **Moving weighted-average valuation.** Each receipt updates the item's
  moving-average unit cost; on-hand value = qty × avg cost; all math Decimal/`Numeric(18,6)`
  (D-11). Gives MOUSSE a real inventory cost to consume and flow back to SYERP (PRD-7 acceptance
  signal). Rejected: quantity-only (defers the cost-flow capability MOUSSE needs) and
  standard-cost-from-PLUM (misses purchase-price variance).
- **D-P8-5 (owner):** **PO depth = Draft → Approve → Receive-into-inventory, no AP.** Receiving
  posts SYERP-10 receipt transactions at PO unit cost; the workflow stops before vendor-invoice
  matching and payment, which stay SYERP-12. Rejected: pulling basic AP invoice-match forward
  (scope growth into SYERP-12) and PO-history-only with no receiving integration (weakest
  integration; would need manual stock adjustments).
- **D-P8-6:** Both the inventory-item `code` and the PO number use a **numeric-safe
  auto-generator** (order by integer cast, never lexicographic `MAX`) — carrying forward the
  PLUM `generate_part_number` defect lesson (Phase 7 `1b8bfa1`) so the same digit-boundary bug
  is not re-introduced in a new generator.
- **D-P8-7:** v2.0 **rejects** issues/adjustments/transfers that would drive a location negative,
  and **rejects** PO over-receipt beyond ordered qty (both HTTP 4xx). Backorder / negative-stock
  policy and over-receipt tolerance are deferred — sensible strict defaults now, revisited if a
  real workflow needs them.

## Phase 8 planning (2026-07-05)

- **D-P8-8 (owner):** Phase 8 is **one full-stack phase**, delivered in wave order: inventory
  backend → inventory UI → purchasing backend → purchasing UI → verify. PO receiving is built and
  verified on a working inventory ledger; the receipt→moving-average integration is proven
  end-to-end. Rejected: split by capability (inventory Phase 8 / purchasing Phase 9) and
  backend-first-UI-later — owner wants a complete, demoable operations slice in one phase.
- **D-P8-9 (owner):** **UI folded into the plan — no separate DESIGN.md.** Item and location CRUD
  reuse the existing SYERP list+sheet+archive template (`Vendors.tsx`/`Customers.tsx`/`PartnerSheet`);
  the novel screens (on-hand-by-location, adjust/transfer, PO create/approve/receive) are specified
  directly in the tasks. *Why:* the SYERP CRUD template is a strong enough starting point that a
  separate design pass wasn't worth the step.
- **D-P8-10 (owner):** **A single `syerp:write` gates all mutations, including PO approval**
  (Draft→Approved); reads use `syerp:read`. No separate approve permission. Approver identity is
  captured via the audit event (`po.approved` + `approved_by`). *Why:* keeps Phase-8 RBAC scope
  tight and matches the current SYERP pattern; approval-authority separation can be added later
  without a data migration. Rejected: a distinct `syerp:approve` code.
- **D-P8-11 (owner):** Phase 8 branch = **`feature-syerp-inventory-purchasing` cut from the current
  `bugfix-plum-v1-gaps` tip**, NOT from `master`. *Why:* `master` (HEAD `f4e2bd3`, 2025-12-20)
  predates the entire re-platform and contains no `backend/`/`frontend/`/`.zj/` (the same trap
  documented in D-P7-3); only the current tip carries the real codebase plus the Phase-7 fixes.
  Phase 8 therefore builds atop unmerged Phase 7 — consistent with the owner's choice to plan 8
  before formally closing v1.0.
- **D-P8-12 (owner):** **Moving-average valuation is stored** as a `moving_avg_cost Numeric(18,6)`
  column on `syerp_inventory_item`, recomputed transactionally on each receipt. On-hand *quantity*
  stays a derived `SUM(quantity)` over the immutable ledger, and every receipt's `unit_cost` is
  retained in the ledger, so the average remains auditable/replayable — a mutated-by-design column,
  not a violation of the "on-hand is derived" rule (D-P8-4). Rejected: full ledger-replay on every
  read (more code, slower reads, no offsetting benefit at single-shop scale).
- **D-P8-13 (owner):** Auto-generated code prefixes — inventory items **`ITEM-0001`**, purchase
  orders **`PO-0001`** — both via the numeric-safe generator (regex-filter then integer-cast order,
  D-P8-6), distinct from partner `P-0001`.
- **D-P8-14 (owner):** A fresh deploy **seeds one idempotent `Main` stock location** (upsert-by-name,
  mirroring `coa_seed.py`) so receiving/adjustments work out-of-the-box. Rejected: no seed (adds a
  manual setup step before any stock movement).
- **D-P8-15:** PO line `qty_received` is a **stored accumulator** on the line (POs are mutable
  working documents, not the immutable ledger), cross-checkable against `SUM(quantity)` of the
  receipt transactions whose `source_id` = the line id.

## v1.0 milestone close (2026-07-09)

- **D-M1-1 (owner):** **The v1.0 tag is applied at the milestone HEAD, which contains Phase 8
  (v2.0) work.** *Why:* Phase 7's blocker fix (`7562a02`), its guard (`8975eeb`), and the
  milestone-audit fix (`63ea954`) were all committed *after* Phase 8's 30 commits, because Phase 8
  was planned and built on the unclosed Phase-7 branch (D-P8-11). No commit in history is
  therefore a clean v1.0 tree. A cherry-pick of the three fixes onto the last pre-Phase-8 commit
  was considered and **rejected** — it would duplicate commits and create a divergent line for
  cosmetic tag purity. *Consequence:* checking out `v1.0` yields inventory and purchasing too;
  the changelog says so explicitly. **Do not start the next milestone's build on an unclosed
  milestone's branch** — this is the concrete cost of having done so.
- **D-M1-2 (owner):** **Gaps G1 and G2 were fixed at milestone close rather than deferred**
  (`63ea954` + API image rebuild); **G3 (broken live-DB pytest harness) stays deferred** to
  BACKLOG p1 / D-P7-4. *Why:* G1 sat inside the definition of done ("multi-level BOMs") and
  guaranteed a UAT failure; G2 was a stale-image artifact with no code change required. G3 is
  test-infrastructure work whose absence is compensated, for now, by the `verify_*.py` live-DB
  gates and the Vitest suite — both of which do run.

- **D-M1-3 (owner):** **The v1.0 human UAT is run in rounds; round-1 defects are fixed before the
  tag rather than deferred.** Round 1 (2026-07-11) passed checks 3/5/6/12 and surfaced three UI
  defects the backend proofs and the machine audit had both missed — D1 (flat-BOM cost footer
  triple-counted sub-assemblies: 280 vs 110), D2 (AVL "Add Vendor" 500 on a duplicate/soft-deleted
  link — a user-triggerable crash), D3 (import file picker entirely non-functional: no drag handler,
  decorative Choose-File button). All three sit inside the v1.0 definition of done (BOM cost roll-up,
  vendor links, import/export), so all three were fixed now (`a88431c`) with regression tests and
  live proof, and the owner re-runs checks 2, 4/9, 7, 10, 11 before tagging. *Why fix not defer:* a
  milestone that ships a user-triggerable 500 and a dead import button is not "done" against its own
  definition. **Reinforces the G1 lesson:** "API verified live" never transfers to the UI that
  consumes it — five of the twelve UAT checks were closable only by a human in a browser, and three
  of them exposed real bugs.

## Phase 9a planning — GL posting engine split + build decisions (2026-07-11)

Phase 9 (SYERP-12) is split into three ZJ sub-phases at planning (owner-confirmed, extends
D-P9-1's "expect to split"): **9a** = GL posting engine + receipt auto-post + manual journal UI
(covers SYERP-12 AC1/AC2/AC3 and AC8/AC9 for that surface); **9b** = AP bills/match/payments
(AC4/AC5); **9c** = AP aging + financial statements (AC6/AC7). 9a is planned/built/verified
first. GR/IR account confirmed as new seeded **2150 "Goods Received Not Invoiced (GR/IR)"**,
LIABILITY under Current Liabilities 2100 (D-P9-3 left the codes open; Inventory 1130, AP 2110,
Cash 1110 already exist). Manual journal-entry UI is IN scope for 9a (owner chose it over
auto-post-only), and UI is folded into the plan with no separate DESIGN.md (D-P8-9 precedent).

- **D-P9a-1 (owner-default):** `JournalEntry` / `JournalLine` are **append-only and immutable** —
  no mutable status column; a posted entry is the only state a row can be in, mirroring the
  `InventoryTxn` ledger. Corrections are **reversing entries** (new row, self-FK `reversal_of_id`),
  never edits or deletes. Money is `Numeric(18,6)`/`Decimal` (D-11); each line carries exactly one
  of debit/credit, both ≥ 0. *Why:* audit-trail/traceability is first-class (medical-device origin),
  and it reuses the proven Phase-8 ledger pattern rather than inventing a mutable GL.
- **D-P9a-2 (owner, corrects a stale premise):** Phase 9a branches **`feature-syerp-gl-posting-engine`
  off `master`**, not off the Phase-8 branch. The architect draft assumed master was 263 commits
  behind (D-P8-11), but that debt was **resolved at the v1.0 ship (2026-07-11)** — PR #1
  fast-forward-merged `feature-syerp-inventory-purchasing` → `master`, so master now carries
  Phases 1–8 (verified: `backend/`/`frontend/`/`.zj/` tracked on master, HEAD `f2466d3`). The
  D-P8-11 trap ("branch off the working tip, not master") no longer applies because **master is now
  the working tip**. *Consequence:* the next-milestone-on-unclosed-branch cost noted in D-M1-1 is
  paid off; 9a builds on a clean, merged master.
- **D-P9a-3 (owner-default):** GL endpoint paths — `POST/GET /syerp/gl/journal-entries`,
  `GET /syerp/gl/journal-entries/{id}`, `POST /syerp/gl/journal-entries/{id}/reverse`,
  `GET /syerp/gl/accounts/{id}/register?from=&to=` (existing `GET /syerp/gl/accounts` unchanged).
- **D-P9a-4 (owner-default):** JE **reversal swaps debit⇄credit** on every line, sets
  `reversal_of_id`, takes an optional memo (default `"Reversal of {id}"`), and is **dated today**
  (lands in the current period), not back-dated to the original. Revisit if same-period reversal is
  later needed.
- **D-P9a-5 (owner-default):** The PO-receive endpoint writes **both `po.received` and
  `gl.journal_posted`** audit rows (after `receive_line` commits), so the auto-posted GR/IR JE is
  attributable per AC8 — chosen over folding the JE id into the `po.received` detail (less
  discoverable).

## Phase 9b plan — AP bills, PO match & payments (2026-07-11, SYERP-12 AC4/AC5)

- **D-P9b-1 (owner):** **Bill creation is receipt-driven.** The user picks a vendor; the system
  lists that vendor's PO lines with **unbilled received quantity** (`qty_received − Σ already-billed
  qty`, matched at PO-line grain) and the user selects which to bill. Chosen over free-form keyed
  lines with an optional match picker. *Why:* least keying, hardest to mis-key, and matches the
  procure-to-pay loop D-P9-2 built PO receiving for. Matched bill lines are the GR/IR clearing legs.
- **D-P9b-2 (owner):** **Matched bill lines require an exact match** — a matched line bills exactly
  the unbilled received qty × the PO line's unit cost, so the posting is **Dr GR/IR 2150 == Cr AP
  2110** and GR/IR clears to zero. A billed amount/qty that diverges from the received value is
  **rejected 4xx**. Chosen over allowing price/qty variance to a new Purchase Price Variance account.
  *Why:* simplest correct MVP that keeps GR/IR exactly clearing with no new account; real invoice
  discrepancies are keyed as a separate non-PO expense/adjustment line (D-P9b-3). Revisit (add a PPV
  account + 3-line variance posting) if the shop hits routine price variances.
- **D-P9b-3 (owner):** **Bills also carry non-PO lines** (freight, services, direct expenses not
  tied to a receipt), each with a **user-chosen GL account** (any EXPENSE or ASSET), posting
  **Dr <chosen account> / Cr AP 2110**. Chosen over PO-match-only. *Why:* real vendor invoices mix
  received goods with freight/fees on one document; this realizes AC4's "Dr Inventory/Expense
  (unmatched)" branch. A bill is therefore matched lines (Dr GR/IR) + non-PO lines (Dr chosen), all
  Cr AP for the total.
- **D-P9b-4 (owner):** **Payments credit a selectable cash/bank asset account**, chosen from the
  ASSET accounts under Current Assets 1100, **defaulting to 1110 Cash**; a new **1111 Bank –
  Checking** is seeded so the choice is real. Posting is **Dr AP 2110 / Cr <chosen>**. Chosen over
  hardcoding 1110. *Why:* a shop pays from cash and from a bank account and the books should show
  which; the picker is cheap given the register/statements (9c) will report per-account.
- **D-P9b-5 (owner-default, confirm if wrong):** Bills **auto-number `BILL-####`** (mirroring the
  `_next_po_number` numeric-safe generator) and capture the vendor's **invoice reference** as a
  free-text field; the **Draft→Posted→Paid FSM is enforced server-side** via a `BILL_TRANSITIONS`
  mapping (PO_TRANSITIONS pattern — invalid transitions 4xx, not just hidden in the UI); a bill
  **auto-advances to Paid** when its open balance (billed − paid) reaches zero, and a payment that
  would drive it **negative is rejected 4xx** (D-P8-7 over-receipt guard pattern).
- **D-P9b-6 (architect call, adopted):** **Payments = `Payment` header + `PaymentAllocation` rows**
  (one payment settles N bills). `Payment.amount` must equal `Σ` its allocations; a bill's open
  balance derives as `total − coalesce(Σ allocation.amount, 0)`. *Why:* AC5 says "against one or
  more posted bills" — a real cheque/transfer clears several vendor invoices at once, and the
  allocation grain is exactly what the open-balance and overpayment guard need. A flat
  1-payment→1-bill column would force N payments per cheque and re-model later.
- **D-P9b-7 (architect call, adopted):** **AP endpoint paths** = `POST/GET /syerp/ap/bills`,
  `GET /syerp/ap/bills/{id}`, `POST /syerp/ap/bills/{id}/post`,
  `GET /syerp/ap/unbilled-receipts?vendor_id=`, `POST/GET /syerp/ap/payments` — mirroring the
  `/syerp/gl/…` shape of D-P9a-3.
- **D-P9b-8 (owner, 2026-07-11):** **Phase 9b branches fresh `feature-syerp-ap-bills` off the
  verified 09a tip** (current `feature-syerp-gl-posting-engine` HEAD, tagged
  `zj/good-09a-gl-posting-engine`), rather than continuing on the 9a branch. *Why:* 9b stacks
  cleanly on 9a's commits, each Phase-9 sub-phase keeps its own branch for a separate ship/PR, and
  the 9a branch stays closed at its tag — matching the "branch off the working tip" discipline
  (D-P8-11). Chosen over entangling two phases' history on one branch.

## v2.0 / Phase 9 spec — SYERP-12 expansion (2026-07-11)

- **D-P9-1 (owner):** **The GL goes to full subledger auto-posting, not document-only aging.**
  Offered three depths — (A) AP/AR documents + aging with the GL left a manual chart, (B) add a
  manual journal + statements, (C) **inventory receipts and AP documents auto-post balanced
  journal entries to the GL, with statements derived from posted activity** — the owner chose
  **(C)**. *Why:* the shop's real financial position (Trial Balance / P&L / Balance Sheet) should
  be derivable from the system that already records receipts and bills, not reconstructed by hand;
  "reporting on the GL" is empty if nothing posts to the GL. *Cost accepted:* this is the largest
  of the three options and makes Phase 9 heavy — a general-journal posting engine **plus** AP
  **plus** reporting. Mitigation: expect to split Phase 9 into sub-phases at `/zj:plan` (engine →
  AP → reporting), same as MOUSSE is flagged to split.
- **D-P9-2 (owner):** **AP depth = vendor bill matched to PO receipts, with payments.** Chosen over
  (bill+payments no match) and (bill records + a paid flag). *Why:* Phase 8 already built PO
  receiving; matching the bill back to the receipt closes the procure-to-pay loop and is what makes
  three-way reconciliation and the GR/IR clearing account meaningful. Bills carry a
  Draft→Posted→Paid FSM enforced server-side (SYERP-11.1 pattern); payments can be partial;
  overpayment is rejected 4xx (D-P8-7 guard pattern).
- **D-P9-3 (owner-default, confirm at planning):** **Posting model = GR/IR clearing.** A PO receipt
  posts **Dr Inventory / Cr GR/IR**; posting the matched vendor bill posts **Dr GR/IR / Cr AP**;
  a payment posts **Dr AP / Cr Cash**. *Why:* this is the standard three-account procure-to-pay
  flow and keeps received-not-yet-invoiced value visible in one clearing account; it also means the
  Phase-8 receipt path gains a JE side-effect (stock txn + JE in one atomic transaction). *Open:*
  the exact seeded account codes (Inventory asset, GR/IR, AP control, Cash/Bank, expense fallback)
  are a `/zj:plan` detail — the CoA seed (`coa_seed.py`) must include them. Flagged for owner
  confirmation at planning, not locked here.
- **D-P9-4 (owner):** **Accounts receivable is deferred to the CRUMB milestone.** The original
  SYERP-12 ("AP/AR and financial reporting") is **narrowed to AP + GL + reporting**; AR is split
  out to a new append-only placeholder **SYERP-13**, delivered with CRUMB. *Why:* AR invoices
  belong downstream of sales orders, which do not exist yet — keying standalone customer invoices
  now would be throwaway UI, and Phase 9 is already large (D-P9-1). AR still traces PRD-7 but rides
  the PRD-8 (CRUMB) milestone where its upstream data lives.
- **D-P9-5 (owner):** **v2.0 definition of done is unchanged — all three clauses kept.** v2.0
  ("Operations") still requires MOUSSE work orders (Phase 10) that consume PLUM BOMs and inventory
  to close; Phase 9 (GL+AP+reporting) is a step toward it, not the finish line. Rejected: closing
  v2.0 at Phase 9 and moving MOUSSE to a v3.0. *Why:* "Operations" without manufacturing execution
  is gutted; the whole dependency-first ordering (D-6) exists to reach work orders. **MOUSSE-01
  stays a coarse placeholder** and is expanded via `/zj:spec` at Phase-10 planning — the same
  just-in-time expansion used for SYERP-10/11 (Phase 8) and SYERP-12 (Phase 9).

### Phase 9c (AP aging + financial statements — planned 2026-07-12)

- **D-P9c-1 (owner):** **Add a real `Bill.bill_date`.** The 09b `Bill` model carries only
  `created_at` (system entry timestamp) and `posted_at`; AC6 ages open bills "from bill dates."
  Add `bill_date` (SQLAlchemy `Date`, NOT NULL) via **migration 0011** — add nullable → backfill
  existing rows `created_at::date` (server-side) → alter NOT NULL, so the NOT-NULL add is safe on a
  populated table. `create_bill` accepts `bill_date` (defaults to `date.today()` when omitted, so
  existing 09b callers/tests are unchanged), and the create dialog gains an optional bill-date
  field. **Crucially, `post_bill` sets the bill's JE `entry_date` from `bill.bill_date`** (was
  `date.today()`), so the AP subledger (aged by `bill_date`) and the 2110 Accounts-Payable control
  account (aged by `entry_date`) share one date basis and the AC6 tie-out (aging grand total ==
  derived 2110 balance) holds exactly. *Why over reusing `created_at`:* a bill entered late for an
  old invoice would otherwise age in the wrong bucket; the medical-device audit posture wants the
  true invoice date, and the column is cheap now vs. retrofitting later. *Rejected:* bucket by
  `created_at::date` (no schema change) — conflates entry date with invoice date.
- **D-P9c-2 (owner):** **Financial reports UI = one tabbed page + a separate AP Aging item.** A
  single **Financial Reports** SYERP nav item hosts Trial Balance / P&L / Balance Sheet as
  tabs/sub-sections sharing date controls; **AP Aging** is its own nav item placed near Bills.
  *Why:* the three GL statements share date-range controls and read the same posted-activity
  surface, so they group naturally; AP aging is a subledger view that belongs beside Bills.
  *Rejected:* four separate nav items (flatter but a longer SYERP sidebar).
- **D-P9c-3 (manager, precedent-driven):** **Phase 9c branches fresh `feature-syerp-financial-
  reports`** off the verified 09b tip (tag `zj/good-09b-ap-bills-match-payments`), not continuing
  `feature-syerp-ap-bills`. *Why:* mirrors the per-sub-phase branching of D-P9a-2 / D-P9b-8 and
  keeps the branch name descriptive of the reports work (the 09b branch name describes AP bills).
  All of Phase 9 remains unmerged and stacks on the same line; the tag is the 09b rollback point.

### Phase 10 planning (MOUSSE manufacturing execution core — 2026-07-13)

- **D-P10-1 (owner):** **Phase 10 = MOUSSE materials-only work-order core.** WO header + status
  FSM, single-level BOM snapshot, explicit component issue → WIP, completion → finished-goods
  receipt, materials cost to GL. **Routing/work-centers, labor + overhead costing (5120/5130), and
  the shop-floor operator execution view are deferred** to a follow-on MOUSSE phase. *Why:* the
  v2.0 DoD only requires "work orders that consume PLUM BOMs and inventory" with cost flowing to
  SYERP — this slice closes it; the fuller MES is a later milestone. *Rejected:* core+routing+labor
  (plan as 10a/10b) and full MOUSSE-01 in one phase (largest, highest verify risk).
- **D-P10-2 (owner):** **Actual moving-average costing; WIP account 1140 clears to zero.** Component
  issues post Dr 1140 WIP / Cr 1130 Inventory at each item's `moving_avg_cost`; the finished-goods
  receipt is valued at the accumulated WIP so 1140 returns to its pre-WO balance (Dr 1130 / Cr
  1140). No standard-cost/variance account. *Why:* 1140 is already seeded and unused; actual cost is
  what's in inventory and makes WIP clear by construction (the 9b GR/IR clearing-crux pattern).
  *Rejected:* PLUM standard cost (needs a variance account + reconciliation, doesn't clear cleanly).
  - **AMENDED at /zj:verify 10 (2026-07-16, owner):** The original design credited 1140 AND debited
    1130 for exactly `accumulated_wip`, but `post_receipt` capitalises only `planned_qty ×
    fg_unit_cost` (6-dp quantized) into the inventory subledger. When `accumulated_wip` does not
    divide evenly by `planned_qty` (e.g. 100/3), the 1130 control account permanently drifted from
    the subledger by a sub-quantum residual — an invisible tie-out break (the class Phase 9c treats
    as first-class). Fix: completion now posts a **3-line JE** — Cr 1140 for exactly `accumulated_wip`
    (WIP still clears to zero, SC3), Dr 1130 for exactly the FG receipt value `planned_qty ×
    fg_unit_cost` (1130 ties to the subledger), and a balancing Dr/Cr to a NEW seeded account **5190
    Inventory Rounding** (COGS, under 5100) for the residual. This narrowly amends "no variance
    account" — 5190 is a rounding sink, not a cost variance — so BOTH invariants hold Decimal-exactly.
    Pinned by `verify_mousse.py` scenario D (1130-debit == FG receipt value; 5190 == residual;
    receipt_value + 5190 == accumulated_wip). Surfaced by the reviewer at verify; owner chose the
    rounding-sink remedy over accepting/documenting a sub-cent break.
- **D-P10-3 (owner):** **Explicit issue action, distinct from completion** (`txn_type="issue"`,
  reserved for MOUSSE). Matches shop-floor reality, supports partial/incremental issue, exercises
  the per-location negative-stock floor guard. *Rejected:* backflush-on-completion (one atomic step,
  simpler, but no partial-issue and less realism).
- **D-P10-4 (manager):** **The `syerp/service.py` split (~3,824 lines → cohesive submodules behind
  unchanged public functions) + the MAP.md refresh are a SEPARATE chore branch FIRST**, verified
  green against the existing `verify_*` scripts, before the MOUSSE build — kept out of the MOUSSE
  feature diff. *Why:* mixing a large no-behavior-change refactor with new-feature work muddies the
  diff and the review/verify; a standalone refactor is independently reviewable (existing scripts
  stay green = proof). *Rejected:* folding the split into Phase 10 (fewer branches, worse diff);
  deferring the split entirely (monolith keeps growing under MOUSSE's imports).
- **D-P10-5 (owner, confirmed at handoff):** **A WO snapshots the single-level (direct) BOM** of the
  part's Released revision at release — the `PlumBomItem` rows at `parent_revision_id`, NOT a
  multi-level leaf explosion. A sub-assembly is issued from stock as one component (it was produced
  by its own earlier WO). *Why:* the materials-only core has no nested work orders; each assembly
  level is its own WO; avoids the `load_flat_bom` sub-assembly/leaf ambiguity. *Rejected:*
  multi-level-to-leaves (assumes one WO builds every level at once; conflicts with the deferred
  routing model).
- **D-P10-6 (manager):** **MOUSSE is a new module** `backend/app/modules/mousse/`, self-registered
  in the registry, router prefix `/mousse`, RBAC codes `mousse:read`/`mousse:write` (mirror syerp);
  it **imports** SYERP inventory/GL service functions rather than duplicating them. The `mousse`
  module is already seeded in `modules_seed.py`.
- **D-P10-7 (manager):** **A component whose PLUM part has no linked `InventoryItem`** (nullable
  `plum_part_id`) makes the WO unbuildable → **reject at WO release (4xx), no partial snapshot** — so
  an unissuable WO can never reach In Progress. *Why:* fail fast at release rather than dead-end at
  issue time.
- **D-P10-8 (manager, precedent-driven):** **Chore branch, then `feature-mousse-work-orders`, both
  cut off the verified 09c tip** (tag `zj/good-09c-ap-aging-financial-statements`). Phase 9 stays
  unmerged; the MOUSSE line stacks on it (per D-P9a-2/D-P9b-8/D-P9c-3).
- **D-P10-9 (owner):** **Completion requires full component issue unless an explicit manual override
  is passed; and the FSM gains an On Hold state (In Progress ⇄ On Hold) for pause/resume.**
  `complete_work_order` rejects (4xx) if any component's issued qty < `qty_required` unless
  `override_incomplete=true`, which is audited (`work_order.completed` detail records the override
  and the FG is valued at whatever WIP accumulated — WIP still clears exactly). A WO In Progress can
  be put On Hold and later resumed to In Progress. *Why:* the owner wants a deliberate, attributable
  decision to close an under-issued build (not a silent default) and the ability to pause a build
  mid-flight and return to it. *Rejected:* silently allowing under-issued completion (recommendation
  (a) at handoff — owner tightened it to require an override); hard-blocking under-issued completion
  with no escape (rejects legitimate under-builds/substitutions).

## v2.0 milestone close (2026-07-16)

- **D-M2-1 (manager):** **v2.0 "Operations" closed.** The definition of done — *"Can track
  inventory, raise purchase orders, keep real books (double-entry GL with AP + financial
  statements), and execute work orders that consume PLUM BOMs and inventory"* — was audited
  goal-backward against the running stack (`.zj/MILESTONE-v2.0-AUDIT.md`): all four clauses traced
  end-to-end backend→router→schema→frontend, 13/13 live `verify_*` scripts exit 0, whole-DB trial
  balance nets zero, control accounts tie to their subledgers, frontend build + 90 Vitest green.
  Verdict clean but for one minor gap. *Consequence:* v2.0 is a real, integrated release, not just
  a phase-list completion. Tagged `v2.0` at the milestone HEAD (see D-M2-3).
- **D-M2-1a (manager):** **Gap G1 fixed at close, not deferred** (mirrors D-M1-2). The audit's one
  finding — the Profit & Loss report fired with an empty `from` date on first tab open and 422'd —
  was fixed in `2578ca5` (default `from` to year-start, pinned by a new `FinancialReports.test.tsx`
  case). Cosmetic first-render error, but cheap to fix and it strengthens the tagged tree.
- **D-M2-2 (owner):** **Human click-through UAT deferred to a tracked post-tag task**, not a tag
  blocker. `.zj/UAT-v2.0.md` (14 UI checks) and the owed v1.0 round-2 checks never ran. All backend
  behavior is live-proven (13/13 verify scripts) and the milestone audit confirmed every route is
  mounted, in-nav, and contract-aligned with its backend schema — so the tag rests on backend
  proof + wired-UI audit (the D-P7-5 precedent that backend proof substitutes for the click-through).
  *Consequence:* the UAT becomes a **pre-public-release gate**, homed as a BACKLOG item. *Rejected:*
  running the 14-check UAT now (blocks the close); waiving it entirely (loses the release-gate).
- **D-M2-3 (owner):** **Version = `v2.0`**, applied at the `feature-mousse-work-orders` HEAD. As with
  v1.0 (D-M1-1), that tree is the working tip of an **unmerged** branch — master is 98 commits behind
  and carries none of Phases 9–10. The master-merge remains the standing `/zj:ship` debt (D-P7-3 /
  D-P8-11); the tag preserves the SHAs a later fast-forward will keep.
- **D-M2-4 (owner):** **Next milestone = Customer & logistics** — CRUMB (CRM), GELATO (WMS), and
  **SYERP-13 accounts receivable** (split out of Phase 9 at D-P9-4, so AR invoices flow from CRUMB
  sales orders). Chosen over the FLAN port and PLUM-advanced. *Why:* completes the sell-side +
  fulfillment loop on top of the now-complete operations core; AR was explicitly parked here.

## v3.0 "Customer & logistics" spec (2026-07-16)

Sharpens the D-M2-4 milestone into a verifiable DoD and expands the three coarse FRs (CRUMB-01,
GELATO-01, SYERP-13) into full acceptance criteria. The through-line is a **sell-side mirror of the
v2.0 buy-side**: order-to-cash mirrors procure-to-pay, and the proven Phase 8–10 patterns
(numeric-safe numbering, Draft→…FSM enforced server-side, immutable balanced JEs on the SYERP-12
engine, subledger↔control Decimal-exact tie-outs, `asyncio.gather` concurrency verify, live-Postgres
`verify_*` scripts) carry over.

- **D-V3-1 (owner):** **v3.0 DoD = three clauses** — (1) CRM & sales pipeline (CRUMB-01), (2)
  warehouse fulfillment (GELATO-01), (3) accounts receivable & sell-side books (SYERP-13). *Why:* the
  milestone is the order → ship → invoice → collect loop; each clause is one suite's contribution and
  independently verifiable, exactly as v2.0's four clauses mapped to inventory/PO/GL-AP/MOUSSE.

- **D-V3-2 (owner):** **Sell-side GL = two-event real books.** Shipment posts **Dr 5100 COGS / Cr
  1130 Inventory** at moving-avg cost; the invoice posts **Dr 1120 AR / Cr 4110 Product Revenue**; a
  customer receipt posts **Dr Cash/Bank / Cr 1120 AR**. *Key simplification vs. the buy side:* the
  two events touch **disjoint accounts** (COGS/Inventory vs AR/Revenue), so **no clearing account** is
  needed — the sell side has no GR/IR analogue. Every account is **already seeded** in `coa_seed.py`
  (1120 AR, 4110 Product Revenue, 5100 COGS, 1110/1111 Cash/Bank, 1130 Inventory) — no new CoA codes,
  no migration for accounts. *Rejected:* a single invoice-time event posting both revenue and COGS
  (would make GELATO shipping non-financial — stock wouldn't move until invoiced); AR-side-only with
  COGS deferred (leaves inventory un-relieved, GELATO decorative). *Why chosen:* keeps GELATO
  shipping financially meaningful and matches the D-P9-1 real-books depth. *Caveat (accepted, deferred
  refinement):* COGS lands at ship and revenue at invoice, so if the two straddle a period boundary
  they mismatch — negligible for a shop that invoices from shipment same-period; a "shipped-not-
  invoiced" deferral clearing is out of scope (revisit only if period-accurate matching is needed).

- **D-V3-3 (owner):** **Invoices are shipment-driven** — the user invoices a customer's
  shipped-but-uninvoiced quantities (uninvoiced = shipped − Σ already-invoiced, matched at
  sales-order-line grain), mirroring the receipt-driven AP bill (D-P9b-1). Partial shipments → partial
  invoices. *Rejected:* invoice-from-order (can bill goods that never shipped) and free-form manual
  invoices (no order↔invoice tie-out). *Why:* hardest to mis-key and preserves the procure-to-pay
  symmetry the shop already knows from AP.

- **D-V3-4 (owner):** **Lot/serial tracking deferred** to a follow-on GELATO phase; v3.0 fulfillment
  is **quantity + cost only**. *Why:* lot/serial is the heaviest schema addition (a dimension on
  every stock movement and on-hand read) and the DoD's fulfillment loop doesn't require it; carving it
  out mirrors deferring routing/labor out of MOUSSE (D-P10-1) to keep the milestone shippable.
  *Rejected:* lot-only and lot+serial now (largest verify surface; the medical-device traceability
  story is better served once CRISP frames the requirement).

- **D-V3-5 (owner):** **CRUMB depth = full lean chain** — leads → opportunities (pipeline stages) →
  quotes → sales orders, plus a **customer communication/interaction log**; **no** email send/receive
  integration and **no** reporting/analytics. *Why:* delivers the DoD's "sales pipeline through to
  orders" without pulling in an external-service (email) dependency, which would breach the
  self-hosted/offline posture and balloon scope. *Rejected:* trimmed to quotes→orders (loses the
  pipeline the DoD names); full incl. email/analytics (external dependency, largest).

- **D-V3-6 (owner):** **Quote/order line pricing = PLUM-derived default, editable.** A line's unit
  price defaults from the part's PLUM released cost + an editable markup and is editable per line; the
  effective cost is shown for margin visibility. **No price-list entity.** *Why:* gives useful default
  pricing and margin insight without a price-list/customer-pricing table (which overlaps the deferred
  PLUM-16 distributor-pricing FR). *Rejected:* manual-only (no margin help); full price list (PLUM-16
  territory, later milestone).

- **D-V3-7 (owner):** **GELATO scope = inbound + outbound.** v3.0 adds **bins** as a sub-level within
  SYERP's flat stock locations (realizing the bin/zone hierarchy deferred at D-P8-3), **directed
  putaway-to-bin** on inbound receipts, **and** the outbound **pick → pack → ship** flow. Per-bin
  on-hand derives from bin-aware movements and rolls up to the SYERP location total. *Why:* the owner
  wants a real WMS layer, not just an outbound shipping hook; bins are the foundational structure both
  directions share. *Rejected:* outbound-only (leaves inbound putaway unbuilt) and ship-from-flat-
  locations-no-bins (leaves the D-P8-3 bin promise unmet). *Cost accepted:* larger than the
  outbound-only slice; the inbound putaway overlaps SYERP-11.4 receiving and the integration seam
  (extend the receipt to target a bin vs. a follow-on putaway move) is a `/zj:plan` detail.

- **D-V3-8 (owner):** **A confirmed sales order soft-reserves inventory.** Confirming reserves
  `min(qty_ordered, available)` per line against the SYERP inventory item; `available = on-hand − Σ
  reservations` and a reservation **never drives available negative**; a short line is confirmed with
  a visible **backorder** indicator (not hard-blocked, single-shop). Shipping (GELATO-01.5) converts
  the reservation to an issue. *Why:* prevents the same stock being promised twice across orders — the
  reservation invariant is the crux CRUMB-01 verify pins. *Rejected:* decrement-only-at-ship (simpler,
  but two orders can each believe stock is available). *Note:* reservation is a soft ledger concept,
  not a physical move — no InventoryTxn until ship.

- **D-V3-9 (manager, precedent-driven):** **Module ownership** — leads/opportunities/quotes/sales
  orders live in the new **CRUMB** module; bins/putaway/pick/pack/ship in the new **GELATO** module;
  AR invoices/receipts/aging **and all GL journal entries** stay in **SYERP** (the hub owns the
  books). GELATO ship and the AR invoice **import** SYERP inventory/GL service functions rather than
  duplicating them (the MOUSSE D-P10-6 precedent). Sales orders are CRUMB (not SYERP) per PRD-8 — the
  deliberate asymmetry with SYERP purchase orders, because the sell side is CRUMB's domain and POs
  predate the CRUMB module. RBAC: new `crumb:read`/`crumb:write` and `gelato:read`/`gelato:write`
  codes (mirror `syerp:*`); AR endpoints stay under `syerp:*`. *Why:* keeps SYERP the single GL
  authority (one posting engine, one set of tie-outs) while the customer/warehouse suites own their
  workflow surface.

### Phase 11 planning — CRUMB CRM & sales orders split (2026-07-16)

- **D-V3-10 (owner):** **Phase 11 (CRUMB-01) splits into 11a + 11b.** CRUMB-01 is the largest single
  FR in the project — 5 new entities (leads, opportunities, quotes, sales orders, communication log),
  3 server-enforced FSMs, PLUM-derived pricing, the soft-reservation invariant, and ~5 net-new
  screens. **11a = CRM pipeline** (leads → opportunities → quotes + communication log): pure
  CRUD/FSM/pricing referencing SYERP customers + PLUM parts, **no inventory dependency**. **11b =
  sales orders** (Draft→Confirmed→Fulfilling→Closed), the **accepted-quote→sales-order conversion**,
  and the **soft-reservation crux** (D-V3-8). Each is planned/built/verified on its own branch and
  tag, extending the 9a/9b/9c precedent. *Why:* the clean seam is inventory — 11a has no hard
  invariant (isolable, big-but-easy), 11b carries the one hard invariant (reservation) in a
  small-but-hard phase with a focused verify. *Rejected:* one full-stack Phase 11 in waves (Phase-8/10
  style) — a ~25–30-task diff and one heavy verify pass over both the CRM surface and the reservation
  invariant at once. **11a is planned first (this `/zj:plan 11`).**

- **D-V3-11 (owner):** **Soft-reservation = a `qty_reserved` accumulator on the sales-order line**
  (an 11b concern, decided now because it shapes the GELATO handoff). On-hand is a derived
  `SUM(InventoryTxn.quantity)` over the immutable ledger; a soft reservation moves no stock, so it
  cannot live in that ledger. It is stored as `qty_reserved` on the SO line — a **mutable working
  document**, exactly like the PO `qty_received` accumulator (D-P8-15) — and `available(item) =
  derived_onhand − Σ open SO-line reservations`. GELATO shipping (11b/Phase 12) decrements
  `qty_reserved` and posts the real `issue` InventoryTxn, converting the reservation to a physical
  move. *Rejected:* a separate append-only `crumb_reservation` ledger mirroring InventoryTxn — more
  auditable/replayable but a second ledger to maintain and reconcile against the SO, unwarranted at
  single-shop scale for a soft (non-physical) quantity. *Why:* reuses the proven mutable-accumulator
  pattern and keeps the immutable ledger reserved for real stock movements.

- **D-V3-12 (owner):** **CRUMB UI folded into the plan — no separate DESIGN.md** (D-P8-9 precedent).
  Leads/opportunities/quotes screens reuse the existing SYERP **list + sheet + archive** and
  **FSM-detail** template (`Vendors.tsx`/`Customers.tsx`/`PartnerSheet.tsx`, PO detail); the
  **opportunity pipeline is a per-stage grouped list** as AC2 literally states ("view the pipeline as
  a per-stage list"), **not** a drag-drop kanban, which keeps the one novel screen inside the existing
  component vocabulary. *Why:* the SYERP CRUD/FSM template is a strong enough starting point that a
  separate design pass isn't worth the step; the pipeline's novelty collapses to a grouped list.
  *Rejected:* running `/zj:design` first (de-risks novel UX but adds a step the reduced pipeline scope
  doesn't need).

- **D-V3-13 (manager, precedent-driven):** **Phase 11a branch = `feature-crumb-crm-pipeline` off
  master.** Master is now the working tip (v2.0 shipped via PR #2 fast-forward to `35f9b66`, resolving
  the D-M2-3 debt), so the D-P9a-2 discipline applies: branch feature work off master, not off an
  unclosed line. The docs-only `chore-spec-v3-customer-logistics` spec branch (which carries these
  v3.0 planning artifacts) **fast-forwards to master first**; then `feature-crumb-crm-pipeline` cuts
  from that clean master tip. *Why:* keeps the CRUMB build on a merged base and the spec branch out of
  the feature diff.

- **D-V3-14 (owner):** **Quote-line markup default = a module constant.** `DEFAULT_MARKUP_PCT =
  Decimal("30")` lives in `crumb/service/_common.py` and is applied as the initial per-line default
  (`unit_price = released_cost_snapshot × (1 + DEFAULT_MARKUP_PCT/100)`), **editable per line**. *Why:*
  gives a useful default and margin visibility (D-V3-6) with zero config surface. *Rejected:* a CRUMB
  settings row (scope creep — D-V3-6 excludes a price-list/config entity) and per-line-default-0 (no
  margin help, more keying). Change the constant to re-baseline; a per-customer/price-list model is
  PLUM-16 territory, later.

- **D-V3-15 (owner):** **A quote may be spawned only from a `won` opportunity.**
  `spawn_quote(db, opp_id, …)` rejects (422) unless the opportunity's stage is `won` — mirroring AC2's
  "a Won opportunity can spawn a quote." *Rejected:* allowing any open stage (qualify/proposal) to
  spawn — defensible since a quote is the proposal document, but it loosens the pipeline's meaning;
  revisit if the shop wants to quote earlier.

## v3.0 Phase 11b planning (2026-07-16)

- **D-V3-16 (owner):** **Unlinked / free-text SO lines are non-stock.** A sales-order line whose PLUM
  part has no linked `InventoryItem`, or a free-text line with no part, confirms with `qty_reserved=0`
  and a visible non-stock / backorder indicator; the SO still confirms. *Why:* consistent with D-V3-8
  ("a line whose ordered qty exceeds available is confirmed with a shortage indicator, not
  hard-blocked" — single-shop). *Rejected:* a MOUSSE-D-P10-7-style hard reject of confirmation until
  every line maps to a stock item — that contradicts the soft/backorder intent on the sell side.

- **D-V3-17 (owner):** **Phase 11b delivers both direct SO creation and quote conversion.** A user can
  create a sales order directly (header + lines, editable while Draft, mirroring the PO/quote create),
  AND convert an Accepted quote to a Draft SO copying its lines (the AC3 tail). The SO is a
  first-class document (SRD AC4), not merely a conversion artifact. *Why:* the SO-detail screen and
  line editor are needed for the Draft-edit path regardless, so direct-create is cheap marginal scope;
  users can raise ad-hoc orders without a prior quote. *Rejected:* conversion-only (smaller surface,
  but forces every SO through a quote).

- **D-V3-18 (owner):** **Reservation locking is narrow — the contended `InventoryItem` row(s) only.**
  `confirm_sales_order` locks the distinct `InventoryItem` rows its stock lines reference `FOR UPDATE`
  in sorted-id order BEFORE the `available = on-hand − Σ open reservations` read-check-write (the
  `bills.py` template), which is sufficient to make the reservation invariant race-safe. The broader
  standing BACKLOG p2 item — one shared floor-guard lock across every SYERP ledger-writing path
  (issue/adjust/receive/transfer) — is **not** taken on in 11b; it defers to Phase 12, when GELATO
  ship actually writes real `issue` `InventoryTxn`s and gains the ledger-floor race. *Why:* keeps the
  small-but-hard phase focused on its one invariant; a soft reservation moves no stock, so it doesn't
  touch the ledger floor guard. *Rejected:* unifying the shared ledger-floor lock now (bigger diff
  over verified SYERP paths for a debt whose third writer isn't live until Phase 12). The reviewer
  should read the narrow scope as intentional.

- **D-V3-19 (manager, precedent-driven):** **Phase 11b branch = `feature-crumb-sales-orders` off the
  verified 11a tip** (tag `zj/good-11a-crumb-crm-pipeline`, commit `efcf2e6`). 11a is unmerged, so 11b
  stacks on it, extending the per-sub-phase branch precedent (D-P10-8 / D-P9b-8). *Why:* keeps the
  CRUMB sales-order build on the verified CRM base without waiting on a master merge.

## v3.0 Phase 11b verify (2026-07-17)

- **D-V3-20 (owner):** **Quote→SO conversion stays non-idempotent for now — fix the blocker only.** The
  `/zj:verify 11b` fix loop surfaced two items: (1) a **blocker** — direct-create/edit SO lines never
  resolved `plum_part_id→item_id` (the UI line-editor sends `plum_part_id` only), so UI-created orders
  reserved 0 stock; and (2) an open **question** — an Accepted quote can convert to unlimited duplicate
  SOs (no guard, no quote state change). Owner chose **fix the blocker, defer the convert guard.** *Why:*
  the reservation bug is a broken headline feature (must fix); duplicate SOs are visible and cancellable
  in a single-shop model, and the right guard depends on the quote→SO→invoice lifecycle that Phase 13
  (SYERP-13 invoicing) will firm up. Blocker fixed `fec334f` + pinned by new `verify_crumb_so.py` (D2)
  assertions; the convert-idempotency follow-up logged to BACKLOG p3.
