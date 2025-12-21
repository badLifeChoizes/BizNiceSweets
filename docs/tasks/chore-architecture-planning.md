# Architecture Planning - Suite Roadmaps & Documentation

**Branch:** `chore-architecture-planning`
**Created:** 2025-12-20
**Status:** In Progress

## Goal

Based on the analysis report, interview the user to fully understand the systems and create:
1. An overall ROADMAP for the BizNiceSweets ecosystem
2. Complete `docs/features/{suite}/` documentation for each suite using templates

## Reference Materials

- [Analysis Report](../reports/analysis-report-existing-apps.md)
- [Templates](../../_templates/)

## Suites to Document

| Suite | Status | Priority |
|-------|--------|----------|
| PLUM (PLM) | **Documented** | High |
| FLAN (PRJ-MGMT) | **Documented** | High |
| SYERP (ERP) | Planned | High (receives features from FLAN) |
| CRUMB (CRM) | Planned | Medium |
| MOUSSE (MES) | Planned (receives features from PLUM) | Medium |
| CRISP (QMS) | Planned | Low |
| GELATO (WMS) | Planned | Low |

## Checklist

### Phase 1: Discovery & Interview
- [x] Understand user's business context and use cases
- [x] Clarify integration priorities between suites
- [x] Confirm roadmap corrections from analysis report
- [x] Define timeline/phase expectations (if any)

**Completed:** See [docs/decisions.md](../decisions.md) for all 5 architecture decisions.

### Phase 2: Master Roadmap
- [x] Create `docs/ROADMAP.md` with suite development order
- [x] Define integration milestones
- [x] Document shared infrastructure requirements

**Completed:** See [docs/ROADMAP.md](../ROADMAP.md) and [docs/interviews/roadmap-planning.md](../interviews/roadmap-planning.md) for all 7 new architecture decisions.

### Phase 3: Suite Documentation (Active)
- [x] PLUM: Create `docs/features/plum/README.md` (from template)
- [x] PLUM: Create `docs/features/plum/architecture.md`
- [x] PLUM: Create `docs/features/plum/dependencies.md`
- [x] PLUM: Create `docs/features/plum/INVARIANTS.md`
- [x] PLUM: Create `docs/features/plum/usage.md`
- [x] PLUM: Create `docs/features/plum/ROADMAP.md`
- [x] FLAN: Create `docs/features/flan/README.md`
- [x] FLAN: Create `docs/features/flan/architecture.md`
- [x] FLAN: Create `docs/features/flan/dependencies.md`
- [x] FLAN: Create `docs/features/flan/INVARIANTS.md`
- [x] FLAN: Create `docs/features/flan/usage.md`
- [x] FLAN: Create `docs/features/flan/ROADMAP.md`

**PLUM Completed:** See [docs/features/plum/README.md](../features/plum/README.md) and [docs/interviews/plum-documentation.md](../interviews/plum-documentation.md) for gap analysis.

**FLAN Completed:** See [docs/features/flan/README.md](../features/flan/README.md) and [docs/interviews/flan-documentation.md](../interviews/flan-documentation.md) for gap analysis.

### Phase 4: Suite Documentation (Planned)
- [ ] SYERP: Create complete documentation set
- [ ] CRUMB: Create complete documentation set
- [ ] MOUSSE: Create complete documentation set
- [ ] CRISP: Create complete documentation set
- [ ] GELATO: Create complete documentation set

### Phase 5: Integration Specs
- [ ] Define PLUM <-> MOUSSE integration
- [ ] Define PLUM <-> SYERP integration
- [ ] Define FLAN <-> SYERP integration
- [ ] Define shared vendor/document infrastructure

## Notes

- Templates are in `_templates/` folder
- This is primarily a documentation task
- Will require user input to understand business priorities
