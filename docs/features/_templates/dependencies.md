# {Feature Name} Dependencies

What to read before working on this feature.

---

## This Feature Depends On

| Feature | Why | Must Read |
|---------|-----|-----------|
| {Feature A} | {Reason} | `_restructure/{feature-a}/INVARIANTS.md` |
| {Feature B} | {Reason} | `_restructure/{feature-b}/INVARIANTS.md` |

---

## Other Features Depend On This

| Feature | Integration Point | What They Expect |
|---------|-------------------|------------------|
| {Feature X} | {API/Event/Data} | {Expectation} |
| {Feature Y} | {API/Event/Data} | {Expectation} |

---

## Cross-Cutting Concerns

| Concern | Applies When | Must Read |
|---------|--------------|-----------|
| Bento Grid | Building UI components | `_restructure/ui/bento-grid/INVARIANTS.md` |
| Event Bus | Emitting/subscribing to events | {location} |
| IPC | Communicating between processes | {location} |

---

## Reading Checklist

Before implementing changes to this feature:

- [ ] Read this feature's `INVARIANTS.md`
- [ ] Read `{dependency1}/INVARIANTS.md`
- [ ] Read `{dependency2}/INVARIANTS.md`
- [ ] Check cross-cutting concerns that apply
- [ ] Review root `DEPENDENCIES.md` for full context

---

## Integration Points

### With {Feature A}

**How they connect:** {Description}

**Data exchanged:** {What data flows between them}

**Events:** {What events are sent/received}

### With {Feature B}

**How they connect:** {Description}

**Data exchanged:** {What data flows between them}

**Events:** {What events are sent/received}
