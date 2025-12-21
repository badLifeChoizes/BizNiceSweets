# Establish Integrated Suite Structure

**Branch:** `chore-suite-structure`
**Created:** 2025-12-20
**Status:** Complete

## Goal

Restructure BizNiceSweets as a parent project containing integrated business suites (PLM, PRJ-MGMT, ERP, MES, CRM, etc.) with consistent directory structure and documented features/requirements.

## Checklist

- [x] Define standard suite directory structure
- [x] Reorganize existing PLM suite
- [x] Reorganize existing PRJ-MGMT suite
- [x] Create skeleton directories for future suites (ERP, MES, CRM)
- [x] Create docs/features/INDEX.md with suite overview
- [x] Document existing PLM features and requirements
- [x] Document existing PRJ-MGMT features and requirements
- [x] Create placeholder feature docs for future suites
- [x] Update root README.md with new structure
- [x] Commit changes

## Acceptance Criteria

- Each suite has consistent directory structure
- Existing tools (PLM, PRJ-MGMT) remain functional
- Feature documentation exists for each suite
- Clear separation between suites while maintaining integration points

## Notes

Suites to include:
- **PLM** - Product Lifecycle Management (existing, v54)
- **PRJ-MGMT** - Project Management (existing, v24)
- **ERP** - Enterprise Resource Planning (planned)
- **MES** - Manufacturing Execution System (planned)
- **CRM** - Customer Relationship Management (planned)

## Related

- Depends on: initial project setup (complete)
