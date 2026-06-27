# Phase 5: PLUM Parts & Revisions - Context

**Gathered:** 2026-06-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up the **PLUM module's first real entity** — individual **parts** managed
through their full lifecycle of **revisions and statuses**. This phase creates
the `backend/app/modules/plum/` package (it does not exist yet — only `auth`
and `syerp` modules exist today) and the PLUM frontend screens.

**Delivers (PLUM-01 … PLUM-03):**
- **Parts CRUD** — create / view / edit / soft-delete a part (PLUM-01).
- **Parts search & filter** — server-side debounced search by part number /
  description + status filter + active/archived toggle (PLUM-02).
- **Revision workflow** — create revisions on a part and advance each through
  Draft → In Review → Released → Obsolete, with a visible **revision history**
  on a dedicated part-detail page (PLUM-03).

**NOT in this phase (deferred to Phase 6 / later):**
- **BOM / multi-level product structure, where-used, cost roll-up, margin**
  (PLUM-04…06, PLUM-08…09) — Phase 6. Phase 5 establishes the revision as the
  object Phase 6's BOM and cost will attach to.
- **Vendor/AVL linking** (PLUM-07) — Phase 6.
- **Import/export** (PLUM-10) — Phase 6.
- **ECO / engineering-change-order workflow** — the prototype has ECOs +
  effectivity dates; out of scope here. A free-text "reason for revision" note
  is the lightweight stand-in for change governance in v1.
- **Working iterations / check-in–check-out** (e.g. A.1, A.2 informal versions)
  — not modeled; v1 tracks formal revisions only (see D-03).

</domain>

<decisions>
## Implementation Decisions

### Revision Model
- **D-01: Attribute-snapshot revision model.** A part is a stable header; each
  **revision** is a versioned iteration under it that **freezes a snapshot** of
  the revision-controlled attributes. A **Released** revision is **immutable**.
  Revision history shows **what changed** between revisions (A→B). Chosen over
  "status-only rows" (can't freeze a design, can't show diffs, can't anchor
  Phase 6 BOM to a rev) and over "full rev-controlled / check-in-check-out"
  (heavier than PLUM-03 needs, overlaps Phase 6). This is the industry-aligned
  "PLM-lite" model (Arena / Duro / OpenBOM style).
- **D-02: Stable identity vs revision-controlled split.**
  - *Part-level (stable, shared across all revs, never snapshotted):*
    **part number**, **classification tags** (see D-12).
  - *Revision-controlled (snapshotted per revision):* **description**,
    **category**, **unit of measure**, **notes**, and later (Phase 6)
    **BOM + cost**. Principle locked: the part number is the immutable identity;
    descriptive design data evolves under revision control.
- **D-03: First revision auto-created; copy-forward seed.** Creating a part
  **auto-creates its first revision in Draft** (a part always has ≥1 revision —
  no zero-revision stubs). Creating a *new* revision **copies a prior
  revision's attributes forward** as the editable starting point (default: the
  latest released revision; the user may clone from **any** prior revision —
  this is also the "go back" escape hatch, see D-09). No blank-form revisions.

### Revision & Part Numbering
- **D-04: Revision scheme is a system-wide setting** (built on the Phase-3
  settings infrastructure), with two modes:
  - **SemVer mode** — parts auto-start at revision **`0.1.0`**.
  - **ASME mode** — parts auto-start at revision **`A`** (A, B, C…, **skipping
    I, O, Q, S, X, Z** per ASME Y14.35).
- **D-05: SemVer digit mapping.** In SemVer mode: **MAJOR** bumps on release and
  zeroes the rest (`0.1.0` → `1.0.0` on first release; later `1.1.0` → `2.0.0`);
  **MINOR** bumps for a new in-progress (Draft) revision (`1.0.0` → `1.1.0`);
  **PATCH** for trivial corrections. Released revisions land on clean whole
  numbers (`1.0.0`, `2.0.0`); drafts carry minor/patch.
- **D-06: Part number = auto-prefill + editable + unique.** Mirrors the Phase-4
  partner-code pattern (D-04 Phase 4): system prefills the next sequential part
  number on create, user may override before save, **DB-enforced unique**. No
  format/pattern enforcement in v1 (the prototype's `partNumberPatterns` regex
  is deferred). Part number is distinct from the revision label.

### Status Workflow
- **D-07: Lifecycle states live on the revision** (not the part), so Rev A can
  be Obsolete while Rev B is Released and Rev C is Draft — concurrently. States:
  **Draft → In Review → Released → Obsolete**, plus **reject (In Review →
  Draft)**. Draft is editable; In Review is locked from edits (submitted for
  review); Released is **frozen/immutable**; Obsolete is terminal.
- **D-08: Supersede on release.** Releasing a new revision **auto-obsoletes the
  prior released revision**. Exactly **one revision is in `Released` status**
  per part at any time (= the current effective design). History keeps the
  superseded revision visible as Obsolete.
- **D-09: Forward-only — no revert flag.** There is **no `is_current` /
  revert** mechanism. To "go back" (post-release recall, or a previously
  preferred design becoming preferred again), the user creates a **new forward
  revision**, optionally cloning a prior revision's attributes as the seed
  (D-03). (A revertible-current-pointer design was considered and explicitly
  rejected in favor of this simpler forward-only flow.)
- **D-10: Transitions are `plum:write`-gated and audited.** Status transitions
  and part/revision mutations use `require_permission("plum:write")` and the
  `write_audit` helper (e.g. `part.created`, `revision.released`,
  `revision.obsoleted`), consistent with the medical-device traceability
  posture. Whether the In Review → Released step warrants a finer-grained
  approver permission is planner's discretion.

### Soft Delete
- **D-11: Soft-delete / archive — no hard delete** (carried forward from Phase-4
  D-05). "Delete" archives the part (`active=false` or `archived_at` — planner's
  choice); lists default to active-only with a **show-archived toggle**. Rows
  are retained so Phase-6 FK references (BOM, AVL) never orphan and the audit
  trail stays intact.

### Part Classification (type)
- **D-12: Classification = optional multi-select tags, NOT a required enum.**
  A part carries **zero-or-more** classification tags (part-level, stable).
  Ship a **seeded starter vocabulary** — *Purchased, Manufactured, Assembly,
  Finished Good, Tool* (+ *Raw Material*) — and make the vocabulary **editable
  via a setting** (like the revision-scheme setting, D-04). Tags are
  **organizational** (search / filter / reporting); they do **not** drive
  structural behavior. **⚠ Deliberate divergence from ROADMAP success-criterion
  #1**, which lists "type" as a *required* attribute: the user chose optional
  tags instead because several values (Finished Good, Tool) are orthogonal
  roles, not mutually exclusive procurement types. **The required-to-create
  fields are therefore part number + description.** The verifier/planner should
  treat the classification tag set as satisfying the "type" criterion.
- **D-13: Phase 6 derives make/buy/assembly from the BOM, not the tag.** The
  semantically load-bearing distinction (purchased *leaf* with an entered cost
  vs. *assembly* with a rolled-up cost) is **derived from BOM structure + cost
  data in Phase 6** (a part with children *is* an assembly), so the v1 tags can
  stay purely organizational without breaking Phase-6 cost roll-up.

### Parts UX
- **D-14: List → dedicated Part Detail route.** A parts **list** screen (table:
  part #, classification tag(s), current revision, current status, description)
  → clicking a row opens a **dedicated Part Detail route** showing the part
  header + a **revision-history timeline** + revision actions (new revision,
  advance status). Quick-create a part still uses a sheet/dialog. Chosen over a
  Phase-4-style edit-in-a-sheet because the criteria explicitly call for a "part
  detail page" and revision timelines need room + deep-linkability.
- **D-15: Search & filter reuse the Phase-4 mechanism.** Server-side debounced
  live search across **part number + description**, a **status filter**
  (Draft / In Review / Released / Obsolete — filtering on each part's current
  revision status), and the **active/archived toggle** (D-11). Consistent with
  the Vendors / Customers screens. (A part-type/tag filter facet was considered
  and not added in v1 — see Deferred.)

### Claude's Discretion (delegated to planner/researcher)
- Exact `plum_part` / `plum_part_revision` column sets, types, lengths,
  nullability, indexes (esp. search indexes on part number / description), and
  how the attribute snapshot is stored (e.g. columns on the revision row vs a
  JSON snapshot) — D-01/D-02.
- `active=false` vs `archived_at` timestamp for the soft-delete marker (D-11).
- Unit-of-measure handling (free text vs a seeded UoM list) and whether
  `category` is free text or a controlled field — both revision-controlled per
  D-02; not separately decided.
- Storage of classification tags (join table vs array/JSON) and the exact
  fixed-vs-editable seed-management surface — D-12.
- Whether In Review → Released needs a dedicated approver permission beyond
  `plum:write` (D-10).
- Exact frontend composition of the Part Detail route and revision timeline
  (D-14); precise debounce timing and filter mechanics (D-15).
- Whether the revision-scheme + tag-vocabulary settings are PLUM-scoped or live
  in the global system settings table (D-04, D-12) — align with Phase-3
  settings infrastructure.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements (authoritative)
- `.planning/ROADMAP.md` §"Phase 5: PLUM Parts & Revisions" — phase goal and the
  5 success criteria this phase is verified against (part create w/ required
  attrs & appears in list; edit/delete part; search/filter by #/description/
  status; create revision & advance Draft→Released→Obsolete; revision history
  visible on detail page). **Note the D-12 divergence on "type".**
- `.planning/REQUIREMENTS.md` — PLUM-01 (parts CRUD), PLUM-02 (search/filter),
  PLUM-03 (revisions + status workflow).
- `.planning/PROJECT.md` — locked stack (FastAPI + SQLAlchemy 2.0 + PostgreSQL;
  React/TS/Tailwind/shadcn; TanStack Query), modular-monolith + SYERP-as-hub,
  self-hosted, and the **medical-device audit/traceability posture** that drives
  soft-delete (D-11), immutable released revisions (D-01), and audit logging
  (D-10).

### Prior-phase decisions this phase builds on (authoritative for integration)
- `.planning/phases/04-syerp-core-hub/04-CONTEXT.md` — **the closest analog.**
  D-05 (soft-delete/archive pattern PLUM reuses), D-04 (auto-gen+editable+unique
  code pattern → part number D-06), D-07 (server-side debounced search → D-15),
  D-08 (fill-the-module-stub package layout, `module:action` RBAC, no-`/api/v1`
  prefix rule), D-10 (`write_audit` on mutations). PLUM mirrors all of these.
- `.planning/phases/03-app-shell-settings/03-CONTEXT.md` — settings
  infrastructure (the **revision-scheme setting** D-04 and **tag-vocabulary
  setting** D-12 build on it); nav visibility = module enabled ∩ user permitted
  (the PLUM nav entry + Part Detail route land here).
- `.planning/phases/02-authentication-users/02-CONTEXT.md` — `module:action`
  RBAC + `require_permission(...)` gate + `write_audit` audit-log pattern that
  D-10 reuses (`plum:read` / `plum:write` permissions).
- `.planning/phases/01-project-scaffolding-deployment/01-CONTEXT.md` — single
  Alembic history (one migration adds `plum_part` + `plum_part_revision`),
  module registry (PLUM must register as a module), auto-migrate + idempotent
  seed on startup (the tag-vocabulary / settings seeds follow this).

### Existing code this phase extends (authoritative)
- `backend/app/modules/syerp/{models,schemas,service,router}.py` — **the
  closest backend analog**: a real module package (CRUD + search + archive +
  audit + code-gen + RBAC) to mirror for `backend/app/modules/plum/`.
- `backend/app/modules/auth/{router,service,schemas,dependencies}.py` —
  `require_permission` / `get_current_user` dependencies + service/schema
  patterns the new PLUM routers consume.
- `backend/app/core/models.py` — central model aggregator Alembic imports; the
  new `plum_part` / `plum_part_revision` models MUST be importable here for
  autogenerate discovery.
- `backend/app/core/seed.py` (`run_seeds()`) — idempotent select-before-insert
  seed hook; the classification-tag starter vocabulary + default settings plug
  in here.
- `frontend/src/routes/syerp/Vendors.tsx` / `Customers.tsx` +
  `components/PartnerSheet.tsx`, `PartnerArchiveDialog.tsx`, `SyerpNav.tsx` —
  **the closest frontend analogs**: list + create/edit sheet + archive dialog +
  TanStack Query + shadcn. The Parts list + create sheet follow this; the **Part
  Detail route + revision timeline is net-new UX** (D-14) with no existing
  analog.
- `frontend/src/components/ui/` — installed shadcn primitives to reuse (table,
  dialog/sheet, input, label, select, button, card, badge, switch, separator,
  dropdown-menu); a revision-status **badge** and a **timeline** treatment are
  the likely new UI pieces.

### Reference (informational, not authoritative)
- `plum/app/plm_v54.html` (v54 prototype, ~1.3 MB) — **field-set & UX reference
  only, NOT the target schema.** Useful: part fields (partNumber,
  legacyPartNumber, name, type, category, status, cost, class), the
  draft/released/obsolete status set, and the **revision-diff viewer** (CSS
  `.revision-diff-*`, ~line 989) which illustrates the "what changed A→B" view
  (D-01). Its ECO/effectivity machinery is **out of scope** (Phase 6+).
- `docs/features/plum/` (if present) — high-level PLUM vision; informational.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/modules/syerp/` — copy the module-package shape (models/schemas/
  service/router) wholesale for `plum/`; it already demonstrates CRUD + search +
  archive + audit + auto-code-gen + RBAC against a `syerp_`-prefixed table.
- `core/seed.py` `run_seeds()` idempotent pattern — seed the classification-tag
  starter vocabulary + revision-scheme/tag-vocabulary default settings.
- `require_permission("plum:read"|"plum:write")` — gates new routes (confirm the
  PLUM permissions exist / are seeded alongside the module registration).
- `write_audit(...)` — part + revision mutation audit entries (D-10).
- `frontend/.../syerp/Vendors.tsx` + `PartnerSheet.tsx` — table + create/edit
  sheet + TanStack Query template for the Parts list + quick-create.

### Established Patterns
- **Module-as-package** under `backend/app/modules/<name>/` — create the new
  `plum/` package; register PLUM in the module registry and `core/models.py`.
- **Single Alembic history** — one autogenerated migration adds `plum_part` +
  `plum_part_revision` (+ any tag/setting tables).
- **`plum_` table-name prefix** + `Base` inheritance — required for Alembic
  discovery (per the module conventions documented in the syerp stub).
- **Routers omit `/api/v1`** — `mount_all()` adds it; routes mount under
  `/api/v1/plum/...`.
- **Soft-delete + audit + auto-gen-editable-unique code** — all carried from
  Phase 4.

### Integration Points
- PLUM is a **new module** in the Phase-3 nav shell (visible when enabled ∩
  user has `plum:read`) — the first PLUM nav entry + the Part Detail route.
- `plum_part_revision` is the object **Phase 6 BOM + cost attach to** (D-01) —
  Phase 6 builds the BOM tree and cost roll-up *per revision*, and derives
  make/buy/assembly from BOM structure (D-13).
- The **revision-scheme** + **tag-vocabulary** settings consume the Phase-3
  settings infrastructure (D-04, D-12).
- Phase-6 AVL (PLUM-07) will FK parts/revisions to `syerp_partner` — the
  Phase-4 soft-delete on partners + the Phase-5 soft-delete on parts keep those
  links stable.

</code_context>

<specifics>
## Specific Ideas

- User explicitly wanted **SemVer as a first-class revision option** (auto-start
  `0.1.0`) alongside ASME letters, surfaced as a **user-toggled setting** — a
  deliberate, modern departure from the typical letter-only PLM convention. They
  were previously unaware ASME uses letters and liked having both.
- User designed and then **deliberately simplified** the supersede behavior:
  initially wanted a revertible `is_current` flag (for recalls / re-preferred
  designs) but reconsidered and chose **forward-only revising** (clone a prior
  rev forward) as the cleaner mental model.
- User reframed "part type" from a **required enum into optional metatags**
  (Purchased / Manufactured / Assembly / Finished Good / Tool) after discussing
  that some of those values are orthogonal roles, not mutually exclusive
  procurement types — an intentional, well-reasoned divergence from the literal
  success criterion (D-12).

</specifics>

<deferred>
## Deferred Ideas

- **BOM / multi-level structure, where-used, cost roll-up, margin, AVL linking,
  import/export** — Phase 6 (PLUM-04…10). Phase 5 deliberately shapes the
  revision as the anchor object for these.
- **ECO / engineering-change-order workflow + effectivity dates** — present in
  the prototype; deferred. v1 uses a free-text "reason for revision" note.
- **Working iterations / check-in–check-out** (informal A.1, A.2 versions) — not
  modeled in v1; only formal revisions (D-03).
- **Revertible `is_current` current-release pointer** — designed during
  discussion, then rejected in favor of forward-only revising (D-09). Could
  revisit if recall workflows demand it.
- **Part-number format/pattern enforcement** (prototype `partNumberPatterns`
  regex) — v1 enforces uniqueness only (D-06).
- **Part-type / tag filter facet** on the parts list — considered, not built in
  v1 (D-15); the seeded tags make it a cheap additive later.
- **Distinct approver permission for In Review → Released** — left as
  `plum:write` in v1; finer granularity deferred to planner/later (D-10).

</deferred>

---

*Phase: 5-PLUM Parts & Revisions*
*Context gathered: 2026-06-27*
