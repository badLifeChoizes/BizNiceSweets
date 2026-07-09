# Work log — Milestone v1.0 (Foundation + PLUM)

**Range:** repo start (`f4e2bd3`, 2025-12-20) → milestone close (2026-07-09)
**Branch at close:** `feature-syerp-inventory-purchasing`
**Definition of done:** "Can deploy it, log in, manage vendors/customers, and design parts with
multi-level BOMs and cost roll-up."

## Effort

| Measure | Value |
|---|---|
| Commits (v1.0 era, through `5e77de5`) | 224 |
| Commits (whole branch incl. Phase 8) | 263 |
| Active days | 18 |
| Inferred work sessions (>90 min idle = new session) | 30 (v1.0) / 34 (all) |
| **Estimated hours** | **≈ 47 h (v1.0)** / ≈ 52 h (all) |

Hours are inferred from commit clustering, not tracked. Run `/zj:timeline` for the visual.

## What shipped

| Phase | Delivered | Requirements |
|---|---|---|
| 0 | PLUM v54 + FLAN v24 prototypes; 7-suite architecture; program roadmap | — |
| 1 | FastAPI + SQLAlchemy async + Alembic; React 19 + Vite + Tailwind 4; module registry; Podman Compose; auto-migrating entrypoint | CORE-01, CORE-09 |
| 2 | JWT two-token auth (PyJWT + Argon2), refresh rotation via httpOnly cookie + single-flight axios interceptor, admin user management, RBAC | CORE-02..05 |
| 3 | AppShell (nav = enabled modules ∩ permissions), admin Settings + Modules, live toggle propagation, always-on SYERP guard | CORE-06..08 |
| 4 | Partner model (vendor/customer flags), Vendors/Customers screens, seeded chart of accounts, SYERP sub-nav; 4 UAT fixes | SYERP-01..05 |
| 5 | Parts CRUD/search, revision FSM with DB-level one-Released invariant, SemVer/ASME labels, tags, audit events | PLUM-01..03 |
| 6 | Multi-level BOM tree/flat/where-used with cycle detection, AVL + price breaks, Decimal cost chain + margin + release snapshot, JSON/Excel import-export | PLUM-04..10 |
| 7 | Partner-alias runtime fix, numeric-safe part numbering, import-commit cache invalidation, traceability reconciliation | PLUM-01 defect, PLUM-07, PLUM-10 |
| — | **Milestone close:** where-used contract fix (G1), API image rebuild (G2), doc-truth corrections | PLUM-06 |

**Changelog:** `CHANGELOG.md` — 98 `feat:`/`fix:` entries, grouped by phase.

## Decisions made, and why

The full record is `.zj/DECISIONS.md` (44 entries, indexed). The ones that shaped v1.0:

- **D-3/D-4** — modular monolith over one shared PostgreSQL DB with SYERP as hub, on
  FastAPI + React, replacing the prototypes' client-side localStorage plan. *Why:* prototypes
  cannot scale to a shared team system; microservices are not worth the ops cost at this scale.
- **D-7** — Milestone 1 = thin foundation **plus** the PLUM port, not plumbing alone. *Why:* the
  milestone should end with a tool someone can actually use.
- **D-8/D-9** — PyJWT + pwdlib[argon2] (not python-jose: CVEs; not passlib: abandoned); the
  backend 403 is the authz boundary, UI gating is convenience. *Why:* security posture belongs
  server-side.
- **D-11/D-13** — all cost/qty math is `Decimal`/`Numeric(18,6)`, never float; effective cost
  resolves vendor price → manual → BOM roll-up → uncosted, frozen at release. *Why:* money.
- **D-12** — one-Released-revision-per-part enforced by a DB partial unique index, not service
  code. *Why:* invariants belong where they cannot be bypassed.
- **D-ADOPT-4** — the HTML prototypes are frozen reference only. *Why:* two live implementations
  of the same domain is a maintenance trap.
- **D-P7-4** — the live-DB pytest harness is broken and its repair is deferred; `verify_*.py`
  standalone scripts substitute. *Why:* real test-infra work, outside the adopted phase scope.
- **D-P7-5** — human UAT moved from a per-phase gate to a milestone-close activity. *Why:* atomic
  bisectable commits make regressions cheap to localize. **This is the decision that caused the
  UAT debt this milestone had to pay off.**
- **D-P7-6** — `part_number` keeps no format constraint, so the auto-numbering `ORDER BY` must
  stay `cast(..., Numeric)`. *Why:* a regex would reject legitimate real-world part numbers; an
  `Integer` cast reintroduces a persistent-500 DoS.
- **D-M1-1** — the v1.0 tag sits at a HEAD that contains Phase 8 (v2.0) work. *Why:* Phase 8 was
  built on the unclosed Phase-7 branch (D-P8-11), so no commit is a clean v1.0 tree; a cherry-pick
  was rejected as cosmetic.
- **D-M1-2** — G1 and G2 fixed at close; G3 deferred to BACKLOG p1.

## Evidence at close

- **Milestone audit:** `.zj/MILESTONE-v1.0-AUDIT.md` — DOD-1..4 driven live against the running
  stack. Verdict: GAPS FOUND → two fixed, one deferred.
- **Live-DB proof:** 66 assertions across five `backend/scripts/verify_*.py`, 0 failures.
- **Suites:** backend `pytest` 90 passed / 98 skipped (D-P7-4); frontend Vitest 54 passed;
  `tsc -b` clean.
- **Artifact health:** `zj doctor` 0 errors (was 18), 20 warnings.

## Gaps found by the milestone audit that seven phase verifications missed

1. **G1 (major, fixed `63ea954`)** — the Where-Used card labelled *every* parent "Direct parent".
   The UI derived its label from `via_part_number`, a field the backend never emitted. The backend
   traversal was correct all along; the UI discarded its answer. No test covered it.
2. **G2 (fixed by image rebuild)** — Excel export 500'd. `openpyxl` is pinned in
   `requirements.txt` but was missing from the running API image.
3. **G3 (deferred, BACKLOG p1 / D-P7-4)** — the live-DB pytest harness skips 98 tests spanning
   auth 38, plum 34, syerp 17, core 7 — not PLUM-only, as the SRD had claimed.

Plus: 18 `zj doctor` artifact errors, a stale `PRD-7` status (`planned` after Phase 8 shipped),
an SRD evidence path to a file that does not exist, and a root instructions file advertising a
"zero-warning" lint policy when both lint gates were non-functional.

## Outstanding at time of writing

- **Human UAT: 2/12** (`.zj/UAT-v1.0.md`). Both known blockers are cleared; the remaining 10
  checks are genuine visual/affordance confirmations. **The tag is not applied until these pass.**
- **G3** — pytest live-DB harness repair (BACKLOG p1).
- **Both lint gates non-functional** (BACKLOG p1).
- **`master` is 263 commits behind** at `f4e2bd3` (2025-12-20) — the entire re-platform is
  unmerged. Merge story unresolved; see `/zj:ship`.
