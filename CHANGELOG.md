# Changelog

All notable changes to BizNiceSweets.

> **Generated from conventional commits — do not edit by hand.**

Format loosely follows [Keep a Changelog](https://keepachangelog.com/). Only `feat:` and
`fix:` commits appear here; `docs:`/`chore:`/`test:` are omitted.


## [v4.0] — Infra-debt & quality paydown — 2026-08-18

Definition of done — five clauses: *"The full test suite (integration + unit) runs green in a
GitHub Actions CI pipeline on every push, both lint gates enforce a zero-violation baseline, the
inventory ledger is race-safe across every writer, and every shipped UI flow has a documented,
runnable human check — so a new deploy is trustworthy without a manual `verify_*` run."* (The
fourth clause was amended at close from "has **passed** a documented human click-through" to match
NFR-8 and PRD-12, which D-P5-11 had already moved — see `.zj/MILESTONE-v4.0-AUDIT.md` GAP-1.
`.zj/QA.md` §6 holds zero readings: **v4.0 ships with no human-exercised UI evidence, by design.**)

**This release adds no new end-user capability.** It pays down p1 infrastructure debt that had
ridden unpaid for three milestones and hardens the shared inventory ledger. For v1.0→v3.0
correctness rested entirely on standalone `verify_*` scripts and Vitest **run by hand**, and the
class of bug that ships when tests silently skip had already bitten once.

Highlights: CI now runs on every push (six blocking-capable jobs); both lint gates enforce a
zero-violation baseline; ~100 DB-backed tests that had **never actually run** now run 0-skip; the
ledger's `FOR UPDATE` discipline covers every writer; and the shipped container image is built —
and booted — on every push. Three deploy-blocking defects were found and fixed along the way, two
of which had been invisible for five phases because nothing had ever exercised the artifact a
self-hoster receives.

Audited goal-backward at close against the running stack (`.zj/MILESTONE-v4.0-AUDIT.md`): pytest
**245 passed / 0 skipped**, 17/17 non-API + 9/9 API `verify_*` (251 assertions), both lint gates 0,
Vitest 148/45, build clean. The audit returned **GAPS FOUND** — 1 blocker-to-close, 3 major, 4
minor — against a milestone whose every phase had already passed verification; **all eight were
fixed at close.**

### Phase 1 — Lint gates fixed-to-clean (NFR-6)

**Fixed**

- resolve 4 F821 undefined-name annotations (`35b91d0`)
- resolve F811/E741/F841 lint violations (`5ea6363`)

### Phase 2a — Pytest harness repair (NFR-5)

Zero product-code change; `git diff -- backend/app/` provably empty.

**Fixed**

- repair DSN probe with libpq keyword args (`afa5798`)
- DB now a hard requirement + zero-skip self-check (`a2bb5a6`)

### Phase 2b — Port the `verify_*` cruxes into pytest (NFR-5)

Test-only, again with `git diff -- backend/app/` empty: 7 service-layer crux files + 5 HTTP
audit/RBAC files, each headline Decimal asserted against an independent oracle. Suite to 232
passed / 0 skipped.

### Phase 3 — CI pipeline, GitHub Actions (NFR-4)

Infra-only. `.github/workflows/ci.yml` — `frontend`, `backend-lint`, `backend-tests` (against a
live `postgres:17` service) and `verify-scripts`, on every push and PR, with required-status branch
protection on `master`. Red-proven on real Actions runs by deliberately breaking a test and
planting lint violations, then reverting.

### Phase 4 — Inventory ledger race-safety (NFR-7)

**Added**

- serialize inventory writers on item-master lock (`73e45c2`)
- serialize receive_line on PO-header lock (`e1dc5c0`)
- bin-aware post_adjustment — explicit-or-unbinned (`4285202`)
- bin-aware post_transfer via from_bin_id (`b80cb37`)
- bin-aware issue_components — per-line bin_id (`455cf5c`)
- optional bin picker on StockAdjustDialog (`6d55d72`)
- optional from-bin picker on StockTransferDialog (`b270161`)
- per-line bin picker on IssueComponentsDialog (`886193a`)

**Fixed**

- restore per-location floor in issue_components (`2a87f6d`)
- refresh item under lock in post_transfer legs (`5a45a7b`)

### Phase 5 — Human click-through UAT → the standing QA checklist (NFR-8)

Delivered `.zj/QA.md`: 61 requirement-keyed checks over fixtures reproducible on a fresh volume.
Three defects, all found by engineering before anyone clicked — two of them deploy blockers.

**Added**

- validate bin existence and location membership (`e57c1ff`)

**Fixed**

- **U0** — db never received POSTGRES_PASSWORD on a fresh volume (`4ace2c4`)
- **U1** — duplicate-email user create returned HTTP 500 (`f508554`)
- **U2** — the API image could not be built at all (`8d61cca`)
- reject an archived bin in post_adjustment (`fd7ca87`)
- refuse to seed a database that is not a UAT stack (`3a6ce35`)
- port uat.ps1 to the env split and warn on the old layout (`50e14b5`)

### Milestone close — audit remediation

The close audit found the milestone's own subject matter was where its holes were: an unlocked
ledger writer, and three CI coverage gaps.

**Fixed**

- **GAP-2** — serialize execute_pick on the SO row and sort its item locks (`4dc3154`). The last
  ledger writer outside the `FOR UPDATE` discipline. Both failure modes were *reproduced* under a
  barrier: two concurrent first-picks of one sales order produced two open shipments — the second's
  picked stock unreachable, since GELATO exposes no list-shipments-for-an-SO route — plus a lost
  `qty_picked` update; and two picks sharing two items in opposite order deadlocked 6/6. Each half
  of the fix proven load-bearing in isolation.
- **GAP-7** — QA.md status cells contradicted the SRD, now cross-checked (`5fe324e`)

Also landed as CI configuration (`a962a79`): a `verify-scripts-api` job running the 9
`verify_*_api.py` scripts, which had run in **no** job at all — leaving ~250 router-level
assertions outside CI, including the only automated coverage anywhere of the financial-reporting
HTTP surface and the v2.0 audit's own P&L-422 remediation; the `container-image` job extended to
**boot** the artifact it builds and probe `/health/ready`; and `eslint.config.js` brought inside
its own lint coverage.


## [v3.0] — Customer & logistics — 2026-07-19

Definition of done — three clauses: *(1) manage customers and run leads → opportunities →
quotes → sales orders with PLUM-derived editable line pricing and a communication log, where
confirming an order soft-reserves inventory; (2) bins within stock locations, directed putaway
on inbound receipts, and outbound pick → pack → ship that relieves the reservation; (3) shipment
posts Dr COGS / Cr Inventory, invoice-from-shipment posts Dr AR / Cr Revenue, customer receipt
posts Dr Cash / Cr AR, with AR aging tying Decimal-exactly to the 1120 control account and the
trial balance still netting zero.* All three clauses audited goal-backward against the running
stack (`.zj/MILESTONE-v3.0-AUDIT.md`): 23/23 live verify scripts exit 0 (14 service + 9 HTTP),
whole-DB trial balance nets zero, AR/AP control accounts tie to their subledgers, frontend build
+ Vitest green. Human click-through UAT carried on BACKLOG p1 (D-M2-2).

Adds two new suites — **CRUMB** (CRM) and **GELATO** (WMS) — and closes the sell-side of SYERP
with accounts receivable, completing the lead → order → ship → invoice → cash loop.


### Phase 11a — CRUMB CRM & pipeline


**Added**

- add CRM ORM models — lead, opportunity, quote, interaction (`e57459c`)
- add Alembic 0013 for crumb crm tables (`5391918`)
- seed crumb:read / crumb:write permissions (`79fcf31`)
- add CRUMB Pydantic schemas (`3cd5b1f`)
- scaffold crumb/service package + FSM/markup helpers (`6bbb5d5`)
- quotes service — PLUM-priced lines, QUOTE-#### generator, status FSM (`e145998`)
- leads service — CRUD, archive, customer link, convert (`67744c1`)
- interactions service — append-only per-customer timeline (`8154c7c`)
- opportunities service — stage FSM, pipeline, spawn quote (`0dc2ddd`)
- router + self-registration with router-layer audit (`ff88aeb`)
- frontend nav, hooks, routes + page stubs (`402d048`)
- leads list, detail sheet, archive + convert UI (`d409d4d`)
- opportunity pipeline (stage-grouped) + detail (`2fef975`)
- quote builder, line editor + status FSM actions (`3550f69`)
- communication-log timeline (append-only) (`1a6fbcd`)

**Fixed**

- close verification gaps in quote lines + convert + audit (`a697c69`)


### Phase 11b — CRUMB sales orders + soft-reservation


**Added**

- add SalesOrder + SalesOrderLine ORM models (`3f37d72`)
- add alembic migration 0014 for CRUMB sales-order tables (`567a48d`)
- add SO_TRANSITIONS FSM table to CRUMB _common (`c6b5b64`)
- add get_item_on_hand scalar helper to SYERP inventory service (`f19964e`)
- add sales-order Pydantic schemas (`ce3d13f`)
- sales-orders service — create, draft edits, status FSM (`a80bba1`)
- convert accepted quote to draft sales order (`b69034e`)
- sales-order confirm (soft-reservation) + cancel release (`692dbda`)
- sales-order + conversion router endpoints with audit (`9f5c563`)
- sales-order hooks, routes, and nav item (`73030eb`)
- Convert to Sales Order action on accepted quotes (`ed1cb59`)
- sales-order list + create dialog with draft line editor (`69cbc48`)
- sales-order detail with reserved / shortage lines + FSM (`1233aea`)

**Fixed**

- resolve item_id from plum_part_id on direct SO create/edit (`fec334f`)


### Phase 12a — GELATO bins & directed putaway


**Added**

- add Bin model + bin_id ledger column + gelato package (`b0b0dcd`)
- wire module import + model aggregation (`2cc1161`)
- migration 0015 — gelato_bin + syerp_inventory_txn.bin_id column (`7449fb4`)
- seed gelato:read / gelato:write permissions (`57745e5`)
- add Pydantic schemas for bins + putaway (`24c47ed`)
- add SYERP post_putaway + get_bin_on_hand bin-aware primitives (`5de6ea6`)
- bin CRUD + putaway orchestration service (`f548f2e`)
- router — bins CRUD + putaway, RBAC + audit (`f8dd454`)
- FE API hooks + nav + routes (`f46bce4`)
- Bins screen — list / create / edit / archive (`7ab258c`)
- Putaway screen — unbinned → bin directed move (`82e37c5`)

**Fixed**

- coerce bin audit target_id to str for varchar column (`136e98d`)


### Phase 12b — GELATO outbound pick → pack → ship + COGS JE


**Added**

- add qty_picked / qty_shipped accumulators to SalesOrderLine (`61a695e`)
- add Shipment + ShipmentLine ORM models (`6515f50`)
- add shipment pick/pack/ship Pydantic schemas (`074d1c0`)
- migration 0016 — shipment tables + SO-line accumulators (`9a0c867`)
- add SYERP bin-aware post_issue inventory primitive (`2940d61`)
- add commit param to post_putaway for atomic batching (`9b87e14`)
- shipment pick service — bin-aware, net-zero to staging (`53b3b88`)
- shipment pack service — FSM picking → packed (`3f06ed3`)
- ship service — issue + Dr 5100 COGS / Cr 1130 JE + reservation relief (`0082f9d`)
- pick/pack/ship router endpoints with audit + RBAC (`c248fdf`)
- shipment hooks + Fulfillment nav / route (`304f78a`)
- Fulfillment pick/pack/ship screen + test (`6d319b2`)
- SO-detail Fulfill/Ship affordance + qty_shipped (`da3f5d7`)

**Fixed**

- type shipment FK id fields as Optional[str] (`6fa9c0f`)
- serialize qty_picked / qty_shipped on SalesOrderLineRead (`65a1425`)
- lock shipment row FOR UPDATE before ship FSM gate — prevents concurrent double-ship (`553bcfb`)


### Phase 13 — SYERP-13 accounts receivable & sell-side books


**Added**

- add Invoice + InvoiceLine ORM models (`6a5ce2f`)
- add Receipt + ReceiptAllocation ORM models (`4a95d88`)
- add AR Pydantic schemas — invoice / receipt / aging (`86399ac`)
- add qty_invoiced accumulator to SO line — model + schema + UI (`4ba5ec6`)
- migration 0017 — AR tables + qty_invoiced column (`da64a80`)
- AR scaffolding — invoice numbering + uninvoiced-shipments query (`21b33f7`)
- create_invoice + invoice read layer (`40a0114`)
- post_invoice — Dr 1120 AR / Cr 4110 Revenue journal entry (`dd35877`)
- record_receipt — allocations + Dr cash / Cr 1120 + auto-Paid (`86dd190`)
- ar_aging_report — buckets + 1120 control tie (debit-normal, no negation) (`099d92b`)
- AR router endpoints — RBAC-gated, audit-after-commit (`f06ec78`)
- AR invoices list + create-from-shipment dialog (FE) (`651a204`)
- AR invoice detail — post action + open balance (FE) (`71250bb`)
- AR receipts — record receipt against posted invoices (FE) (`5e9d14f`)
- AR aging screen + nav + routes (FE) (`5d89da8`)

**Fixed**

- import model aggregator at startup so cross-module FKs resolve on a cold process (`ea2f2cb`)
- validate invoice sales_order_id up front + bound retry — prevents unbounded recursion/500 (`7610e63`)


### Milestone close — audit gap fixes


**Fixed**

- AR aging tie-out reclassifies prepayments — a receipt dated before its invoice_date no longer reports a false negative 1120 control (`97b977b`)
- invoice picker shows a resolved item "code — name" label instead of a bare item UUID (`97b977b`)


## [v2.0] — Operations — 2026-07-16

Definition of done: *"Can track inventory, raise purchase orders, keep real books (double-entry
GL with AP + financial statements), and execute work orders that consume PLUM BOMs and
inventory."* All four clauses audited goal-backward against the running stack
(`.zj/MILESTONE-v2.0-AUDIT.md`): 13/13 live verify scripts exit 0, trial balance nets zero, all
control accounts tie to their subledgers, frontend build + 90 Vitest green. Human click-through
UAT (`.zj/UAT-v2.0.md`) deferred post-tag by owner decision (D-M2-2).


### Phase 8 — SYERP inventory & purchasing


**Added**

- add inventory item/location/txn schema (migration 0007) (`b5c5c31`)
- inventory item CRUD with numeric-safe ITEM- code generator (`511d6ae`)
- stock-location CRUD + idempotent Main location seed (`06f318c`)
- derived on-hand-by-location + valuation + txn history reads (`e35021e`)
- receipt posting + Decimal moving-average recompute (`8e1b31f`)
- stock adjustment posting with per-location negative guard (`0074bf0`)
- stock transfer posting (paired legs, underflow guard) (`5f2a228`)
- inventory items screen (list, sheet, archive) + route (`1fd2423`)
- stock locations screen (list, sheet, archive) + route (`8e75af9`)
- inventory item detail — on-hand, valuation, ledger (`8b2c748`)
- stock adjustment dialog (signed qty, reason, 422 toast) (`c9d6952`)
- stock transfer dialog (from/to guard, 422 toast) (`cdf0e6c`)
- add purchase-order schema (migration 0008) (`cafa93f`)
- PO draft CRUD + numeric-safe PO- generator + vendor guard (`b5d7882`)
- PO approve/close FSM with server-side transition guard (`92896ea`)
- PO line receiving -> inventory receipt + status roll-up (`79181bd`)
- vendor PO history — per-PO total + received roll-up (`ce5f666`)
- purchase-orders list screen (status, totals, vendor filter) (`6d8afcc`)
- PO create/draft-edit screen (vendor + line editor) (`e21ac2a`)
- PO detail — roll-up, approve/close, receive seam (`cd03899`)
- PO receiving dialog (qty + location, 422 toast) (`8aa6b65`)


**Fixed**

- reject non-existent plum_part_id with 4xx, not 500 (`554c3fe`)


### Phase 9a — GL posting engine + receipt auto-post (SYERP-12 AC1/2/3/8/9)


**Added**

- seed GR/IR clearing account 2150 in standard CoA (`8b97fc2`)
- pure Decimal journal-entry balance helpers (`9844b3e`)
- JournalEntry and JournalLine GL models (`f570f68`)
- GL journal-entry and account-register schemas (`5679510`)
- 0009 GL journal migration (`343b334`)
- GL posting/reversal/register services (`fd9adf1`)
- GL journal-entry endpoints with RBAC + audit (`dee9820`)
- auto-post balanced GL entry (Dr 1130 / Cr 2150) on PO receipt (`0d9eb98`)
- manual journal entry list + post dialog (`38d65b1`)
- reverse action + Account Register screen (`c2bde3d`)
- GL journal + account register routes and nav tabs (`706432c`)


**Fixed**

- GL Read-schema id fields are uuid str, not int (`89daadc`)
- verify-loop majors: zero-cost receipt regression, double-reversal guard (`c905a6b`)


### Phase 9b — AP bills, PO match & payments (SYERP-12 AC4/AC5)


**Added**

- pure Decimal AP helpers + unit tests (`c1b431b`)
- seed 1111 Bank – Checking in standard CoA (`5502445`)
- Bill, BillLine, Payment, PaymentAllocation models (`1697973`)
- AP bill/payment Pydantic schemas (`ff39967`)
- 0010 AP bills/payments migration (`b91ed73`)
- unbilled-receipts query + create bill with PO-line match (`52d9a83`)
- post_bill balanced JE + Draft→Posted→Paid FSM (`3b8eb33`)
- record_payment JE + allocations + overpayment guard (`be0a774`)
- AP bill endpoints — unbilled/create/list/get/post (`7ef302b`)
- AP payment endpoints — record + list (`e7bb9b2`)
- AP bills list + create/match dialog (`4e25ab2`)
- bill detail with post + pay actions (`bb57463`)
- AP Bills routes + nav tab (`72cfd82`)


**Fixed**

- reject duplicate po_line_id in one bill payload (`13ca4cd`)
- add list_payments read for GET /ap/payments (`99ef164`)
- row-lock AP guards against concurrent double-bill/overpay (`380c73b`)


### Phase 9c — AP aging + financial statements (SYERP-12 AC6/AC7)


**Added**

- Bill.bill_date column (invoice date for AP aging) (`f6b9635`)
- migration 0011 — syerp_bill.bill_date NOT NULL (`cab8531`)
- wire bill_date through create_bill and bill JE (`729ec00`)
- report read schemas (AP aging, TB, P&L, balance sheet) (`69e4724`)
- AP aging report with 2110 subledger tie-out (`c24c9f6`)
- trial balance report (nets debits == credits) (`7aecf7c`)
- profit & loss report over a date range (`1d38ddb`)
- balance sheet with computed current-year net income (`6f79047`)
- read-only report endpoints (AP aging, TB, P&L, BS) (`a9cae54`)
- AP aging screen with per-vendor buckets + 2110 tie-out (`c6b47d3`)
- financial reports page (trial balance, P&L, balance sheet) (`8994f5c`)
- report routes + nav; bill-date on the create dialog (`48c8453`)


### Phase 10 — MOUSSE manufacturing execution core (materials-only, MOUSSE-01)


**Added**

- seed mousse:read/write permissions (`0ce67ae`)
- WorkOrder ORM models (`162c463`)
- work-order Pydantic schemas (`f94c5a9`)
- alembic 0012 for work-order tables (`dd40197`)
- WO create, number gen, list/get, detail (`09c5a64`)
- WO FSM, release BOM snapshot, cancel/hold/resume (`c84bf2b`)
- issue components — Dr 1140 WIP / Cr 1130 at moving-avg (`21ad021`)
- complete WO — WIP clears to zero, FG receipt Dr 1130 / Cr 1140 (`83b4d0e`)
- work-order router with RBAC and audit (`1f75d62`)
- register module and mount work-order router (`2e04ffc`)
- work-order list, hooks, route, and nav wiring (`5a75966`)
- work-order create dialog (`67091c0`)
- work-order detail — snapshot lines, issue, hold/resume (`3d93be4`)
- work-order complete action with override-incomplete guard (`c3239a6`)


**Fixed**

- route WO completion residual to 5190 rounding account so 1130 ties to subledger (`5cffeeb`)
- re-export PO_TRANSITIONS/BILL_TRANSITIONS from split service pkg (`3d59068`)


### Milestone close — v2.0 audit fixes


**Fixed**

- default P&L From date to year-start so the report never 422s on first open (`2578ca5`)


## [v1.0] — Foundation + PLUM — 2026-07-11 (tag `v1.0`)

Definition of done: *"Can deploy it, log in, manage vendors/customers, and design parts with
multi-level BOMs and cost roll-up."* Proven at the API layer by the milestone audit
(`.zj/MILESTONE-v1.0-AUDIT.md`: 66 live-DB assertions, 0 failures). The 12-check human UAT
(`.zj/UAT-v1.0.md`) is the remaining gate before this tag is applied.


> **Note on ordering:** Phase 7's last two fixes (`7562a02`, `8975eeb`) and the milestone-audit
> fix (`63ea954`) were committed *after* Phase 8's work. No single commit is a clean v1.0 tree.


### Phase 1 — Project scaffolding & deployment


**Added**

- backend core (config, DB, Base, registry, health) (`f1ca179`)
- SYERP hub stub, central model aggregator, seed hook, Alembic single history (`8e4b060`)
- scaffold Vite + React + TS frontend with Tailwind v4 + shadcn (`6d4c50d`)
- wire Router + TanStack Query providers and landing/health page (`6a68780`)
- pytest Wave 0 harness (pyproject, conftest, health + migration tests) (`a81e985`)
- add SPA serving, multi-stage Dockerfile, and entrypoint (`c918b27`)
- add compose files, .env.example, gitignore updates, and dev docs (`a0f037b`)


**Fixed**

- relocate build file to root Containerfile for Windows podman-compose (`84fdc7c`)
- install devDependencies in frontend build stage (`c4b892b`)
- enable alembic prepend_sys_path so app package imports in container (`dd93df4`)
- align frontend health paths with backend (/health, not /api/health) (`5f7fee9`)


### Phase 2 — Authentication & users


**Added**

- add pyjwt/pwdlib deps and extend Settings with auth fields (`068aaa1`)
- implement auth models, service helpers, schemas, and module registration (`2018f8b`)
- add Wave 0 test harness and auth tables Alembic migration (`66b6a88`)
- implement service auth functions and auth dependencies (`dd4be6a`)
- implement login/refresh/logout/me endpoints and flip xfail tests (`82a76c9`)
- implement idempotent first-admin seed (GREEN) (`8662a80`)
- implement admin user CRUD, RBAC probe, deactivation, and audit log (GREEN) (`51c2e16`)
- add axios client, silent-refresh interceptor, token store, useAuth, and ProtectedRoute (`3b40b95`)
- add Login page and App routing wiring (`f28cfd8`)
- add Admin User Management screen with table, sheet, and deactivate dialog (`748d641`)


**Fixed**

- revise plans per checker feedback (`33a08bf`)
- add email-validator dep and document required auth env vars (`2ae8ebd`)
- load role permissions via awaitable_attrs in admin seed (`272db33`)
- align admin-user role field with backend contract and fix create_user role assignment (`6ed6b66`)
- guard diagnostic _rbac_probe behind debug (`2def5b2`)


### Phase 3 — App shell & settings


**Added**

- ORM models for modules and settings + Alembic discovery wiring (`ef4a029`)
- idempotent seeds + settings:manage permission + Alembic revision 0003 (`41a7c84`)
- Pydantic schemas + modules/settings routers + main.py mount (`c1a68ba`)
- extend /auth/me with flat permissions list + green core tests (`4b2c3b0`)
- Switch primitive, data hooks, AuthUser permissions, App.tsx routing (`c9e63ff`)
- AppShell, Sidebar, Topbar, MobileSidebar chrome (`d8b2efb`)
- Home, Settings form, and Modules toggle screens (`b767be4`)


### Phase 4 — SYERP core hub


**Added**

- define Partner + GLAccount models and migration 0004 (`f60f89a`)
- add idempotent CoA seed and wire into run_seeds() (`ad05312`)
- implement SYERP Pydantic schemas (PartnerCreate/Read/Update, GLAccountRead) (`7ceb1af`)
- implement SYERP service layer (partner CRUD, search, archive, code gen, GL list) (`396d8ad`)
- implement SYERP router (partner + GL endpoints) and green Wave 0 tests (`c81c9d5`)
- shared PartnerSheet and PartnerArchiveDialog components (`f539a85`)
- Vendors and Customers list screens with Wave 0 tests (`96c31a5`)
- add GLAccounts screen and wire SYERP routes in App.tsx (`d90e731`)
- add SYERP sub-nav tab strip (Vendors/Customers/Chart of Accounts) (`d88d55e`)


**Fixed**

- register shadcn color tokens via @theme so Sheet/Dialog/form panels render opaque (Tailwind v4) (`41d2fb7`)
- constrain partner country fields to ISO 2-letter and surface API validation errors in toast (`a3f50da`)
- add catch-all route so unknown paths redirect to Home instead of blank screen (`2e78af8`)


### Phase 5 — PLUM parts & revisions


**Added**

- define PLUM models, schemas, and module stub (`9f793e1`)
- wire PLUM model discovery, seed, and migration 0005 (`4dbc2ce`)
- implement PLUM service layer — CRUD, FSM, label generation (`570ec82`)
- implement PLUM router with RBAC, audit, and revision FSM endpoints (`f0d1a9e`)
- add PlumNav, ArchivePartDialog, and PartSheet components (`f2d988d`)
- add PartsList screen and Wave 0 smoke tests (`38335e3`)
- add NewRevisionDialog and AdvanceStatusDialog (`5435887`)
- add PartDetail route and wire PLUM routes in App.tsx (`011308e`)


**Fixed**

- add missing permissions field to ProtectedRoute test mock (`f5cd61b`)
- register PLUM module in main.py so its router mounts (`37aeba1`)
- enforce Released immutability in Part edit UI (UAT step 10) (`2a75450`)


### Phase 6 — PLUM BOM, costing & integration


**Added**

- extend PLUM models with BOM/AVL/cost tables + openpyxl dep (`3f1da80`)
- author migration 0006 — BOM/AVL/costing tables + revision cost cols (`c7afcdd`)
- add Phase-6 schemas and Wave 0 backend test stubs (PLUM-04..10) (`931ae25`)
- BOM CRUD + traversal + cycle detection + cost copy-forward (`5280576`)
- wire BOM/AVL/cost endpoints in router.py with RBAC + audit (`eb41f35`)
- install Tooltip primitive + BomTree with tree/flat modes + smoke test (`a47ed44`)
- BomLineSheet — add/edit BOM line with part search combobox + inline cycle error (`32bc12a`)
- PriceBreakEditor + AvlLinkSheet — vendor link with inline price breaks (`767263f`)
- implement JSON/Excel export and import parse+validate+commit (`cadbc70`)
- wire export+import endpoints in router.py (`280a31e`)
- extend PartDetail with four Phase-6 section cards (`bad4dbe`)
- add ImportExport page, PlumNav tab, App route, and smoke test (`e157a07`)


### Phase 7 — Close v1.0 gaps


**Fixed**

- invalidate plum parts cache on import commit success (`37b5f97`)
- resolve plum vendor-path ImportError (Partner alias) (`5c33ed8`)
- numeric-safe generate_part_number past digit boundary (`1b8bfa1`)
- cast part-number suffix to Numeric, not Integer (`7562a02`)
- where-used must name the intermediate part (`63ea954`)


### Tooling & developer experience


**Added**

- add interview skill for structured discovery sessions (`5b03d57`)
- add interview skill for structured discovery sessions (`1057373`)


**Fixed**

- pass compose subcommand correctly in uat.ps1 (rename $Args param) (`a17ffc7`)

