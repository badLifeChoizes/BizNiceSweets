# Phase 6: PLUM BOM, Costing & Integration - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend the Phase-5 PLUM foundation (Part + Revision tables already exist; **no
cost fields and no BOM/AVL tables yet**) into a full product-structure + costing
module. Delivers **PLUM-04 … PLUM-10**:

- **Multi-level BOM** — add child parts to a parent to build an expandable tree
  (PLUM-04), with a **flat BOM** view that rolls up quantity across all levels
  (PLUM-05).
- **Where-used** — direct *and* indirect parents of a part (PLUM-06).
- **Vendor / AVL linking** — link a part to one or more SYERP vendors with an
  approved-vendor list (PLUM-07).
- **Costing + roll-up** — set a cost on a part and roll it up through the BOM
  to the top assembly (PLUM-08); **margin** analysis (price vs cost) for a
  product (PLUM-09).
- **Import / export** — JSON and Excel, round-tripping the dataset (PLUM-10).

All BOM + cost data is **revision-controlled** (carried from Phase-5 D-01): it
attaches to a part **revision**, and a **Released** revision is immutable.

**NOT in this phase (deferred — see Deferred Ideas):**
- Labor costing, dev-estimate cost ranges, distributor/multi-tier discounting.
- ECO / engineering-change-order workflow + effectivity dates (Phase-5 deferral).
- BOM tree / where-used / margin **screen layouts** — owned by the UI-spec phase
  that follows this discussion (ROADMAP "UI hint: yes").

</domain>

<decisions>
## Implementation Decisions

### BOM Model & Structure
- **D-01: Parent revision owns the BOM.** BOM lines belong to a specific
  **parent part revision**. You edit the BOM on a **Draft** revision; releasing
  it **freezes the structure** (immutable per Phase-5 D-01). A new revision
  copies the prior BOM forward to edit. (Chosen over part-level BOM, which loses
  the freeze-on-release property, and over revision→revision lines, which were
  judged too heavy for v1.)
- **D-02: BOM line references a child PART, resolved at view time.** Each line
  points to a child **part** (not a fixed child revision); the line resolves to
  the child's **latest Released** revision when displayed/rolled-up.
- **D-03: Unreleased children resolve provisionally.** If a child has **no
  Released revision** (still Draft), the line falls back to the child's **latest
  revision**, flagged **"unreleased"** in the tree, and its provisional cost is
  used in roll-up. This lets a product be costed while still in design (essential
  for early quoting). (Chosen over "show as gap" and over blocking the add.)
- **D-04: BOM line payload** = child part + **decimal quantity** (supports
  0.5 kg, 2.3 m raw-material quantities) + optional **reference designators**
  (free text, e.g. `R1,R4,C7`) + the child's **unit of measure** shown for
  context.
- **D-05: Cycles are hard-blocked.** On add/save, detect whether the edit would
  create a cycle (adding A under B when B is already under A) and **reject it
  with a clear message**. The BOM graph is therefore guaranteed acyclic, so
  roll-up and where-used never need cycle-guarding at read time. Where-used
  itself must find **direct AND indirect** parents (ROADMAP criterion #3).

### Costing, Roll-up & Margin
- **D-06: Single material cost per revision.** v1 stores **one unit material
  cost** per part revision (revision-controlled, lives on the revision
  snapshot). No labor / dev-range fields in v1 (see Deferred). **Condition from
  the user:** the deferred richer cost features MUST be written down as
  future-phase requirements, not dropped — see Deferred Ideas.
- **D-07: Effective-cost resolution chain (applies to any part).**
  1. **Selected-vendor price-break cost** (D-11) if a vendor+break is selected;
  2. else the **manually-entered** material cost;
  3. else (if the part has children) the **BOM roll-up** of children;
  4. else **uncosted**.
  Consequence: a **manual cost wins over roll-up** even on an assembly — this
  intentionally supports the **buy-vs-make / purchased sub-assembly** case
  (a part with children that you nonetheless buy as one line). The UI should
  **surface both** the entered cost and the computed roll-up so any divergence
  is visible.
- **D-08: Roll-up = Σ(child effective cost × line quantity)** up the tree,
  evaluated per the resolution chain at each node.
- **D-09: Margin is ungated and shown on Part Detail.** **Any** part revision
  may carry an **optional sale price**; when set, **margin** (price − effective
  cost) and **margin %** are computed and shown on the **Part Detail** page. No
  "finished good" gating (the Phase-5 classification tag is non-load-bearing per
  D-12). (Chosen over finished-goods-only and over a separate margin report.)
- **D-10: Single system currency.** One organization currency (a **Phase-3
  system setting**, default e.g. USD). All costs/prices/roll-ups are in it; bare
  amounts, **no per-line currency, no FX conversion**. Multi-currency is its own
  future project.

### Vendor / AVL Linking
- **D-11: Full AVL link shape.** Each part↔vendor link carries: FK to
  `syerp_partner` + the **vendor's part number** + a **preferred** flag +
  optional notes + a **quantity price-break table** (rows of qty / unit cost /
  lead days). (User chose the full prototype AVL over link-only.)
- **D-12: Vendor-driven costing is IN v1.** A part designates a **selected
  vendor + selected price-break row** (`selectedVendorId` +
  `selectedVendorCostIndex` in prototype terms); that row's unit cost feeds the
  effective-cost chain (D-07 step 1). This **un-defers** the "vendor price-break
  costing" item that would otherwise have been v2.
- **D-13: `preferred` ≠ `selected-for-costing`** (two distinct concepts, per the
  prototype). **`preferred`** is an AVL sourcing designation (can apply to
  several vendors). The **`selected` vendor + break** is the single source that
  drives cost. (User explicitly chose to keep them distinct.)
- **D-14: Freeze cost on Release; always show live cost too.** AVL list +
  price-breaks are **part-level / live** data (current suppliers + current
  prices). The **selected-vendor+break choice is revision-controlled**. On
  **Release**, the **resolved effective cost is snapshotted as a frozen
  as-released number** on the revision (later vendor-price edits do NOT mutate a
  released revision's cost — honors D-01). **The UI MUST additionally surface the
  live/current recomputed cost** alongside the frozen one (e.g. "released at $X,
  current would be $Y") so the user can decide whether to revise. **Draft**
  revisions always show live cost. (User's explicit refinement.)

### Import / Export
- **D-15: Server-side endpoints.** Import/export are **FastAPI endpoints**
  (not client-side SheetJS like the prototype). Export streams a generated file;
  import accepts an upload, validates, and writes to Postgres in a transaction.
  RBAC-gated and audited (see D-19). (Architecture is now client-server; backend
  owns the data.)
- **D-16: JSON lossless, Excel multi-sheet.** **JSON** = the **full lossless
  round-trip** of the entire PLUM dataset (parts, all revisions, BOM lines,
  AVL + price-breaks, tags, costs) — this is what satisfies "restore the same
  dataset" (PLUM-10 criterion #7) and serves as backup/migration. **Excel** =
  a **human-friendly multi-sheet** workbook (Parts, BOMs, AVL) that round-trips
  the practical fields for bulk view/edit. (Built server-side, e.g. openpyxl.)
- **D-17: Upsert, never delete.** Import matches on stable keys (**part number**;
  BOM by **parent-rev + child**; AVL by **part + vendor**), **updates** existing
  rows and **inserts** new ones, and **NEVER hard-deletes** rows absent from the
  file. Both JSON and Excel use this. Honors the standing soft-delete /
  no-hard-delete + audit posture; "restore the same dataset" holds for
  additive/edit restores. (Chosen over replace-all and over a per-import
  mode toggle.)
- **D-18: Preview-then-transactional commit.** Import is two-step: **upload →
  server validates → returns a PREVIEW** (N new, M updated, K errors with
  row-level messages, e.g. "BOM row references unknown part", "AVL vendor not in
  SYERP") **→ user confirms → commit in ONE all-or-nothing transaction** (any
  unresolved error blocks the commit). (Chosen over no-preview transactional and
  over partial/skip-invalid import.)

### Claude's Discretion (delegated to planner/researcher)
- **D-19:** [informational] Exact RBAC split — export likely `plum:read`, import `plum:write`;
  audit events for import/export (e.g. `plum.imported`, `plum.exported`) using
  the existing `write_audit` helper.
- Exact table/column design: `PlumBomItem` (parent_revision_id, child_part_id,
  qty NUMERIC, ref_des, ...), the AVL tables (part↔vendor link + price-break
  rows), and **where the single material cost + sale price columns live on the
  revision snapshot** — all per D-01/D-06.
- How the **as-released cost snapshot** (D-14) is stored (a frozen numeric column
  on the revision set at release time) vs the live-recompute path.
- Where-used implementation (recursive CTE vs iterative) and any practical
  depth/perf guards on deep trees.
- JSON schema/versioning for the lossless export; Excel sheet/column layout and
  the openpyxl-vs-alternative library choice.
- Whether the system-currency setting is PLUM-scoped or global (align with
  Phase-3 settings infra), per D-10.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements (authoritative)
- `.planning/ROADMAP.md` §"Phase 6: PLUM BOM, Costing & Integration" — phase goal
  and the **7 success criteria** this phase is verified against (BOM tree;
  flat BOM qty roll-up; direct+indirect where-used; AVL vendor linking; cost
  set + roll-up; margin for a finished product; JSON/Excel export+re-import
  restoring the same dataset).
- `.planning/REQUIREMENTS.md` — **PLUM-04** (multi-level BOM tree), **PLUM-05**
  (flat BOM qty roll-up), **PLUM-06** (where-used), **PLUM-07** (vendor/AVL FK to
  SYERP), **PLUM-08** (cost + roll-up), **PLUM-09** (margin), **PLUM-10**
  (JSON+Excel import/export). Also the **`## v2 Requirements`** section — the
  deferred cost features (D-06) should be promoted here (see Deferred Ideas).
- `.planning/PROJECT.md` — locked stack (FastAPI + SQLAlchemy 2.0 + PostgreSQL;
  React/TS/Tailwind/shadcn; TanStack Query), modular-monolith with **SYERP as the
  hub** (the AVL FK target), self-hosted, and the **medical-device audit /
  traceability posture** that drives revision-controlled BOM/cost (D-01),
  immutable as-released cost (D-14), soft-delete-on-import (D-17), and audit
  logging (D-19).

### Prior-phase decisions this phase builds on (authoritative for integration)
- `.planning/phases/05-plum-parts-revisions/05-CONTEXT.md` — **the direct
  predecessor.** D-01 (attribute-snapshot revisions; Released = immutable — BOM
  + cost are the revision-controlled data this phase adds), D-02 (stable-identity
  vs revision-controlled split — BOM/cost are revision-controlled), D-03
  (copy-forward on new revision — the BOM copies forward, D-01 here), D-08
  (one Released revision per part — what D-02 resolves to), **D-13 (make/buy/
  assembly DERIVED from BOM + cost, not from the tag — the basis for D-07's
  "has children ⇒ assembly" roll-up)**, D-10/D-11 (`plum:write` RBAC + audit +
  soft-delete reused).
- `.planning/phases/04-syerp-core-hub/04-CONTEXT.md` — the **vendor master**
  (`syerp_partner`, `active` soft-delete, `is_vendor`) that PLUM-07 AVL links FK
  to; the server-side-search + soft-delete + audit + module-package patterns.
- `.planning/phases/03-app-shell-settings/03-CONTEXT.md` — **settings
  infrastructure** the **system-currency setting** (D-10) builds on; module
  enable/disable + permission-filtered nav (BOM/cost screens land under the
  existing PLUM nav).
- `.planning/phases/02-authentication-users/02-CONTEXT.md` —
  `require_permission(...)` gate + `write_audit` pattern reused by every new
  endpoint (D-19).
- `.planning/phases/01-project-scaffolding-deployment/01-CONTEXT.md` — single
  Alembic history (one migration adds the BOM + AVL + cost columns/tables),
  module registry, `core/models.py` aggregator import requirement.

### Existing code this phase extends (authoritative)
- `backend/app/modules/plum/models.py` — **`PlumPart`** (id, part_number unique,
  `active`) and **`PlumPartRevision`** (part_id, revision_number, revision_label,
  status, description/category/uom/notes, released_at/obsoleted_at; the
  `uq_plum_part_one_released` partial unique index) — **the snapshot to add cost +
  sale-price columns to, and the parent the new `PlumBomItem` / AVL tables FK to.
  No cost/BOM columns exist yet.**
- `backend/app/modules/plum/service.py` — revision FSM, `create_revision`
  copy-forward (line ~613), `advance_revision_status` supersede-on-release
  (line ~707) — **the release path D-14 hooks into to snapshot the as-released
  cost**; `generate_part_number` code-gen pattern.
- `backend/app/modules/plum/{schemas,router,seed}.py` — schema/endpoint/seed
  patterns (RBAC + audit logging at router lines ~22-31) to mirror for BOM,
  AVL, costing, and import/export endpoints.
- `backend/app/modules/syerp/models.py` — **`syerp_partner`** (id, `active`,
  `is_vendor`, `currency`) — the AVL FK target (D-11).
- `backend/app/core/models.py` (aggregator — new tables must be importable here
  for Alembic autogenerate) and `backend/app/core/seed.py` (idempotent
  select-before-insert; system-currency default setting plugs in here).
- `frontend/src/routes/plum/PartDetail.tsx` — the part-header + revision-timeline
  page; **margin (D-09), the BOM tree, AVL, and cost surfaces attach here.**
- `frontend/src/routes/plum/PartsList.tsx` + `components/` (PartSheet,
  NewRevisionDialog, AdvanceStatusDialog, PlumNav) and
  `frontend/src/components/ui/` (table, dialog, sheet, select, badge, card,
  switch, separator, dropdown-menu installed) — reusable building blocks; a
  **BOM tree** and **price-break editor** are the likely net-new UI pieces (UI
  phase).

### Reference (informational, NOT the target schema)
- `plum/app/plm_v54.html` (v54 prototype) — **field-set & behavior reference
  only.** Useful analogs validated during scout: `BomConfigurations` /
  `addToBom` / `generateFlatBom` (recursive roll-up with `visitedIds` cycle
  guard, ~line 3894), `getWhereUsed` (~line 3814), `getEffectiveCost`
  (selected-vendor → released → avg chain, ~line 3669 — basis for D-07/D-12),
  `partVendors` price-break shape (~line 3418 — basis for D-11), `ExportManager`
  + SheetJS export/import (~line 17135, `handlePartsImport`/`handleBomsImport`
  ~line 25773). **Its labor/dev-range/ECO machinery is OUT of scope** (Deferred).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/modules/plum/` — extend the existing module package (don't create
  a new one): add BOM/AVL models + cost columns, new service functions, new
  router endpoints, following the established CRUD+RBAC+audit shape.
- `core/seed.py` idempotent `run_seeds()` — seed the **system-currency** default
  setting (D-10).
- `require_permission("plum:read"|"plum:write")` + `write_audit(...)` — gate and
  audit every new endpoint (BOM edit, AVL edit, costing, import/export) — D-19.
- `syerp_partner` (vendor master) — AVL FK target; reuse its `is_vendor`/`active`
  semantics so archived vendors don't orphan AVL links.
- `PartDetail.tsx` + installed shadcn primitives — host the BOM tree, AVL editor,
  cost/margin surfaces.

### Established Patterns
- **Revision-controlled snapshot** (Phase-5 D-01/D-02) — BOM lines + cost +
  sale price + selected-vendor choice attach to the **revision**; the release
  path freezes them (D-14).
- **Single Alembic history** — one autogenerated migration adds the BOM table,
  AVL tables, and the cost/sale-price columns; new models must be imported in
  `core/models.py`.
- **`plum_` table-name prefix** + `Base` inheritance for Alembic discovery.
- **Routers omit `/api/v1`** — `mount_all()` adds it; new routes mount under
  `/api/v1/plum/...`.
- **Soft-delete + audit** carried throughout, including import (D-17 never
  hard-deletes).

### Integration Points
- **PLUM ↔ SYERP**: AVL links FK `plum` part → `syerp_partner` — the first real
  cross-module foreign key (validates "SYERP as hub"). Import (D-18) must
  validate that referenced vendors exist in SYERP.
- **PLUM ↔ Phase-3 settings**: the **system-currency** setting (D-10).
- **Within PLUM**: BOM lines reference other PLUM parts (self-referential tree);
  cost roll-up + where-used traverse it; the release FSM (Phase-5) is where the
  as-released cost snapshot is taken (D-14).

</code_context>

<specifics>
## Specific Ideas

- **User wants nothing silently dropped.** When offered the lean single-cost
  model, the user accepted it **only on condition** that the richer prototype
  cost features (labor, dev-cost ranges, distributor discount) are **documented
  as future-phase requirements** — promote them into `REQUIREMENTS.md` v2. This
  is a standing expectation for the whole phase, not just costing.
- **Buy-vs-make matters to the user.** They deliberately chose "manual cost wins
  over roll-up even on assemblies" (D-07) to model **purchased sub-assemblies**.
- **The user values historical + live cost together** (D-14): "Snapshot cost
  value on release is preferred for tracking historical costs and state at the
  time… as long as the UI allows the user and the system to view/use the current
  cost when it matters." Both the frozen as-released cost and a live recompute
  must be visible.
- **Vendor sourcing realism**: the user kept the full AVL with price-breaks and
  the distinct `preferred` vs `selected-for-costing` concepts (D-11/D-13),
  pulling vendor-driven costing into v1 (D-12).

</specifics>

<deferred>
## Deferred Ideas

**These came up and are real PLM capabilities — to be promoted into
`.planning/REQUIREMENTS.md` under `## v2 Requirements` (user's explicit
condition on D-06), not dropped:**

- **Labor costing** — flat labor cost on assemblies, and the full
  hours × rate × notes machinery (prototype `laborCost/laborHours/laborRate/
  laborNotes`); roll-up of labor up the tree.
- **Dev-estimate cost ranges** — low / high / avg cost with a costed-date
  (prototype `costLow/costHigh/costAvg/costedDate`) for early-design estimating
  before a released cost exists.
- **Distributor discount / multi-tier pricing** (prototype `distributorDiscount`)
  and a dedicated **margin-analysis report screen** (vs the inline-on-detail
  margin shipped in v1, D-09).

**Out of scope for this milestone (prior deferrals / other phases):**
- **ECO / engineering-change-order workflow + effectivity dates** — Phase-5
  deferral; still out.
- **Revision→revision BOM lines** (freezing exact child rev per line, D-01) —
  considered, not adopted in v1; revisit if true as-built traceability is needed.
- **Multi-currency + FX conversion** (D-10) — its own future project.
- **BOM tree / where-used / margin SCREEN layouts** — not deferred, but owned by
  the **UI-spec phase** that follows this discussion (ROADMAP "UI hint: yes"),
  not decided here.

</deferred>

---

*Phase: 6-PLUM BOM, Costing & Integration*
*Context gathered: 2026-06-29*
