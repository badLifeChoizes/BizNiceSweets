Generate or update CHANGELOG.md from conventional commits.

## Steps

1. Find the last tag (or first commit if no tags):
   ```bash
   LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || git rev-list --max-parents=0 HEAD)
   ```

2. Get all commits since last tag:
   ```bash
   git log --oneline --no-merges $LAST_TAG..HEAD
   ```

3. Parse commits into categories based on conventional commit prefixes:
   - `feat:` → Features
   - `fix:` → Bug Fixes
   - `docs:` → Documentation
   - `refactor:` → Refactoring
   - `test:` → Tests
   - `chore:` → Chores (usually omit from changelog)

4. Generate changelog entry:
   ```markdown
   ## [{version or "Unreleased"}] - {today's date}
   
   ### Features
   - {feat commit message} ({short hash})
   
   ### Bug Fixes
   - {fix commit message} ({short hash})
   
   ### Documentation
   - {docs commit message} ({short hash})
   ```

5. If CHANGELOG.md exists, prepend new entry after the header
   If not, create with header:
   ```markdown
   # Changelog

   All notable changes to this project will be documented in this file.

   The format is based on [Keep a Changelog](https://keepachangelog.com/),
   and this project adheres to [Conventional Commits](https://www.conventionalcommits.org/).

   {new entry}
   ```

6. Report:
   ```
   ✓ Updated CHANGELOG.md
   
   Added {count} entries:
   - {x} features
   - {y} bug fixes
   - {z} other
   
   Review the changes and commit when ready:
   git add CHANGELOG.md && git commit -m "docs: update changelog"
   ```

## Optional: Version Bump

If $ARGUMENTS contains a version (e.g., "1.2.0"):
- Use that version in the changelog header
- Suggest tagging: `git tag -a v{version} -m "Release {version}"`
