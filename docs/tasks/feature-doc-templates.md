# Feature: Document Templates

## Overview
Add document template upload and export functionality to PLM v56. Users can upload blank document templates (ECO, ECN, BOM, NPR) that the program stores. When exporting a document, users can choose a template format for their facility's specific form requirements.

## Checklist

### Setup
- [x] Create feature branch `feature-doc-templates`
- [x] Create task file

### Core Implementation
- [x] Copy plm_v55.html to plm_v56.html
- [x] Add Document Templates data structure to DB object
- [x] Add template storage using localStorage (base64 encoded files)
- [x] Add nav item for "Doc Templates" section

### Template Management UI
- [x] Create Document Templates view with list of uploaded templates
- [x] Add template type categories (ECO, ECN, BOM, NPR)
- [x] Implement template upload modal with file picker and drag-drop
- [x] Show template preview/metadata
- [x] Add ability to delete templates
- [x] Add field mapping editor for manual cell mappings

### Export Integration
- [x] Add "Export to Template" option when exporting ECO
- [x] Add "Export to Template" option when exporting BOM
- [x] Template selector modal showing available templates for doc type
- [x] Merge document data into template fields (both {{placeholders}} and cell mappings)

### Testing & Polish
- [x] Update version references to v56
- [ ] Test template upload for each type
- [ ] Test export with template selection
- [ ] Verify data persists in localStorage

## Document Types
| Type | Description |
|------|-------------|
| ECO | Engineering Change Order |
| ECN | Engineering Change Notice |
| BOM | Bill of Materials |
| NPR | New Part Request Form |

## Implementation Details

### Template Storage
Templates are stored in `DB.documentTemplates[]` with structure:
```javascript
{
  id: 'tpl_xxx',
  name: 'Facility A ECO Form',
  type: 'ECO', // ECO, ECN, BOM, NPR
  fileName: 'eco_form.xlsx',
  fileData: 'base64...', // Full file stored as base64
  fieldMappings: { 'B5': 'ecoNumber', 'C10': 'title' },
  uploadedAt: '2024-...',
  uploadedBy: 'user'
}
```

### Placeholder System
Users can use `{{fieldName}}` placeholders in their template cells. The system automatically detects these on upload and creates field mappings.

### Available Fields by Type
- **ECO**: ecoNumber, title, description, priority, type, requestedBy, approvedBy, effectiveDate, affectedParts, tasks
- **ECN**: ecnNumber, title, description, changeType, reasonForChange, implementationDate
- **BOM**: assemblyNumber, assemblyName, revision, itemNumber, partNumber, partName, quantity, cost, totalCost
- **NPR**: requestNumber, partName, partType, category, estimatedCost, justification, requiredDate

## Notes
- Templates are Excel files (.xlsx) that users upload
- Each facility may have different form layouts
- Template mapping matches field names to document data via placeholders or manual cell mappings
