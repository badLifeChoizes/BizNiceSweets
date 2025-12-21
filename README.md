# BizNiceSweets

A collection of free and open source business suite tools with deliciously sweet names.

## Suites

| Suite | Name | Description | Status |
|-------|------|-------------|--------|
| PLM | [**PLUM**](plum/) | Product Lifecycle Management | Active (v54) |
| PRJ-MGMT | [**FLAN**](flan/) | Project Management | Active (v24) |
| CRM | [**CRUMB**](crumb/) | Customer Relationship Management | Planned |
| ERP | [**SYERP**](syerp/) | Enterprise Resource Planning | Planned |
| MES | [**MOUSSE**](mousse/) | Manufacturing Execution System | Planned |
| QMS | [**CRISP**](crisp/) | Quality Management System | Planned |
| WMS | [**GELATO**](gelato/) | Warehouse Management | Planned |

## Quick Start

### Active Suites

**PLUM** - Product Lifecycle Management
- Open [plum/app/plm_v54.html](plum/app/plm_v54.html) in your browser
- [Roadmap](plum/docs/PLM_FEATURE_ROADMAP.md)

**FLAN** - Project Management
- Open [flan/app/prj-mgmt-v24.html](flan/app/prj-mgmt-v24.html) in your browser
- [Roadmap](flan/docs/PRJ-MGMT-Roadmap.md)

## Project Structure

```
BizNiceSweets/
├── plum/           # PLUM - Product Lifecycle Management
├── flan/           # FLAN - Project Management
├── crumb/          # CRUMB - Customer Relationship Management
├── syerp/          # SYERP - Enterprise Resource Planning
├── mousse/         # MOUSSE - Manufacturing Execution System
├── crisp/          # CRISP - Quality Management System
├── gelato/         # GELATO (General Enterprise Location & Asset Tracking Operations) - Warehouse Management
└── docs/
    ├── features/   # Feature documentation per suite
    └── tasks/      # Development task tracking
```

Each suite follows a standard structure:

```
{suite}/
├── app/        # Application files
├── archive/    # Version history
├── data/       # Database files
├── templates/  # Import/export templates
└── docs/       # Suite documentation
```

## Documentation

- [Suite Index](docs/features/INDEX.md) - Overview of all suites and integrations
- [CLAUDE.md](CLAUDE.md) - Development workflow

## Development

### Workflow

This project uses a task-based workflow with conventional commits:

- **Task files:** `docs/tasks/{branch-name}.md`
- **Branch naming:** `feature-*`, `bugfix-*`, `hotfix-*`, `chore-*`
- **Commits:** `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`

### Getting Started

1. Clone the repository
2. Open any suite's HTML app directly in a browser
3. No build tools or dependencies required

## License

Open Source - Free to use, modify, and distribute.
