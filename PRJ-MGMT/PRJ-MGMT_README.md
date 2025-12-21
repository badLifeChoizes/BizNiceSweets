# PRJ-MGMT Tool - Import Templates

## Files Included

### Templates (for creating new projects)
- **project_template.json** - Full project template with sample structure
- **phases_template.csv** - CSV template for importing phases only
- **deliveries_template.csv** - CSV template for importing deliveries only

### Example Project (PLM Development)
- **PLM_Development.json** - Complete project ready to import
- **PLM_Development_phases.csv** - Phases data in CSV format
- **PLM_Development_deliveries.csv** - Deliveries data in CSV format

---

## JSON Format Reference

```json
{
  "id": "unique_id",           // Optional - auto-generated if empty
  "name": "Project Name",      // Required
  "created": "ISO date",       // Optional - auto-set on import
  "modified": "ISO date",      // Optional - auto-set on import
  "phases": [
    {
      "id": 1,                 // Unique number
      "name": "Phase name",    // Phase description
      "progress": 0,           // 0-100 percentage
      "status": "pending"      // "pending", "progress", or "complete"
    }
  ],
  "deliveries": [
    {
      "id": 1,                 // Unique number
      "date": "YYYY-MM-DD",    // Ship date
      "title": "Deliverable",  // What's being delivered
      "destination": "Where"   // Destination/recipient
    }
  ],
  "notes": {
    "focus": "Current focus",
    "milestones": "Upcoming milestones", 
    "future": "Future plans"
  }
}
```

---

## CSV Format Reference

### Phases CSV
```
Phase,Name,Progress,Status
1,Phase Name,0,pending
2,Another Phase,50,progress
3,Done Phase,100,complete
```

**Status values:** `pending`, `progress`, `complete`

### Deliveries CSV
```
Date,Title,Destination
2026-01-15,Deliverable Name,Recipient/Location
```

**Date format:** `YYYY-MM-DD`

---

## How to Import

### Import Full Project (JSON)
1. Open PRJ-MGMT Tool
2. Click **📥 Import** → **Import JSON**
3. Select your `.json` file
4. Project loads with all data

### Import Phases Only (CSV)
1. Open PRJ-MGMT Tool
2. Click **📥 Import** → **Import CSV (Phases)**
3. Select your phases `.csv` file
4. Phases replace current project phases

### Import Deliveries Only (CSV)
1. Open PRJ-MGMT Tool
2. Click **📥 Import** → **Import CSV (Deliveries)**
3. Select your deliveries `.csv` file
4. Deliveries replace current project deliveries

---

## Tips

- Use JSON for complete project backup/restore
- Use CSV for bulk editing in Excel/Google Sheets
- CSV imports replace existing data (phases or deliveries)
- JSON import replaces entire project
- Save your project after importing!
