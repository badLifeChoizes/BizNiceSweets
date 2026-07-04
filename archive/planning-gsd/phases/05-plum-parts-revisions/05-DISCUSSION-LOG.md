# Phase 5: PLUM Parts & Revisions - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-27
**Phase:** 5-PLUM Parts & Revisions
**Areas discussed:** Revision model, Status workflow, Numbering schemes, Parts UX shape, Part classification

---

## Revision Model

### Q1 — What does a revision capture?

| Option | Description | Selected |
|--------|-------------|----------|
| Status-only rows | Child table of rev label + status + dates + notes; part attrs shared/mutable | |
| Attribute snapshot | Each revision freezes a snapshot of part attrs; released revs immutable; history shows diffs | ✓ |
| Full rev-controlled fields | Revision is primary versioned object w/ check-in/check-out; part is a header | |

**User's choice:** Attribute snapshot (after requesting industry-standard background).
**Notes:** User first asked for an explainer on how real PLM systems (Windchill, Teamcenter, Arena, Duro, OpenBOM) handle revisions. Chose the "PLM-lite" attribute-snapshot model as the industry-aligned sweet spot — immutable released revs + real history + clean Phase-6 BOM/cost anchor, without check-in/check-out machinery.

### Q2 — Stable identity vs revision-controlled fields

| Option | Description | Selected |
|--------|-------------|----------|
| Number stable, rest rev'd | Part-level: number, type. Rev-controlled: description, category, UoM, notes (+ Phase-6 BOM/cost) | ✓ |
| Minimal rev-control | Part-level: number, type, description, category. Rev-controlled: status + notes + dates only | |
| You decide | Delegate split; lock only that part number is stable identity | |

**User's choice:** Number stable, rest revision-controlled.

### Q3 — First-revision creation + new-revision seed

| Option | Description | Selected |
|--------|-------------|----------|
| Auto Rev A + copy-forward | Part auto-creates first rev in Draft; new revs copy prior released rev forward | ✓ (effectively) |
| Auto Rev A + blank new rev | Auto first rev; new revs start blank | |
| Explicit first rev | Part can exist with zero revs; user creates Rev A explicitly | |

**User's choice:** Free-text — user redirected to numbering, but confirmed "auto rev" (auto-create first revision). Copy-forward retained as default; clone-from-any-prior-rev added as the "go back" escape hatch.
**Notes:** User pivoted here into numbering preferences (see Numbering schemes Q1).

---

## Numbering Schemes

### Q1 — Revision numbering scheme (raised via free-text during Rev Model Q3)

**User's choice (free-text):** "I like semantic versioning but I didn't know that ASME use letters, so let's make it a user toggled setting and do auto rev 0.1.0 for semVer as the format and auto rev A for the ASME."
**Notes:** Revision scheme = system-wide setting. SemVer mode auto-starts `0.1.0`; ASME mode auto-starts `A` (skips I/O/Q/S/X/Z per ASME Y14.35 — user was unaware ASME used letters).

### Q2 — SemVer digit mapping

| Option | Description | Selected |
|--------|-------------|----------|
| Major=release, minor=draft | Release bumps MAJOR + zeroes rest; new draft bumps MINOR; PATCH for trivial fixes | ✓ |
| Minor=release, patch=fix | New rev bumps MINOR; corrective re-release bumps PATCH; MAJOR manual | |
| User-defined bump | User chooses which digit to bump per revision | |

**User's choice:** Major=release, minor=draft.

### Q3 — Part number assignment

| Option | Description | Selected |
|--------|-------------|----------|
| Auto + editable, unique | Prefill next sequential, user can override, DB-unique, no format rule | ✓ |
| Auto + editable + format rule | Same + configurable format/pattern enforcement | |
| Manual only, unique | User always types; uniqueness only | |

**User's choice:** Auto + editable + unique (mirrors Phase-4 partner codes).

---

## Status Workflow

### Q1 — Lifecycle states

| Option | Description | Selected |
|--------|-------------|----------|
| Draft→InReview→Released→Obsolete | Four states w/ review gate + reject-to-draft | ✓ |
| Draft→Released→Obsolete | Literal three states, no review gate | |
| You decide | Delegate exact set | |

**User's choice:** Draft → In Review → Released → Obsolete (with reject to Draft). Status lives on the revision.

### Q2 — Supersede behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-obsolete prior | Releasing a new rev auto-obsoletes the prior released rev; one current released rev | ✓ (final) |
| Manual obsolete | Release doesn't touch prior; user obsoletes manually | |
| You decide | Delegate; lock single unambiguous current rev | |

**User's choice:** Initially asked for auto-obsolete **plus** a revertible `is_current` flag (to switch current release back to a prior rev for recalls / re-preferred designs). **Then reconsidered and simplified** to plain auto-obsolete + forward-only revising — "if something like I described happens it's best the user just keeps forward revising even if they have to clone a previous revision." No `is_current` / revert flag.

---

## Parts UX Shape

### Q1 — Screen structure

| Option | Description | Selected |
|--------|-------------|----------|
| List → detail route | List → dedicated Part Detail route w/ revision-history timeline + actions; quick-create via sheet | ✓ |
| List + expanding sheet | List + large slide-over holding fields + revision sub-section; no separate route | |
| You decide | Delegate composition | |

**User's choice:** List → dedicated Part Detail route.

### Q2 — Search & filter

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse Phase-4 pattern + status filter | Server-side debounced search (#/description) + status dropdown + active/archived toggle | ✓ |
| Search + status + type filters | Same + a part-type filter facet | |
| You decide | Delegate facets | |

**User's choice:** Reuse Phase-4 pattern + status filter.

---

## Part Classification (raised during the "Done" check)

### Q1 — Part type values

**User's choice (free-text):** "I want them to work as metatags instead of being a required field. I like purchased/manufactured/assembly/finished-good/tool. Do you have any insight on this…"
**Notes:** User reframed "type" from a required single enum into **optional multi-select metatags** after a discussion of why some values (Finished Good, Tool) are orthogonal roles, not mutually exclusive procurement types. Deliberate divergence from ROADMAP criterion #1.

### Q2 — Tag model

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-tag, optional, seeded + editable | Zero+ tags; seeded vocabulary; editable via setting; organizational only | ✓ |
| Multi-tag, optional, fixed list | Same but fixed enum, no user-editable vocabulary | |
| You decide | Delegate fixed-vs-editable + storage | |

**User's choice:** Multi-tag, optional, seeded + editable. Phase 6 derives make/buy/assembly from BOM structure, not from the tag.

---

## Claude's Discretion

- Exact `plum_part` / `plum_part_revision` schema (columns, types, indexes, snapshot storage mechanism).
- Soft-delete marker (`active=false` vs `archived_at`).
- Unit-of-measure + category field handling (free text vs controlled).
- Tag storage (join table vs array/JSON) and seed-management surface.
- Whether In Review → Released needs a dedicated approver permission beyond `plum:write`.
- Part Detail route + revision timeline composition; debounce/filter mechanics.
- Whether revision-scheme + tag-vocabulary settings are PLUM-scoped or global.

## Deferred Ideas

- Phase 6: BOM, where-used, cost roll-up, margin, AVL linking, import/export.
- ECO workflow + effectivity dates (prototype has them; v1 uses a free-text reason note).
- Working iterations / check-in–check-out.
- Revertible `is_current` current-release pointer (designed, then rejected for forward-only).
- Part-number format/pattern enforcement.
- Part-type/tag filter facet on the list.
- Distinct approver permission for In Review → Released.
