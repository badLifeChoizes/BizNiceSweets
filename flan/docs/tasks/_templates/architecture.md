# {Feature Name} Architecture

Data models, state machines, events, and APIs.

---

## Data Model

```typescript
{TypeName}
├── id: {type}
├── {field1}: {type}
├── {field2}: {type}
├── {field3}: {type}
└── {field4}: {type}
```

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `{field1}` | `{type}` | {Description} |
| `{field2}` | `{type}` | {Description} |
| `{field3}` | `{type}` | {Description} |

---

## State Machine

{If this feature has states}

```text
{State1} ──[{Trigger}]──► {State2} ──[{Trigger}]──► {State3}
                            │
                      [{Trigger}]
                            │
                            ▼
                        {State4}
```

### State Definitions

| State | Description | Allowed Actions |
|-------|-------------|-----------------|
| **{State1}** | {Description} | {Actions} |
| **{State2}** | {Description} | {Actions} |
| **{State3}** | {Description} | {Actions} |

### Transitions

| From | To | Trigger | Side Effects |
|------|-----|---------|--------------|
| {State1} | {State2} | {Trigger} | {Effects} |
| {State2} | {State3} | {Trigger} | {Effects} |

---

## Events

| Event | Payload | When Emitted |
|-------|---------|--------------|
| `{feature}:{event1}` | `{ field1, field2 }` | {When} |
| `{feature}:{event2}` | `{ field1, field2 }` | {When} |
| `{feature}:{event3}` | `{ field1, field2 }` | {When} |

---

## API / IPC Channels

### {Channel/Endpoint 1}

**Channel:** `{channel-name}`

**Direction:** {Renderer → Main | Main → Renderer | Both}

**Request:**

```typescript
{
  {field1}: {type},
  {field2}: {type}
}
```

**Response:**

```typescript
{
  {field1}: {type},
  {field2}: {type}
}
```

---

## Data Persistence

| Data | Storage | Location |
|------|---------|----------|
| {Data type 1} | {SQLite/Zustand/JSON} | {Table/Store/File} |
| {Data type 2} | {SQLite/Zustand/JSON} | {Table/Store/File} |

---

## Key Implementation Files

| Component | Location |
|-----------|----------|
| Main logic | `src/{path}/file.ts` |
| Types | `src/shared/types/{feature}.types.ts` |
| Store | `src/renderer/stores/{feature}Store.ts` |
| IPC handlers | `src/main/ipc/{feature}-handlers.ts` |
| Tests | `tests/unit/{feature}/` |
