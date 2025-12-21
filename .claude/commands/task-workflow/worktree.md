Create an isolated git worktree for parallel development.

Use this when you need to work on multiple tasks simultaneously without context bleeding.

## Steps

1. Parse the task name from: $ARGUMENTS
   - If empty, ask user for a task name
   - Ensure it follows naming convention (feature-*, bugfix-*, hotfix-*)

2. Get the current project directory name:
   ```bash
   basename $(pwd)
   ```

3. Create the worktree with a new branch:
   ```bash
   git worktree add ../{project-name}-$ARGUMENTS -b $ARGUMENTS
   ```

4. Create the task checklist file in the NEW worktree at `docs/tasks/$ARGUMENTS.md`:

   ```markdown
   # {Task Name (humanized from branch)}

   **Branch:** `$ARGUMENTS`
   **Created:** {today's date}
   **Status:** In Progress

   ## Goal

   {Ask user to describe the goal, or infer from branch name}

   ## Checklist

   - [ ] {First logical step}
   - [ ] {Second step}
   - [ ] {Continue as needed}

   ## Notes

   {Any relevant context, decisions, or blockers}
   ```

5. Commit the task file in the worktree:
   ```bash
   cd ../{project-name}-$ARGUMENTS
   git add docs/tasks/$ARGUMENTS.md
   git commit -m "chore: start $ARGUMENTS"
   ```

6. Tell the user:
   ```
   ✓ Created worktree: ../{project-name}-$ARGUMENTS
   ✓ Created branch: $ARGUMENTS
   ✓ Created checklist: docs/tasks/$ARGUMENTS.md

   To start working in the isolated environment:
   
       cd ../{project-name}-$ARGUMENTS && claude

   This keeps your current session clean for other work.
   ```

## Cleanup Reminder

When done with a worktree, remove it:
```bash
git worktree remove ../{project-name}-$ARGUMENTS
```
