# Codebase-Analyzer Integration Guide

How to use codebase-analyzer effectively to bootstrap project context skills, and how to clean up its output for production quality.

## The Two-Phase Problem

Codebase-analyzer produces raw data that needs human/AI synthesis. Common issues with Phase 1 output:

| Issue | Example | Solution |
|-------|---------|----------|
| Documentation as code | `docs.api.html.jquery` as "core module" | Filter doc directories |
| Trivial uncertainty | "What is `components/`?" | Trust obvious names |
| Generic guidance | "Follow existing patterns" | Add specific patterns |
| Missing business context | No explanation of purpose | Add from README/user |
| Garbage entry points | `search/files_4.js` | Identify real entry points |

## Pre-Analysis Checklist

Before running codebase-analyzer, prepare the project:

```markdown
- [ ] Clean build artifacts (`node_modules/`, `__pycache__/`, `build/`)
- [ ] Remove generated documentation (`docs/api/`, `javadoc/`)
- [ ] Ensure README exists with project description
- [ ] Commit or stash uncommitted changes
```

## Filtering Strategies

### Directories to Exclude

Configure analyzer or manually filter these from output:

```
# Documentation
docs/
documentation/
**/html/
**/javadoc/
**/doxygen/

# Build artifacts
build/
dist/
out/
target/
bin/
obj/

# Dependencies
node_modules/
vendor/
venv/
.venv/
__pycache__/

# Generated
*.generated.*
*.auto.*
**/generated/

# IDE/Editor
.idea/
.vscode/
*.swp
*.swo

# Archives
archive/
deprecated/
old/
backup/
```

### Language-Specific Filters

#### C/C++ (Embedded)

```
# ESP-IDF specific
managed_components/
build/
sdkconfig
sdkconfig.old

# Treat as architecture, not noise
components/           # ESP-IDF component structure
main/                 # Application entry point
```

#### JavaScript/TypeScript

```
# Always exclude
node_modules/
.next/
.nuxt/
coverage/

# Often generated
*.d.ts                # Unless hand-written
*.min.js
*.bundle.js
```

#### Python

```
# Virtual environments
venv/
.venv/
env/
.env/

# Build
*.egg-info/
dist/
build/
__pycache__/

# Testing artifacts
.pytest_cache/
.coverage
htmlcov/
```

## Post-Analysis Cleanup

### Step 1: Validate Entry Points

Codebase-analyzer often misidentifies entry points. Verify:

```markdown
**Detected Entry Points:**
- ❌ `docs/api/search/files_4.js` → DELETE (documentation artifact)
- ❌ `test/fixtures/sample.py` → DELETE (test fixture)
- ✓ `src/main.py` → KEEP (actual entry point)
- ✓ `cmd/server/main.go` → KEEP (CLI entry point)
```

### Step 2: Reduce Uncertainty

Most "uncertain" items don't need user validation:

```markdown
**Trivial (Don't Ask):**
- "What is `components/`?" → It's components
- "What is `utils/`?" → It's utilities
- "What is `tests/`?" → It's tests

**Genuine (Do Ask):**
- "What is `fixtures/`?" → Could be test data or demo data
- "Why are there two `auth/` directories?" → Needs clarification
- "Is `legacy/` still used?" → User must confirm
```

### Step 3: Add Missing Context

Codebase-analyzer cannot infer:

| Missing | How to Add |
|---------|-----------|
| Business purpose | Extract from README, ask user |
| Why decisions were made | Ask user, check git history |
| Performance constraints | Ask user, check config limits |
| Deployment requirements | Check CI/CD files, ask user |
| Security considerations | Review auth code, ask user |

### Step 4: Consolidate Conventions

Transform verbose pattern detection into concise conventions:

**Before (analyzer output):**
```json
{
  "python": {
    "type_hints": true,
    "docstrings": "common",
    "dataclasses": true,
    "async_patterns": true
  }
}
```

**After (context skill):**
```markdown
## Python Conventions
- Type hints required on public functions
- Docstrings: Google style, required on public API
- Data structures: Use `@dataclass` for DTOs
- Async: Use `async/await` for I/O, avoid `asyncio.run()` in library code
```

## Language-Specific Context

### Embedded/IoT (ESP-IDF, FreeRTOS)

Add these sections that analyzer can't infer:

```markdown
## Build System
- Uses ESP-IDF v5.x with CMake
- Build: `idf.py build`
- Flash: `idf.py -p COMx flash`
- Monitor: `idf.py -p COMx monitor`

## FreeRTOS Patterns
- Main task in `app_main()` at priority 5
- BLE task at priority 10 (higher = more important)
- Use `xSemaphore` for shared resources, not raw mutexes
- Stack sizes: 4KB minimum for tasks with logging

## Memory Constraints
- Total heap: 320KB
- Reserved for BLE stack: 64KB
- Application budget: ~200KB
- Use `heap_caps_get_free_size()` to monitor

## Hardware Abstraction
- All GPIO access through `components/hal/`
- Pin definitions in `include/board_config.h`
- Don't use raw `gpio_set_level()` outside HAL
```

### Web Backend (FastAPI, Express, etc.)

```markdown
## API Structure
- Routes in `routes/` or `api/`
- Business logic in `services/`
- Database in `repositories/` or `db/`
- DTOs/schemas separate from ORM models

## Request Flow
1. Route handler validates input
2. Calls service layer with validated data
3. Service orchestrates business logic
4. Repository handles database operations
5. Response serialized through schema

## Error Handling
- Use custom exception classes from `exceptions/`
- Never catch generic `Exception` in handlers
- All errors return JSON with `{ error: { code, message } }`
```

### Frontend (React, Vue, etc.)

```markdown
## Component Structure
- Pages in `pages/` or `views/`
- Reusable components in `components/`
- Shared hooks in `hooks/`
- State management in `store/` or `context/`

## State Management
- Global state: [Redux/Zustand/Context]
- Server state: [React Query/SWR/Apollo]
- Form state: [React Hook Form/Formik]

## Styling
- CSS Modules / Tailwind / styled-components
- Theme variables in `styles/theme.ts`
- No inline styles except for dynamic values
```

## Quality Validation Checklist

Before finalizing a project context skill:

```markdown
### Content Quality
- [ ] Business purpose is explained (not just technical description)
- [ ] Entry points are correct (not documentation/test artifacts)
- [ ] Conventions are specific (not "follow best practices")
- [ ] Guardrails are actionable (explicit DO/DON'T lists)
- [ ] Gotchas include real examples (not theoretical concerns)

### Structure Quality
- [ ] SKILL.md is under 500 lines
- [ ] References are organized by topic
- [ ] No deeply nested reference files
- [ ] Large references have table of contents

### Accuracy
- [ ] Build/run instructions actually work
- [ ] File paths match current project structure
- [ ] Dependencies listed are current
- [ ] No stale information from old versions
```
