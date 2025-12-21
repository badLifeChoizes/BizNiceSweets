# PLUM Invariants

Rules that must ALWAYS be true. Violating any of these breaks the module.

**Read this entire file before implementing any PLUM-related code.**

---

## Part Identity

| Rule | If You Break It |
|------|-----------------|
| Part numbers must be unique across all revisions | Duplicate parts, data corruption |
| Part numbers are immutable after creation | Broken references, lost traceability |
| Revision sequence must be monotonic (A → B → C) | Confusing version history |

**Implementation:** Part number + revision = unique identifier

---

## Part Status Workflow

| Rule | If You Break It |
|------|-----------------|
| Only Draft parts can be edited | Uncontrolled changes to released products |
| Only Draft parts can be deleted | Orphaned BOM references |
| Released parts cannot return to Draft | Audit trail broken |
| Obsolete is terminal (no transitions out) | Zombie parts reappearing |

**Implementation:** Status transitions enforced at API level

```python
# Valid transitions only
VALID_TRANSITIONS = {
    'Draft': ['Released', 'Deleted'],
    'Released': ['Obsolete'],  # Revise creates NEW part
    'Obsolete': []  # Terminal state
}
```

---

## BOM Integrity

| Rule | If You Break It |
|------|-----------------|
| No circular BOM references | Infinite loops in cost calculation |
| BOM items must reference existing parts | Orphaned BOM entries |
| Quantity must be > 0 | Nonsensical BOMs |
| Cannot delete a part used in any BOM | Broken product structures |

**Implementation:** Circular reference check on BOM add/update

```python
def check_circular(parent_id, child_id, visited=set()):
    """Prevent A → B → C → A cycles."""
    if child_id == parent_id:
        raise ValidationError("Circular reference detected")
    if child_id in visited:
        return  # Already checked this branch
    visited.add(child_id)
    for grandchild in get_bom_children(child_id):
        check_circular(parent_id, grandchild, visited)
```

---

## Cost Calculations

| Rule | If You Break It |
|------|-----------------|
| Cost roll-up must include ALL BOM levels | Incorrect product costs |
| Labor costs must be included at each assembly level | Understated costs |
| Costs must never be negative | Financial errors |
| Cost calculation must handle circular refs gracefully | Application crash |

**Implementation:** Visited set prevents infinite recursion

---

## AVL (Approved Vendor List)

| Rule | If You Break It |
|------|-----------------|
| AVL vendor_id must reference valid SYERP vendor | Orphaned AVL entries |
| At least one AVL entry should be Approved or Preferred for purchased parts | Unbuildable products |
| Disqualified vendors cannot be selected for new orders | Quality/compliance issues |

**Implementation:** Foreign key constraint + status validation

---

## Substitutes

| Rule | If You Break It |
|------|-----------------|
| A part cannot be its own substitute | Logical error |
| Substitute relationships are directional (A substitutes B ≠ B substitutes A) | Unexpected swaps |
| Only approved substitutes should be used in production | Quality issues |

---

## Where-Used

| Rule | If You Break It |
|------|-----------------|
| Where-used must reflect current BOM state | Incorrect impact analysis |
| Where-used query must be efficient (indexed) | Slow UI, timeouts |

**Implementation:** Index on `bom_items.child_part_id`

---

## Data Import/Export

| Rule | If You Break It |
|------|-----------------|
| Export must include all related data (BOMs, AVL, substitutes) | Incomplete backups |
| Import must validate all constraints | Corrupt data |
| Import must not create duplicates | Data bloat |
| Import must preserve part number stability | Broken references |

---

## Document Links (Phase 1.5)

| Rule | If You Break It |
|------|-----------------|
| Document URLs must be validated format | Broken links |
| Documents linked to Released parts are read-only references | Confusion about doc versions |

---

## Quick Reference

**Total invariants:** 22

**Most critical:**

1. No circular BOM references (causes infinite loops)
2. Part numbers are immutable (breaks all references)
3. Only Draft parts can be edited (maintains release integrity)

**Common violations to watch for:**

- Allowing BOM edits on Released parts via API bypass
- Deleting parts without checking where-used
- Importing data without circular reference validation
- Calculating costs without visited set (stack overflow)
- Allowing negative quantities in BOMs

---

## Validation Checklist

Before deploying changes, verify:

- [ ] Part status transitions follow allowed paths
- [ ] BOM operations check for circular references
- [ ] Delete operations check where-used first
- [ ] Cost calculations use visited set for recursion
- [ ] Import validates all constraints before committing
- [ ] AVL entries reference valid vendor IDs