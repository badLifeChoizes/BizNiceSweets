Show the current task status and checklist progress.

## Steps

1. Get current branch:
   ```bash
   git branch --show-current
   ```

2. Check if on main/master:
   - If yes, list all active task files in `docs/tasks/` (excluding _completed)
   - Report: "No active task. Use `/project:new-task` or `/project:worktree` to start one."

3. If on a task branch, read `docs/tasks/{branch-name}.md`

4. If task file doesn't exist:
   ```
   ⚠ No checklist found for branch: {branch-name}
   
   Create one with: /project:new-task {branch-name}
   Or manually create: docs/tasks/{branch-name}.md
   ```

5. Parse and display status:
   ```
   ## Current Task: {branch-name}
   
   **Progress:** {completed}/{total} items ({percentage}%)
   **Status:** {status from file}
   **Created:** {date from file}
   
   ### Remaining Items
   - [ ] {unchecked item 1}
   - [ ] {unchecked item 2}
   
   ### Completed
   - [x] {checked item 1}
   - [x] {checked item 2}
   
   ---
   Next unchecked item: "{first unchecked item}"
   ```

6. Also show recent commits on this branch:
   ```bash
   git log --oneline -5
   ```
