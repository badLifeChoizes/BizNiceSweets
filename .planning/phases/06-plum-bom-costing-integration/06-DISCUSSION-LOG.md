# Phase 6: PLUM BOM, Costing & Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-29
**Phase:** 6-PLUM BOM, Costing & Integration
**Areas discussed:** BOM model & structure, Costing/roll-up/margin, Vendor/AVL linking, Import/export

---

## BOM model & structure

### What does a BOM line attach to?
| Option | Description | Selected |
|--------|-------------|----------|
| Parent revision owns BOM | Lines belong to a parent revision; edit on Draft, freeze on Release (D-01); line references child PART → latest released rev | ✓ |
| Revision→revision lines | Each line points to a specific child revision (max traceability, heavier UX) | |
| Part owns BOM (flat) | Lines belong to the part, prototype style; loses freeze-on-release | |

**User's choice:** Parent revision owns BOM.

### What does each BOM line carry?
| Option | Description | Selected |
|--------|-------------|----------|
| Qty + ref des + UoM | Decimal qty + optional reference designators + child UoM shown | ✓ |
| Qty + ref des only | Drop the UoM surfacing | |
| Qty only | Simplest; ref des deferred | |

**User's choice:** Qty + ref des + UoM.

### Child with no released revision?
| Option | Description | Selected |
|--------|-------------|----------|
| Resolve to latest revision | Fall back to latest (Draft) rev, flagged 'unreleased'; provisional cost used in roll-up | ✓ |
| Show as gap | Only released resolve; unreleased shows as gap, parent cost incomplete | |
| Block adding unreleased | Can only add a child once it has a released rev | |

**User's choice:** Resolve to latest revision (provisional). Enables costing a product mid-design.

### BOM edit that would create a cycle?
| Option | Description | Selected |
|--------|-------------|----------|
| Hard-block with message | Reject the edit; graph guaranteed acyclic | ✓ |
| Allow + guard at read | Permit it; make reads cycle-tolerant + warn | |

**User's choice:** Hard-block with message.

---

## Costing, roll-up & margin

### How rich is the per-part cost model?
| Option | Description | Selected |
|--------|-------------|----------|
| Single material cost | One unit cost per revision; assemblies derive via roll-up | ✓ (conditional) |
| Material + labor | Adds flat labor on assemblies | |
| Full prototype range | Material + dev-range + labor (hrs×rate) + costed-date | |

**User's choice:** Single material cost — **on the explicit condition** that the
richer prototype cost features are documented as future-phase (v2) requirements,
not dropped. (User's free-text: "if full prototype range is too large then I want
to be sure that the rest of the prototype features are documented requirement for
later phases.")
**Notes:** Labor, dev-cost ranges, and distributor discount were captured as
deferred → v2. (Vendor price-break costing was later UN-deferred — see AVL.)

### Manual cost on a part that also has a BOM?
| Option | Description | Selected |
|--------|-------------|----------|
| BOM wins, show override | Roll-up always wins on assemblies; manual retained as reference | |
| Manual wins if present | Explicit cost overrides roll-up even on assemblies (buy-vs-make) | ✓ |
| Leaf-only costs | A part with children can't have a manual cost | |

**User's choice:** Manual wins if present. Models purchased sub-assemblies.

### Margin: which parts + where shown?
| Option | Description | Selected |
|--------|-------------|----------|
| Any part, on detail | Any part may carry optional sale price; margin shown on Part Detail | ✓ |
| Finished goods only | Only 'Finished Good'-tagged parts expose price/margin | |
| Dedicated margin view | Separate margin-analysis report screen | |

**User's choice:** Any part, on detail.

### Currency handling?
| Option | Description | Selected |
|--------|-------------|----------|
| Single system currency | One org currency (Phase-3 setting); no per-line currency, no FX | ✓ |
| Per-cost currency, no FX | Each cost stores currency; sum same-currency only, flag mixed | |

**User's choice:** Single system currency.

---

## Vendor / AVL linking

### AVL link shape?
| Option | Description | Selected |
|--------|-------------|----------|
| Link + vendor PN + preferred | Link + vendor part number + preferred flag + notes; no price breaks | |
| Link only | Just the FK | |
| Full prototype AVL | + quantity price-break table (qty/unit cost/lead days) feeding roll-up | ✓ |

**User's choice:** Full prototype AVL.

### Vendor cost vs part cost? (reconciliation of the tension with single-cost)
| Option | Description | Selected |
|--------|-------------|----------|
| Selected vendor drives cost | Selected vendor+break unit cost is the leaf cost; manual is fallback | ✓ |
| AVL rich, cost stays manual | Store price-breaks as reference; roll-up uses manual cost only | |
| Let me rethink AVL scope | Pause and reconsider | |

**User's choice:** Selected vendor drives cost. This un-defers vendor-driven
costing into v1.

### Which break + preferred vs selected?
| Option | Description | Selected |
|--------|-------------|----------|
| One selected vendor+break | One selected vendor + one selected break; preferred = same vendor | |
| Selected vendor, lowest break | Auto-use lowest unit cost | |
| Preferred ≠ selected | Keep two distinct concepts (sourcing vs costing) | ✓ |

**User's choice:** Preferred ≠ selected.

### What freezes on Release (vs D-01 immutability)?
| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot cost value on release | AVL live (part-level); selection revision-controlled; freeze resolved cost number on release | ✓ |
| Whole AVL revision-controlled | Snapshot entire AVL per revision | |
| AVL fully part-level, live cost | Released cost can change with prices (breaks D-01) | |

**User's choice:** Snapshot cost value on release.
**Notes:** User added that the UI/system must ALSO be able to view/use the
**current live cost** when it matters — both the frozen as-released value and a
live recompute must be visible.

---

## Import / export

### Where does it run?
| Option | Description | Selected |
|--------|-------------|----------|
| Server-side endpoints | FastAPI endpoints; transactional, RBAC-gated, audited | ✓ |
| Client-side (SheetJS) | In-browser like the prototype | |
| Hybrid | Server builds/parses, thin client | |

**User's choice:** Server-side endpoints.

### Format scope?
| Option | Description | Selected |
|--------|-------------|----------|
| JSON lossless, Excel multi-sheet | JSON = full lossless round-trip; Excel = human-friendly multi-sheet | ✓ |
| Both fully lossless | Excel mirrors JSON exactly | |
| Per-entity files | Separate parts/BOM/AVL files | |

**User's choice:** JSON lossless, Excel multi-sheet.

### Import reconciliation mode?
| Option | Description | Selected |
|--------|-------------|----------|
| Upsert, never delete | Match on stable keys; update + insert; never hard-delete | ✓ |
| Mode chosen at import | User picks Merge vs Replace per import | |
| Replace-all | Always wipe + restore to match file | |

**User's choice:** Upsert, never delete.

### Import validation & errors?
| Option | Description | Selected |
|--------|-------------|----------|
| Preview then transactional | Upload → validate → preview (new/updated/errors) → confirm → one transaction | ✓ |
| Transactional, no preview | Validate; commit if clean else reject whole file | |
| Partial import | Import valid rows, skip + report invalid | |

**User's choice:** Preview then transactional.

---

## Claude's Discretion

- RBAC split for import/export (export `plum:read` / import `plum:write`) + audit
  event names (D-19).
- Exact `PlumBomItem` / AVL / cost-column schema and where the as-released cost
  snapshot is stored.
- Where-used implementation (recursive CTE vs iterative) + depth/perf guards.
- JSON export schema/versioning; Excel sheet/column layout; spreadsheet library.
- PLUM-scoped vs global placement of the system-currency setting.

## Deferred Ideas

- Labor costing (flat + hours×rate×notes) — → v2 requirement.
- Dev-estimate cost ranges (low/high/avg + costed-date) — → v2 requirement.
- Distributor discount / multi-tier pricing + dedicated margin report — → v2.
- ECO / effectivity (prior Phase-5 deferral); revision→revision BOM lines;
  multi-currency + FX — out of scope this milestone.
- BOM tree / where-used / margin screen layouts — owned by the UI-spec phase, not
  decided here.
