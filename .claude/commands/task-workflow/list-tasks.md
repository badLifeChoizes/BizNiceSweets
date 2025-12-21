List all tasks (active and completed) with their status.

## Steps

1. List active tasks:
   ```bash
   ls docs/tasks/*.md 2>/dev/null | grep -v '_template.md' | grep -v 'README.md'
   ```

2. List completed tasks:
   ```bash
   ls docs/tasks/_completed/*.md 2>/dev/null
   ```

3. List active worktrees:
   ```bash
   git worktree list
   ```

4. Format output:
   ```
   ## Active Tasks
   
   | Branch | Progress | Created |
   |--------|----------|---------|
   | feature-auth | 3/7 (43%) | 2025-12-08 |
   | bugfix-login | 1/3 (33%) | 2025-12-07 |
   
   ## Active Worktrees
   
   | Path | Branch |
   |------|--------|
   | ../project-feature-auth | feature-auth |
   
   ## Recently Completed (last 5)
   
   | Branch | Completed |
   |--------|-----------|
   | feature-api-v2 | 2025-12-05 |
   | bugfix-memory-leak | 2025-12-03 |
   
   ---
   Use `/project:status` to see details for current branch.
   Use `/project:new-task {name}` to start a new task.
   ```
