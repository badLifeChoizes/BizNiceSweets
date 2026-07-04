# Phase 3: App Shell & Settings - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-25
**Phase:** 3-App Shell & Settings
**Areas discussed:** Shell layout & chrome, Nav visibility logic, Module enable/disable model, System settings model & scope

---

## Shell Layout & Chrome

### Q1 — Overall layout
| Option | Description | Selected |
|--------|-------------|----------|
| Left sidebar nav | Vertical sidebar, content right, collapses to sheet drawer | |
| Top horizontal nav | Module links in a top bar | |
| Sidebar + top bar | Sidebar for modules + thin top bar for global controls | ✓ |

### Q2 — Persistent chrome contents (multi-select)
| Option | Description | Selected |
|--------|-------------|----------|
| Company name / branding | Configured company name in header | ✓ |
| User menu + logout | Identity + logout (closes Phase-2 deferred follow-up) | ✓ |
| Active-module indicator | Highlight current section | ✓ |
| Admin/settings entry | Admin-only link/section | ✓ |

### Q3 — Admin screen placement
| Option | Description | Selected |
|--------|-------------|----------|
| Grouped 'Settings/Admin' area | Dedicated section grouping Users/Settings/Modules | |
| Settings icon/menu in chrome | Gear/user-menu dropdown opening admin pages | ✓ |
| You decide | Builder chooses | |

**User's choice:** Sidebar + top bar; all four chrome elements; admin via settings/user menu in chrome.
**Notes:** Consistent pair — admin entry lives in the chrome menu, keeping the main sidebar focused on business modules.

---

## Nav Visibility Logic

### Q1 — How is the module list determined?
| Option | Description | Selected |
|--------|-------------|----------|
| Enabled AND permitted | Enabled (CORE-07) AND user holds module:action permission | ✓ |
| Enabled only (CORE-08 literal) | Show all enabled to everyone; rely on 403 | |
| You decide | Builder picks | |

### Q2 — Empty state
| Option | Description | Selected |
|--------|-------------|----------|
| Friendly empty state | Shell renders, "No modules available — contact admin" | ✓ |
| Minimal landing | Simple home placeholder, empty nav | |
| You decide | Builder chooses | |

### Q3 — Post-login landing
| Option | Description | Selected |
|--------|-------------|----------|
| Neutral home/dashboard | Land on '/' home, pick module from nav | ✓ |
| First available module | Redirect to first enabled+permitted module | |
| You decide | Builder chooses | |

**User's choice:** Enabled AND permitted; friendly empty state; neutral home/dashboard.
**Notes:** Keeps Phase 3 module-agnostic since real module screens arrive Phases 4–6.

---

## Module Enable/Disable Model

### Q1 — Runtime module state storage
| Option | Description | Selected |
|--------|-------------|----------|
| DB module table, seeded from registry | modules table (key/display_name/enabled/always_on) seeded from code registry; profiles decide present, table decides on | ✓ |
| Settings/config flag per module | Store enabled-modules in system-settings store | |
| You decide | Builder picks | |

### Q2 — SYERP always-on enforcement
| Option | Description | Selected |
|--------|-------------|----------|
| Non-disablable flag | always_on=true; UI control disabled w/ tooltip; backend rejects disable | ✓ |
| Hide SYERP from toggle list | Only optional suites appear | |
| You decide | Builder enforces D-06 | |

### Q3 — "Disappears immediately" requirement
| Option | Description | Selected |
|--------|-------------|----------|
| On next nav fetch / refresh | TanStack Query refetch on toggle/nav/focus; no websockets | ✓ |
| Live push to all clients | WebSocket/SSE broadcast | |
| You decide | Builder picks | |

**User's choice:** DB module table seeded from registry; non-disablable flag; refetch-based immediacy.
**Notes:** User explicitly requested that **live push be added to the backlog for a future milestone** — refetch is the Phase-3 approach.

---

## System Settings Model & Scope

### Q1 — Storage model
| Option | Description | Selected |
|--------|-------------|----------|
| Key-value settings table | Flexible key/value/type; add settings without migrations | ✓ |
| Typed columns (single-row config) | Explicit typed columns; migration per new setting | |
| You decide | Builder picks | |

### Q2 — v1 settings (multi-select)
| Option | Description | Selected |
|--------|-------------|----------|
| Company identity | Company name (+ optional logo/address) | ✓ |
| Locale defaults | Default currency, date format, timezone, units | ✓ |
| Minimal: company name only | Ship just company name | |
| You decide | Builder scopes | |

### Q3 — Scope
| Option | Description | Selected |
|--------|-------------|----------|
| Global, admin-only | System-wide, admin-edited, no per-user prefs | |
| Global + groundwork for per-user | Global now, modeled for per-user later | ✓ |
| You decide | Builder chooses | |

**User's choice:** Key-value table; company identity + locale defaults; global with per-user groundwork.
**Notes:** Broader than the strict minimum — deliberately lays defaults groundwork that Phase 6 costing / SYERP will consume.

---

## Claude's Discretion

- Exact column sets for the `modules` and `settings` tables (and whether `settings` carries a scope/owner column now).
- The admin permission string gating Settings + Module toggles within the Phase-2 `module:action` RBAC model.
- Shell component structure, active-module computation, and which shadcn primitives compose the chrome.
- TanStack Query refetch triggers/cadence for "immediate" toggle propagation.
- Whether enabled-modules + visible-nav is one API response or composed client-side.
- `modules` table seed details (display names, ordering, icons).

## Deferred Ideas

- **Live push of module toggles to all clients** (WebSocket/SSE) — add to backlog for a future milestone (user request).
- **Per-user preferences** — only data-model groundwork in scope this phase.
- **Rich company branding** (logo upload, address, themes) beyond company name.
- **Module nav metadata** (icons/ordering/grouping) — basic version is discretionary; richer catalog UI later.
