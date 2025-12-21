# PLUM Roadmap

Development phases for the Product Lifecycle Management module.

---

## Overview

PLUM development follows a phased approach:

| Phase | Focus | Status |
|-------|-------|--------|
| 1.0 | Core Migration | Not Started |
| 1.5 | Document Links | Planned |
| 2.0 | Document Management | Planned |
| 2.5 | ECO Workflow | Planned |

---

## Phase 1.0: Core Migration

**Goal:** Port prototype features to production architecture (FastAPI + React + PostgreSQL)

**Status:** Not Started

### Features to Port

All features from prototype `plum/app/plm_v54.html`:

| Feature | Priority | Complexity |
|---------|----------|------------|
| Part CRUD | High | Medium |
| Part Numbers (auto-gen) | High | Low |
| Part Revisions | High | Medium |
| Part Status Workflow | High | Medium |
| BOM Tree View | High | High |
| BOM Flat View | High | Medium |
| Cost Roll-up (with labor) | High | High |
| Where-Used Analysis | High | Medium |
| AVL Management | High | Medium |
| Substitutes | Medium | Medium |
| Product Pricing | Medium | Low |
| Margin Analysis | Medium | Medium |
| Import/Export (JSON) | High | Medium |
| Import (Excel) | Medium | Medium |
| Command Palette | Low | Medium |
| Advanced Search | Medium | Medium |

### Architecture Tasks

| Task | Description |
|------|-------------|
| Database Schema | Create PostgreSQL tables per architecture.md |
| API Endpoints | Implement FastAPI routes |
| React Components | Build UI components |
| State Management | Set up stores |
| SYERP Integration | Connect AVL to vendor master |

### Acceptance Criteria

- [ ] All parts operations work (CRUD, revisions, status)
- [ ] BOM tree and flat views render correctly
- [ ] Cost roll-up matches prototype calculations
- [ ] Where-used shows correct parent assemblies
- [ ] AVL links to SYERP vendors
- [ ] Import/export produces compatible JSON
- [ ] Search and filtering work

---

## Phase 1.5: Document Links

**Goal:** Basic document reference capability (URLs/paths only)

**Status:** Planned

### Features

| Feature | Description |
|---------|-------------|
| Document Link Model | Add `documents` table linked to parts |
| Document Types | Specification, Drawing, Datasheet, Certificate |
| URL/Path Storage | Store reference to external file location |
| Link Management UI | Add/edit/delete document links on parts |
| Link Validation | Verify URL format |

### Not Included (Deferred to 2.0)

- File upload
- Version control
- Preview rendering
- Full-text search

### Acceptance Criteria

- [ ] Can add document links to any part
- [ ] Links display in part detail view
- [ ] Links are clickable (open in new tab)
- [ ] Can categorize by document type
- [ ] Export includes document links

---

## Phase 2.0: Document Management

**Goal:** Full document handling with upload and versioning

**Status:** Planned

### Features

| Feature | Description |
|---------|-------------|
| File Upload | Upload documents to storage |
| Version Control | Track document revisions |
| Preview | In-app preview for PDFs, images |
| Download | Download original files |
| Thumbnails | Visual preview in lists |
| Search | Search by document name, type |
| Storage Backend | S3-compatible object storage |

### Integration

- Link document versions to part revisions
- Show document history
- Bulk upload support

### Acceptance Criteria

- [ ] Can upload files up to 50MB
- [ ] Document versions tracked
- [ ] PDF preview works in-app
- [ ] Image preview works in-app
- [ ] Download preserves original filename
- [ ] Storage backend configurable

---

## Phase 2.5: ECO Workflow

**Goal:** Engineering Change Order process with approvals

**Status:** Planned

### Features

| Feature | Description |
|---------|-------------|
| ECO Creation | Request changes to released parts |
| Impact Analysis | Auto-generate where-used impact |
| Approval Workflow | Submit → Review → Approve/Reject |
| Change Types | Design, Cost, Vendor, Documentation |
| Effectivity Dates | Schedule when changes take effect |
| Audit Trail | Complete history of ECO lifecycle |
| Notifications | Alert approvers of pending ECOs |

### Data Model

```text
ECO
├── id: UUID
├── number: string (auto-gen, e.g., ECO-2025-001)
├── title: string
├── description: text
├── type: ChangeType
├── status: ECOStatus
├── requestedBy: UUID
├── affectedParts: Part[]
├── proposedChanges: Change[]
├── effectiveDate: date
├── approvals: Approval[]
├── created: datetime
└── completed: datetime
```

### ECO Status Workflow

```text
Draft ──► Submitted ──► In Review ──► Approved ──► Implemented
                            │              │
                            └──► Rejected  └──► Closed
```

### Acceptance Criteria

- [ ] Can create ECO from part detail
- [ ] Impact analysis auto-populates affected parts
- [ ] Approval workflow enforced
- [ ] Cannot implement ECO without approval
- [ ] Audit trail complete
- [ ] Notifications sent to approvers

---

## Features NOT in PLUM

These features belong in other modules:

| Feature | Module | Reason |
|---------|--------|--------|
| Manufacturing Facilities | MOUSSE | MES manages production sites |
| Work Centers | MOUSSE | MES manages shop floor resources |
| Production Routings | MOUSSE | MES executes routings |
| Work Instructions | MOUSSE | Shop floor execution docs |
| Quality Checkpoints | CRISP | QMS manages inspections |
| Vendor Master Data | SYERP | ERP owns vendor records |
| Purchase Orders | SYERP | ERP handles procurement |
| Inventory Levels | SYERP | ERP tracks stock |

---

## Dependencies

| Phase | Depends On |
|-------|------------|
| 1.0 | SYERP vendor tables (for AVL FK) |
| 1.5 | Phase 1.0 complete |
| 2.0 | Phase 1.5 complete, Object storage configured |
| 2.5 | Phase 2.0 complete, User roles configured |

---

## Success Metrics

| Metric | Phase 1.0 | Phase 1.5 | Phase 2.0 | Phase 2.5 |
|--------|-----------|-----------|-----------|-----------|
| Parts manageable | Yes | Yes | Yes | Yes |
| BOMs with cost roll-up | Yes | Yes | Yes | Yes |
| Document references | No | Yes | Yes | Yes |
| Document upload/versioning | No | No | Yes | Yes |
| Change control workflow | No | No | No | Yes |
| Multi-user collaboration | Basic | Basic | Basic | Full |