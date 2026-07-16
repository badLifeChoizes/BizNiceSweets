# Task: feature-crumb-crm-pipeline (Phase 11a — CRUMB CRM & pipeline)

Building CRUMB-01 (inventory-free portion): leads → opportunities → quotes + communication log.
Plan: `.zj/phases/11a-crumb-crm-pipeline/PLAN.md`. AC4 (sales orders + reservation) deferred to 11b.

## Backend
- [x] 1. CRUMB ORM models + aggregate into core/models.py (e57459c)
- [x] 2. Alembic migration 0013 for crumb tables (5391918)
- [x] 3. Seed crumb:read / crumb:write permissions (79fcf31)
- [x] 4. CRUMB Pydantic schemas (3cd5b1f)
- [x] 5. crumb/service package scaffold + _common.py (FSMs, DEFAULT_MARKUP_PCT) (6bbb5d5)
- [x] 6. Leads service — CRUD, archive, customer link/create, convert-to-opportunity (67744c1)
- [x] 7. Opportunities service — CRUD, stage FSM, per-stage list, spawn quote (0dc2ddd)
- [x] 8. Quotes service — header+lines, PLUM price default, QUOTE-#### generator, FSM (e145998)
- [x] 9. Interactions service — append + per-customer timeline (8154c7c)
- [x] 10. Router + self-registration (audit at router layer) (ff88aeb)
- [x] 11. verify_crumb.py — service-level live-Postgres verification — 20/20 PASS (5d9bf05)
- [x] 12. verify_crumb_api.py — HTTP RBAC + audit verification — 50/50 PASS (c9c7855)
- [x] 13. Regression — 13/13 existing verify_*.py exit 0 (assertion task, no commit)

## Frontend
- [x] 14. CrumbNav, routes, hooks, nav gating (402d0482)
- [x] 15. Leads list / sheet / archive (d409d4d)
- [x] 16. Opportunity pipeline + detail (2fef975)
- [x] 17. Quote builder + FSM actions (3550f69)
- [x] 18. Communication-log timeline (1a6fbcd)
- [x] 19. Frontend tests + build gate — 4 crumb tests green, build exit 0 (326dd4a)
