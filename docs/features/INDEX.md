# BizNiceSweets - Suite Index

A collection of free and open source business suite tools with sweet names.

## Suites

| Suite | Name | Description | Status |
|-------|------|-------------|--------|
| PLM | **PLUM** | Product Lifecycle Management | Active (v54) |
| PRJ-MGMT | **FLAN** | Project Management | Active (v24) |
| CRM | **CRUMB** | Customer Relationship Management | Planned |
| ERP | **SYERP** | Enterprise Resource Planning | Planned |
| MES | **MOUSSE** | Manufacturing Execution System | Planned |
| QMS | **CRISP** | Quality Management System | Planned |
| WMS | **GELATO** | Warehouse Management (Goods and Equipment Logistics And Tracking Operation) | Planned |

## Directory Structure

Each suite follows the same structure:

```
{suite}/
├── app/        # Application files (HTML, JS, CSS)
├── archive/    # Version history
├── data/       # Database and data files
├── templates/  # Import/export templates
└── docs/       # Suite-specific documentation
```

## Feature Documentation

- [PLUM Features](plum/README.md) - Product Lifecycle Management
- [FLAN Features](flan/README.md) - Project Management
- [CRUMB Features](crumb/README.md) - Customer Relationship Management
- [SYERP Features](syerp/README.md) - Enterprise Resource Planning
- [MOUSSE Features](mousse/README.md) - Manufacturing Execution System
- [CRISP Features](crisp/README.md) - Quality Management System
- [GELATO Features](gelato/README.md) - Warehouse Management

## Integration Points

The suites are designed to work together:

```
PLUM (Products) ──────┐
                      ├──► SYERP (Core ERP) ──► CRUMB (Customers)
FLAN (Projects) ──────┤         │
                      │         ▼
MOUSSE (Manufacturing)◄────────►GELATO (Warehouse)
                      │         │
                      ▼         ▼
               CRISP (Quality Assurance)
```
