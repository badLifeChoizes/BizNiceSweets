Make an intermediate commit with checklist update.

Use this after completing a checklist item to save progress.

## Steps

1. Get current branch:
   ```bash
   git branch --show-current
   ```

2. Verify we're on a task branch (not main/master)

3. Check for uncommitted changes:
   ```bash
   git status --porcelain
   ```

4. If $ARGUMENTS provided, use as commit message context
   Otherwise, infer from recent changes

5. Update the task checklist:
   - Read `docs/tasks/{branch-name}.md`
   - Check off the item that was just completed
   - Save the file

6. Stage all changes:
   ```bash
   git add -A
   ```

7. Create commit with conventional format:
   ```bash
   git commit -m "{type}: {description}

   Progress: {completed}/{total} checklist items"
   ```

   Where {type} is inferred from changes:
   - New files with features → `feat`
   - Bug fixes → `fix`
   - Test files → `test`
   - Documentation → `docs`
   - Config/build → `chore`
   - Code restructuring → `refactor`

8. Report:
   ```
   ✓ Committed: {commit hash}
   ✓ Message: {commit message}
   ✓ Task progress: {completed}/{total}

   Next item: {next unchecked item or "All done! Run /project:finish-task"}
   ```

9. **Invariants Reminder:**

   Check if `docs/features/{feature}/INVARIANTS.md` exists for this task's feature.

   If yes, add a reminder:

   ```text
   ---
   ⚠️ INVARIANTS Reminder:
   This task has {count} invariants that must not be violated.

   Primary: @docs/features/{feature}/INVARIANTS.md
   ```

   If the task has cross-feature dependencies with INVARIANTS:

   ```text
   Dependencies:
   - {dep1}: @docs/features/{dep1}/INVARIANTS.md
   - {dep2}: @docs/features/{dep2}/INVARIANTS.md
   ```

   **Skip this step if:**
   - Restructured docs don't exist for this feature
   - The `--no-invariants` flag is passed

10. **Architecture Update Prompt (optional):**

    If the commit touched files in these paths, prompt:

    - `src/shared/types/*.ts` → "Did you update architecture.md?"
    - `src/main/services/*` → "Did you update architecture.md?"
    - New event types → "Did you add events to architecture.md?"

    ```text
    📝 You modified {file type}. Does architecture.md need updating? (y/n/skip)
    ```

    This is optional and can be skipped with `--no-prompts`.
