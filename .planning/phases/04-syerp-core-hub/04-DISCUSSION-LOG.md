# Phase 4: SYERP Core Hub - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-26
**Phase:** 4-SYERP Core Hub
**Areas discussed:** Record fields, Vendor vs Customer model, Delete behavior, GL skeleton scope

---

## Gray-Area Selection

User selected all four offered areas to discuss: Record fields, Vendor vs Customer
model, Delete behavior, GL skeleton scope. (Search/filter was deliberately offered
as builder's-discretion rather than a discussable area.)

---

## Vendor vs Customer Model

| Option | Description | Selected |
|--------|-------------|----------|
| Separate tables | `syerp_vendor` + `syerp_customer` distinct; both-roles = 2 rows | |
| Unified business partner | One `syerp_partner` with `is_vendor`/`is_customer` flags; both-roles = 1 row | ✓ |
| Separate now, partner-ready | Separate tables v1, designed for additive unified layer later | |

**User's choice:** Unified business partner (Odoo/SAP `res.partner` style).
**Notes:** Discussed first because it shapes the schema for every other area.
Grounded in the user's manufacturing reality where the same company is often both
supplier and customer.

### Follow-up: Partner UI presentation

| Option | Description | Selected |
|--------|-------------|----------|
| Separate Vendor & Customer screens | Two filtered views over the partner table, shared edit form | ✓ |
| Single Partners screen | One list with Vendor/Customer/Both type filter | |
| Both | Focused screens AND a unified Partners view | |

**User's choice:** Separate Vendor & Customer screens.
**Notes:** Keeps the literal success-criteria wording ("vendor list" / "customer
list") while one unified table sits underneath.

---

## Record Fields

| Option | Description | Selected |
|--------|-------------|----------|
| Manufacturer-grade | Identity + address block + primary contact + payment terms / tax ID / currency / country-of-origin / notes | ✓ |
| Lean core | Identity + one contact + active flag only | |
| Let me specify the fields | User dictates exact field list | |

**User's choice:** Manufacturer-grade.
**Notes:** Single embedded address + single primary contact in v1 (not one-to-many).
Align field set with the PLUM prototype's vendor data where non-conflicting.

### Follow-up: Partner code assignment

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-generated, editable | System prefills next sequential code; user may override; unique | ✓ |
| Manual, required | User must type a unique code | |
| Optional / name-only | Code optional; name is primary human identifier | |

**User's choice:** Auto-generated, editable.

---

## Delete Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Soft-delete / archive | `active=false`/`archived_at`; row retained, FKs + audit intact; show-archived toggle | ✓ |
| Soft-delete + guarded hard-delete | Archive by default; hard-delete only when 0 FK references | |
| Hard delete | Physical row removal | |

**User's choice:** Soft-delete / archive.
**Notes:** Chosen explicitly with the medical-device traceability posture in mind;
keeps the PLUM AVL FK (Phase 6) stable.

---

## GL Skeleton Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Seeded standard CoA, browsable | Seeded conventional CoA (5 types, standard ranges), read-only expandable tree | ✓ |
| Seeded + editable | Same seed plus account add/edit/deactivate CRUD | |
| Model + structure only | Table + types + a few sample accounts, no full standard seed | |
| Let me define the CoA | User provides the account structure/numbering | |

**User's choice:** Seeded standard CoA, browsable (read-only).
**Notes:** No GL CRUD, postings, or journal entries in this phase — deferred to a
later financials phase.

---

## Closing check

| Option | Description | Selected |
|--------|-------------|----------|
| Ready for context | Lock decisions, write CONTEXT.md | ✓ |
| Discuss search/filter | Weigh in on search/filter mechanics | |
| Explore more gray areas | Surface another implementation decision | |

**User's choice:** Ready for context. Search/filter left to builder's discretion.

---

## Claude's Discretion

- Search & filter mechanics (server-side query across name/code/contact + active/archived
  filter, debounced live search; client-side acceptable fallback).
- Exact column sets/types/indexes for `syerp_partner` and `syerp_gl_account`.
- Partner code series scheme (unified `P-####` vs role-prefixed display).
- `active=false` flag vs `archived_at` timestamp for the soft-delete marker.
- Precise standard-CoA seed contents and account numbering.
- Whether GL browse rides `syerp:read` or a dedicated permission.
- Frontend composition (separate route files vs shared role-parameterized list).

## Deferred Ideas

- GL account CRUD + ledger postings / journal entries — later financials phase.
- Purchasing, POs, AP/AR, sales orders, inventory, financial reporting — SYERP-extended, out of M1.
- Guarded hard-delete (delete-when-unreferenced) — considered, rejected for v1.
- Multiple addresses / contacts per partner (one-to-many) — additive later change.
- Unified "Partners" management screen (single list + type filter) — left as future option.
