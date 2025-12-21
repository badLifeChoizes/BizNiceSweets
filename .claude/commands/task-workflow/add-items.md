Add checklist items to an existing task, or create a new task from items.

Use this for:
- Adding newly discovered work to a task
- Quick task creation without full ceremony
- Importing specific items from a legacy plan

## Usage

```
/project:add-items {task-name} {items or source}
```

## Examples

### Add items directly:
```
/project:add-items feature-auth "Add password reset endpoint" "Add email verification"
```

### Add from a file reference:
```
/project:add-items bugfix-validation @legacy-plan.md:15-20
```
(Imports lines 15-20 from the file)

### Create new task with items:
```
/project:add-items new:bugfix-csrf "Add CSRF token generation" "Validate tokens on POST"
```

## Process

### If task exists (`docs/tasks/{task-name}.md`):

1. Read existing task file
2. Find the `## Checklist` section
3. Append new items as unchecked: `- [ ] {item}`
4. Save file
5. Report:
   ```
   ✓ Added {n} items to {task-name}
   
   New items:
   - [ ] Add password reset endpoint
   - [ ] Add email verification
   
   Total progress: {done}/{new-total}
   ```

### If task doesn't exist and starts with "new:":

1. Extract task name (e.g., "new:bugfix-csrf" → "bugfix-csrf")
2. Create new task file with provided items
3. Report:
   ```
   ✓ Created new task: bugfix-csrf
   
   Checklist:
   - [ ] Add CSRF token generation
   - [ ] Validate tokens on POST
   
   Start with: /project:start-task bugfix-csrf
   ```

### If referencing a file (@filepath:lines):

1. Parse the reference:
   - `@file.md` = entire file
   - `@file.md:15` = line 15 only
   - `@file.md:15-20` = lines 15-20
   - `@file.md:## Section Name` = all items under that heading

2. Extract checklist items (lines starting with `- [ ]` or `- [x]`)

3. Add to specified task (preserving completion status)

4. Report what was imported:
   ```
   ✓ Imported 5 items from legacy-plan.md (lines 15-20)
   
   Added to feature-auth:
   - [ ] Item from line 15
   - [x] Item from line 16 (already complete)
   - [ ] Item from line 17
   ...
   ```

## Flags (in $ARGUMENTS)

- `--done` : Mark imported items as complete
- `--todo` : Mark imported items as incomplete (override [x])
- `--top` : Add items at top of checklist instead of bottom
- `--note "text"` : Add a note about where items came from

## Example with flags:

```
/project:add-items feature-auth @old-plan.md:## Auth Section --note "Migrated from v1 plan"
```

Results in task file:
```markdown
## Checklist

- [x] Existing item 1
- [ ] Existing item 2
- [ ] Migrated item 1  <!-- Migrated from v1 plan -->
- [ ] Migrated item 2  <!-- Migrated from v1 plan -->
```
