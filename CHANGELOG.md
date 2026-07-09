# Changelog

All notable changes to BizNiceSweets.

> **Generated from conventional commits — do not edit by hand.**

Format loosely follows [Keep a Changelog](https://keepachangelog.com/). Only `feat:` and
`fix:` commits appear here; `docs:`/`chore:`/`test:` are omitted.


## [Unreleased] — v2.0 Operations (in progress)


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


## [v1.0] — Foundation + PLUM — *pending tag*

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

