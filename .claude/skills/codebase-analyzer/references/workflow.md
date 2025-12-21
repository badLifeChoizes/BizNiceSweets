# Codebase Analyzer Workflow Guide

Detailed usage instructions for the two-phase hybrid analysis approach.

## Two-Phase Workflow Overview

### Phase 1: Automated Static Analysis

Run the analyzer to collect raw data:

```bash
python scripts/analyze.py /path/to/project --generate-skill
```

This creates a `<project>-context/` folder containing:
- `SKILL.md` - Basic auto-generated context
- `references/synthesis_prompt.md` - Instructions for Phase 2
- `references/full_analysis.json` - Complete raw data
- `references/api_analysis.json` - API endpoint details
- `references/models_analysis.json` - Data model details
- `references/config_analysis.json` - Configuration details

### Phase 2: Claude-Assisted Synthesis

Ask Claude to synthesize the raw analysis into meaningful context:

```
Read the synthesis_prompt.md in <project>-context/references/ and the key files
listed there. Then update the SKILL.md with your understanding of:
- What this project does (business purpose)
- How to work on it (run, test, deploy)
- Key concepts and gotchas
- Validate any uncertain areas with me
```

## Command Reference

### Full Analysis with Skill Generation

```bash
python scripts/analyze.py /path/to/project --generate-skill
```

### Save Analysis to JSON

```bash
python scripts/analyze.py /path/to/project --output analysis.json
```

### Basic Analysis (Skip Extended)

```bash
# Skip API, models, and config analysis for faster results
python scripts/analyze.py /path/to/project --generate-skill --basic
```

### Get Synthesis Prompt Only

```bash
python scripts/analyze.py /path/to/project --synthesis-only
```

### Individual Analyzers

```bash
# Structure only
python scripts/analyze_structure.py /path/to/project --tree

# Dependencies only
python scripts/analyze_deps.py /path/to/project

# Patterns only
python scripts/analyze_patterns.py /path/to/project

# Dependency graph only
python scripts/build_graph.py /path/to/project

# API endpoints only
python scripts/analyze_api.py /path/to/project

# Data models only
python scripts/analyze_models.py /path/to/project

# Configuration only
python scripts/analyze_config.py /path/to/project
```

## Phase 2 Synthesis: What Claude Should Do

### 1. Read the Synthesis Prompt

The `references/synthesis_prompt.md` file contains:
- Summary of what was detected
- Specific questions to investigate
- Key files to read
- Output format guidance

### 2. Read Key Files

The analysis identifies important files to understand:
- **Entry points** - Where the application starts
- **Core modules** - Most imported internal code
- **Route files** - API endpoint definitions
- **Model files** - Data structure definitions
- **Config files** - Environment and settings

### 3. Answer Open Questions

The analysis flags questions like:
- `[HIGH]` What is the project's main purpose?
- `[MEDIUM]` What architectural pattern is used?
- `[LOW]` Which env vars are required vs optional?

### 4. Write Meaningful Context

Transform data into practical guidance:

**Bad (data dump):**
```markdown
## Files
- 245 total files
- 32 directories
- Languages: python (120), typescript (80)
```

**Good (meaningful context):**
```markdown
## What This Project Does

This is a FastAPI backend for a task management SaaS. It provides REST APIs
for user authentication, task CRUD operations, and team collaboration features.

## How to Run

1. Copy `.env.example` to `.env` and fill in database credentials
2. Run `docker-compose up -d` to start PostgreSQL
3. Run `uvicorn main:app --reload` for development

## Key Concepts

- **Tasks** are the core entity - they belong to Users and can be in Projects
- **Projects** group tasks and can have multiple team members
- Authentication uses JWT tokens stored in httpOnly cookies

## Gotchas

- The `task_service.py` has complex status transition logic - read it carefully
- All database queries go through the repository layer, don't bypass it
- The frontend expects snake_case JSON keys, not camelCase
```

### 5. Validate with User

Ask the user to confirm:
- "Is my understanding of the project's purpose correct?"
- "I noticed X pattern - is this intentional?"
- "The analysis flagged Y as uncertain - can you clarify?"

## Example Full Workflow

### Step 1: Run Phase 1

```bash
$ python scripts/analyze.py ~/projects/my-api --generate-skill

📁 Analyzing: my-api

  → Analyzing structure...
  → Analyzing dependencies...
  → Detecting patterns...
  → Building dependency graph...
  → Detecting API endpoints...
  → Extracting data models...
  → Analyzing configuration...

📊 Summary for my-api:
   Files: 156
   Directories: 24
   Languages: python(98), json(32), yaml(12)
   Frameworks: FastAPI
   API Endpoints: 18
   Data Models: 8
   Env Variables: 12
   Confidence: 18 detected, 4 inferred, 2 unknown
   ⚠️  2 areas need verification

✅ Generated skill at: my-api-context

📋 Next Steps (Phase 2):
   1. Read: my-api-context/references/synthesis_prompt.md
   2. Read key files listed in the prompt
   3. Update my-api-context/SKILL.md with synthesized insights
```

### Step 2: Ask Claude to Synthesize

```
I just ran the codebase analyzer on my project. Can you:

1. Read my-api-context/references/synthesis_prompt.md
2. Read the key files it mentions
3. Update my-api-context/SKILL.md with a proper understanding of the project
4. Ask me to clarify anything you're uncertain about
```

### Step 3: Claude Reads and Synthesizes

Claude will:
- Read the synthesis prompt
- Read entry points like `main.py`
- Read route files to understand the API
- Read model files to understand data structures
- Ask clarifying questions
- Generate an updated SKILL.md

### Step 4: Validate and Refine

Review Claude's synthesis and correct any misunderstandings. The skill can be iteratively improved.

## Tips

### For Best Results

- **Run from project root** - Analysis works best from the top-level directory
- **Include a README** - The analyzer extracts context from README files
- **Commit before analyzing** - Ensures analysis reflects clean state
- **Re-analyze after major changes** - Keep the context skill up to date

### For Large Projects

- Use `--basic` flag to skip extended analysis for faster results
- Run individual analyzers to focus on specific aspects
- Consider analyzing subprojects separately in monorepos

### For Uncertain Areas

- The analysis explicitly marks what needs verification
- Claude should ask the user rather than guess
- Update the SKILL.md after clarification

## Supported Frameworks

### API Frameworks

| Language | Frameworks |
|----------|------------|
| Python | Flask, FastAPI, Django, Django REST |
| JavaScript | Express, Fastify, NestJS, Next.js API |
| Go | Gin, Chi, Echo, Fiber, net/http |
| C# | ASP.NET Core (MVC & Minimal APIs) |
| Java | Spring (Boot, MVC) |
| Rust | Actix-web, Axum, Rocket |

### ORM/Database

| Language | ORMs |
|----------|------|
| Python | SQLAlchemy, Django ORM |
| JavaScript | Prisma, TypeORM, Sequelize |
| C# | Entity Framework Core |
| Go | GORM |
| Rust | Diesel |
| SQL | Raw schema files |

### Configuration

| Type | Files Detected |
|------|----------------|
| Environment | .env, .env.*, .env.example |
| Python | settings.py, config.py, pyproject.toml |
| JavaScript | config.json, config.js, next.config.* |
| .NET | appsettings.json, web.config |
| Java | application.properties, application.yml |
| Docker | docker-compose.yml |
