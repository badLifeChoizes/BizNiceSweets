# Concerns

**Analysis Date:** 2026-06-22

Technical debt, risks, and fragile areas observed across the codebase. Severity is a judgement call relative to the project's current goals (free, client-side business tools).

## Technical Debt

| Area | Concern | Evidence | Severity |
|------|---------|----------|----------|
| Monolithic files | All logic for a suite is in one giant HTML file, hard to navigate/refactor/diff | `plum/app/plm_v54.html` ~31,353 lines; `flan/app/prj-mgmt-v24.html` ~11,568 lines | High |
| Global mutable state | Domain modules mutate a shared `DB`/state object directly; no encapsulation | `const DB` at `plum/app/plm_v54.html:2279`, 30+ module objects | High |
| `renderAll()` bottleneck | A single orchestrator re-renders all views on most changes; no granular updates | `renderAll()` at `plum/app/plm_v54.html:18005` | High |
| Code duplication | No shared library — every suite re-implements rendering, persistence, charts, import/export | PLUM vs FLAN both hand-roll SVG charts and JSON I/O | Medium |
| Archive sprawl | 20+ full historical HTML copies per active suite bloat the repo | `plum/archive/`, `flan/archive/` | Medium |
| Inconsistent naming/format | App file naming differs (`plm_v54` vs `prj-mgmt-v24`); indentation inconsistent; no formatter | see `.planning/codebase/CONVENTIONS.md` | Low |
| Misplaced/embedded logic | Business logic lives inside HTML, blocking unit testing or reuse | n/a | Medium |

## Security

| Concern | Detail | Severity |
|---------|--------|----------|
| No authentication / authorization | Apps are open; "users" are just a `plmUsername` string in localStorage. Checkout/checkin is advisory, not enforced | High (for multi-user use) |
| Pervasive `innerHTML` | 145 uses in PLUM, 117 in FLAN; user/imported data rendered as HTML strings → XSS risk if data is untrusted | High |
| CDN scripts without SRI | SheetJS and jsPDF loaded from `cdnjs.cloudflare.com` with no Subresource Integrity hash → supply-chain/tampering risk | Medium |
| Native `prompt`/`confirm`/`alert` for I/O | 53 sites in PLUM; brittle UX and mixes input handling with logic | Low |
| Local-only trust model | All data sits in localStorage / local JSON files; no encryption, no access control | Medium (acceptable for single-user) |

## Performance

| Concern | Detail | Severity |
|---------|--------|----------|
| Full DOM re-renders | `renderAll()` rebuilds large view trees via `innerHTML` on edits → jank on big datasets | High |
| Large data file | `plum/data/plm_database.json` is ~2.7 MB; parsing/holding in memory + localStorage limits (~5–10 MB) are a scaling ceiling | High |
| O(n) lookups | Linear scans over parts/BOM collections instead of indexed maps | Medium |
| Recursive BOM traversal | Deep/where-used BOM walks can be expensive and risk performance cliffs on large assemblies | Medium |

## Fragile Areas

- **Checkout/checkin conflict system** (`plum/app/plm_v54.html:2694`+): advisory locking over a shared JSON file with manual export/import; race conditions and stale `checkedOutBy` state are possible since there's no server arbitration. `forceCheckin()` can override locks.
- **Migration logic:** version-to-version data migration of the 2.7 MB database is high-risk and untested.
- **Recursive BOM / where-used traversal:** correctness depends on clean parent/child references; cycles or orphaned refs could break rendering or loop.
- **Import/export round-trips:** SheetJS/JSON import paths parse external files inside `try/catch` but rely on data shape assumptions; malformed imports may corrupt state.

## Missing Critical Capabilities

- **No automated tests** anywhere (0% coverage) — see `.planning/codebase/TESTING.md`. Refactoring the monoliths has no safety net.
- **No multi-user / real-time collaboration** — only advisory file checkout.
- **No cross-suite data sharing** — suites are fully isolated despite a documented integration vision (`docs/features/INDEX.md`).
- **No real file/attachment storage** — attachments referenced in data have no backing store.
- **5 of 7 suites are empty** (CRUMB, SYERP, MOUSSE, CRISP, GELATO) — scaffolding/docs only, no app.

## Dependency Risks

| Dependency | Risk |
|------------|------|
| SheetJS `xlsx` 0.18.5 (CDN) | Old pinned version; the SheetJS project moved to a non-npm/changed-license distribution after this release. Upgrading path and licensing need review. No SRI hash. |
| jsPDF 2.5.1 (CDN) | CDN availability is a single point of failure; no SRI; offline use breaks if CDN unreachable. |
| Google Fonts (FLAN) | External network dependency for fonts; degrades/fails offline. |

## Priority Recommendations

1. **Add a regression safety net** before any large refactor — start by encoding `docs/features/{suite}/INVARIANTS.md` rules as runnable checks.
2. **Mitigate XSS exposure** — sanitize/escape interpolated data in `innerHTML` paths, especially for imported content.
3. **Pin dependencies with SRI** (or vendor them locally) to remove CDN supply-chain and offline risk.
4. **Plan for data scale** — index hot lookups and watch the localStorage/2.7 MB ceiling for PLUM.
5. **Decide the multi-user story** — current checkout model won't hold up beyond a small, cooperative team.

---

*Concerns analysis: 2026-06-22*
