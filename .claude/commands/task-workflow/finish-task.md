Complete the current task, archive it, and create a PR.

## Steps

1. Get current branch name:
   ```bash
   git branch --show-current
   ```

2. Read the task checklist at `docs/tasks/{branch-name}.md`

3. Verify completion:
   - Count total checklist items: `- [ ]` and `- [x]`
   - Count completed items: `- [x]`
   - If not all complete, report:
     ```
     ⚠ Task not complete: {completed}/{total} items done
     
     Remaining:
     - [ ] {item 1}
     - [ ] {item 2}
     
     Complete these items or use `/project:finish-task force` to finish anyway.
     ```

4. If $ARGUMENTS contains "force" OR all items complete, proceed:

5. Run tests if a test command exists:
   ```bash
   # Check for common test commands
   npm test 2>/dev/null || yarn test 2>/dev/null || pytest 2>/dev/null || go test ./... 2>/dev/null || echo "No tests found"
   ```

6. **Update Requirements Progress** (if task has Related Requirements):

   a. Check if task file has `## Related Requirements` section

   b. If yes, extract all requirement IDs listed (e.g., SESS-001, DEV-005)

   c. Read `docs/features/requirements-progress.md`

   d. For each completed requirement ID:
      - Find the row in the progress file
      - Update status: `⬜` → `✅`
      - Add PR/commit reference in the last column
      - Example: `| SESS-001 | ✅ | Four session states | | #{pr-number} |`

   e. Recalculate the Progress Summary table:
      - Count ✅, 🟡, ⬜, 🔴, ⏸️ for each category
      - Update percentage: `(✅ count / Total) * 100`

   f. Report what was updated:
      ```text
      📊 Requirements Progress Updated:
      - SESS-001: ⬜ → ✅
      - SESS-002: ⬜ → ✅
      - SESS-003: ⬜ → ✅

      Sessions: 3/45 → 6.7% complete
      ```

7. Update task file status to "Complete" and move it:
   ```bash
   # Update status in file
   sed -i 's/Status: In Progress/Status: Complete/' docs/tasks/{branch-name}.md

   # Create _completed directory if needed
   mkdir -p docs/tasks/_completed

   # Move with date prefix
   mv docs/tasks/{branch-name}.md docs/tasks/_completed/$(date +%Y-%m-%d)-{branch-name}.md
   ```

8. Commit the archive (include requirements-progress.md if updated):
   ```bash
   git add docs/tasks/ docs/features/requirements-progress.md
   git commit -m "chore: complete {branch-name}"
   ```

9. Push and create PR:
   ```bash
   git push -u origin {branch-name}
   gh pr create --fill
   ```

10. Report completion:
    ```text
    ✓ Task complete: {branch-name}
    ✓ Archived to: docs/tasks/_completed/{date}-{branch-name}.md
    ✓ Requirements progress updated: {count} requirements marked complete
    ✓ PR created: {pr-url}

    Next steps:
    - Review PR and request reviews
    - After merge, clean up: git branch -d {branch-name}
    - If using worktree: git worktree remove ../{project}-{branch-name}
    ```
