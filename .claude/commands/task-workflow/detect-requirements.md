# Detect Requirements (Internal Helper)

Automatically detect relevant requirements based on task context. Used by other task-workflow commands.

**This is an internal helper - not typically called directly by users.**

## Input

Analyzes these sources in order of priority:

1. **Branch name**: `feature-session-lifecycle` → sessions
2. **Task goal/description**: "Add CSV export to sessions" → sessions + export
3. **File paths mentioned**: `src/sessions/` → sessions
4. **Keywords in checklist items**: "device pairing" → devices

## Feature Keyword Mapping

```python
FEATURE_KEYWORDS = {
    'sessions': {
        'doc': 'docs/features/sessions.md',
        'prefix': 'SESS',
        'keywords': [
            'session', 'timer', 'pause', 'resume', 'start', 'stop',
            'configured', 'active', 'completed', 'timeline', 'export',
            'pdf', 'csv', 'json', 'report'
        ]
    },
    'devices': {
        'doc': 'docs/features/devices.md',
        'prefix': 'DEV',
        'keywords': [
            'device', 'bluetooth', 'pair', 'scan', 'connect', 'disconnect',
            'woundcell', 'sensor', 'virtual', 'transport', 'controller'
        ]
    },
    'participants': {
        'doc': 'docs/features/participants.md',
        'prefix': 'PART',
        'keywords': [
            'participant', 'instructor', 'student', 'patient', 'anonymous',
            'vitals', 'profile', 'role', 'assign'
        ]
    },
    'lesson-plans': {
        'doc': 'docs/features/lesson-plans.md',
        'prefix': 'LP',
        'keywords': [
            'lesson', 'plan', 'objective', 'procedure', 'lock', 'assignment',
            'template', 'scenario', 'curriculum'
        ]
    },
    'plugins': {
        'doc': 'docs/features/plugins.md',
        'prefix': 'PLUG',
        'keywords': [
            'plugin', 'extension', 'install', 'enable', 'disable', 'dependency',
            'marketplace', 'permission', 'hook', 'lifecycle'
        ]
    },
    'provider-network': {
        'doc': 'docs/features/provider-network.md',
        'prefix': 'PN',
        'keywords': [
            'provider', 'network', 'marketplace', 'share', 'upload', 'download',
            'online', 'offline', 'sync', 'cloud', 'bulletin'
        ]
    },
    'architecture': {
        'doc': 'docs/features/INDEX.md',
        'prefix': 'ARCH',
        'keywords': [
            'architecture', 'database', 'sqlite', 'zustand', 'event', 'ipc',
            'electron', 'dashboard', 'search', 'offline-first'
        ]
    },
    # Cross-cutting UI concerns (no requirements, but has INVARIANTS)
    'bento-grid': {
        'doc': 'docs/features/ui/bento-grid/README.md',
        'invariants': 'docs/features/ui/bento-grid/INVARIANTS.md',
        'prefix': None,  # No requirement prefix - cross-cutting concern
        'keywords': [
            'bento', 'grid', 'tile', 'layout', 'theme', 'dashboard', 'panel',
            'resize', 'drag', 'drop', 'position', 'widget', 'responsive',
            'dark-mode', 'light-mode', 'css-variable', 'tile-state'
        ]
    }
}
```

## Detection Process

### Step 1: Extract Keywords from Context

```text
Input: branch="feature-session-export", goal="Add CSV export functionality to completed sessions"

Extracted keywords: [session, export, csv, completed]
```

### Step 2: Score Features by Keyword Matches

```text
Feature Scores:
- sessions: 4 matches (session, export, csv, completed) ★ PRIMARY
- devices: 0 matches
- participants: 0 matches
- lesson-plans: 0 matches
- plugins: 0 matches (export could be plugin but sessions scores higher)
```

### Step 3: Search Requirements for Keyword Matches

Read `docs/features/requirements.md` and score each requirement:

```text
SESS-036: "System SHALL support PDF export format"
  → matches: export ★
SESS-037: "System SHALL support CSV export format"
  → matches: csv, export ★★
SESS-038: "System SHALL support JSON export format"
  → matches: export ★
SESS-039: "Plugins SHALL be able to extend export"
  → matches: export, plugin ★
```

### Step 4: Return Ranked Results

```json
{
  "primary_feature": {
    "name": "sessions",
    "doc": "docs/features/sessions.md",
    "prefix": "SESS",
    "confidence": "high"
  },
  "secondary_features": [],
  "suggested_requirements": [
    {"id": "SESS-037", "text": "CSV export format", "score": 2, "status": "⬜"},
    {"id": "SESS-036", "text": "PDF export format", "score": 1, "status": "⬜"},
    {"id": "SESS-038", "text": "JSON export format", "score": 1, "status": "⬜"}
  ],
  "ambiguous": false,
  "no_match": false
}
```

## Output Scenarios

### Scenario A: Clear Match (Confidence: High)

```text
🎯 Detected Feature: Sessions

Suggested Requirements (3 matches):
- [ ] SESS-037: System SHALL support CSV export format (Must) ⬜
- [ ] SESS-036: System SHALL support PDF export format (Must) ⬜
- [ ] SESS-038: System SHALL support JSON export format (Must) ⬜

Feature doc: @docs/features/sessions.md

Accept these requirements? (y/n/edit)
```

### Scenario B: Ambiguous Match (Multiple Features)

```text
⚠️ Multiple features detected:

1. Sessions (3 keyword matches)
   - SESS-036, SESS-037, SESS-038 (export formats)

2. Plugins (2 keyword matches)
   - PLUG-002: Export Tool plugins

Which feature is primary? (1/2/both)
```

### Scenario C: Partial Match (Low Confidence)

```text
⚠️ Low confidence match for: feature-notifications

Possible matches:
- Sessions: SESS-028 "Alert notification for disconnect" (weak)
- Architecture: No direct match

Options:
1. Run discovery interview (recommended)
   → Uses /interview discovery to explore requirements
   → See: .claude/skills/interview/SKILL.md

2. Use weak matches anyway
   → Accept partial matches as starting point

3. Create new requirements for "notifications"
   → Uses add-feature to create placeholder requirements

4. Skip requirements (manual later)
   → Task will not track requirement progress

Choice (1/2/3/4):
```

**When using discovery interview (Option 1):**

The interview skill provides structured exploration:

- Asks clarifying questions to understand the feature scope
- Presents options with pros/cons for each decision
- Captures requirements with proper IDs and rationale
- Documents why weak matches were accepted/rejected

### Scenario D: Cross-Cutting Concern Match (e.g., Bento Grid)

```text
⚠️ Cross-cutting UI concern detected: Bento Grid

This is not a feature with requirements, but it has INVARIANTS that must be followed.

INVARIANTS: @docs/features/ui/bento-grid/INVARIANTS.md (28 rules)

Key areas covered:
- Tile state management
- Layout persistence
- Theme system (CSS variables)
- Plugin tile isolation

⚠️ Any feature using Bento Grid UI must follow these invariants.

Primary feature for requirements: {detected primary feature}
```

This scenario occurs when keywords like `bento`, `grid`, `tile`, `layout`, `theme` are detected.
The task still needs a primary feature for requirements tracking, but the Bento Grid INVARIANTS
are surfaced as a cross-cutting concern.

### Scenario E: No Match

```text
❌ No matching feature found for: feature-analytics

This appears to be a new feature not covered by existing documentation.

Options:
1. Run discovery interview (recommended for new features)
   → Uses /interview discovery to gather requirements
   → Creates proper feature doc and requirements
   → See: .claude/skills/interview/SKILL.md

2. Create new feature: docs/features/analytics.md
   → Generates stub feature doc
   → Creates placeholder requirements (ANALYTICS-001, etc.)

3. Map to existing feature manually
   → Show list of all features

4. Proceed without requirements
   → Task will not update requirements-progress.md

Choice (1/2/3/4):
```

**When using discovery interview (Option 1):**

For new features, the discovery interview:

- Explores the problem space with targeted questions
- Defines core vs. optional requirements
- Assigns proper requirement IDs (PREFIX-001, etc.)
- Creates both feature doc and task file with requirements linked

## Integration with Other Commands

### new-task uses detect-requirements:

```text
/project:new-task feature-device-firmware

1. Parse branch name
2. Call detect-requirements with branch="feature-device-firmware"
3. Receive: primary_feature=devices, requirements=[DEV-026, DEV-027, DEV-028]
4. Auto-populate task template
5. Show user for confirmation before creating
```

### quick-task uses detect-requirements:

```text
/project:quick-task feature-session-notes "Add instructor notes to sessions"

1. Call detect-requirements with branch + description
2. Store suggested requirements in task file as comment
3. When user runs start-task, requirements are ready
```

### start-task uses detect-requirements:

```text
/project:start-task feature-old-task

1. Read existing task file
2. If no Related Requirements section, call detect-requirements
3. Suggest requirements based on task goal
4. Offer to add them before starting work
```

## Confidence Scoring

| Confidence | Criteria | Action |
|------------|----------|--------|
| **High** | 3+ keyword matches, single feature | Auto-accept with confirmation |
| **Medium** | 1-2 matches OR multiple features | Show options, ask user |
| **Low** | Weak/partial matches only | Warn, offer alternatives |
| **None** | No matches | Offer to create new feature |

## Manual Override

User can always override with explicit requirements:

```text
/project:new-task feature-thing --requirements SESS-001,SESS-002,DEV-005
```

This bypasses auto-detection entirely.

## Interview Skill Integration

When detection confidence is low or no match is found, the interview skill provides structured requirements discovery.

### When to Invoke Interview

| Confidence | Interview Option |
|------------|------------------|
| High | Not offered (auto-accept) |
| Medium | Offered as alternative |
| Low | Recommended (Option 1) |
| None | Strongly recommended |

### Interview Output Format

The discovery interview produces output compatible with detect-requirements:

```json
{
  "primary_feature": {
    "name": "{discovered feature name}",
    "doc": "docs/features/{feature}.md",
    "prefix": "{PREFIX}",
    "confidence": "high"
  },
  "suggested_requirements": [
    {"id": "{PREFIX}-001", "text": "{requirement}", "priority": "Must", "source": "Decision 1"},
    {"id": "{PREFIX}-002", "text": "{requirement}", "priority": "Should", "source": "Decision 2"}
  ],
  "decisions_recorded": "docs/tasks/{branch}.md#decisions"
}
```

### Handoff to Interview

When detect-requirements invokes interview:

```text
detect-requirements → Low confidence
                   ↓
User selects: "Run discovery interview"
                   ↓
/interview discovery {feature-name}
                   ↓
Interview gathers requirements
                   ↓
Output → task file + feature doc
```

See: `.claude/skills/interview/SKILL.md` for full interview documentation.