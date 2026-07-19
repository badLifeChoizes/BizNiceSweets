# Verification: Phase 11a — CRUMB CRM & pipeline
Date: 2026-07-16 | Commits: 039c409..efcf2e6 (branch feature-crumb-crm-pipeline)
Verdict: PASS (all fix-loop gaps resolved — final re-verification below)

All 7 success criteria verified empirically at exists → wired → works, each pinned by a
durable automated test. After the fix loop: both crumb verify scripts pass (**22/22** service,
**54/54** HTTP), all 13 regression scripts exit 0, the frontend build is clean and the 4
colocated Vitest files pass.

The initial verification (verdict PASS, minor doc gaps) plus the reviewer's REVIEW.md
surfaced one major correctness defect the verify scripts did not cover; it was fixed with a
regression test in the fix loop — see **## Resolution (fix loop)** at the foot of this file.

## Criteria

### SC1 Module wiring — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| crumb self-registers | yes | yes | yes | `main.py:82 importlib.import_module("app.modules.crumb")`; registry check returns `True` |
| crumb:read/write seeded | yes | yes | yes | `auth/seed.py:40-41` (_PERMISSIONS) + `:53-54` (_USER_ROLE_PERMS); HTTP RBAC proves live |
| models aggregated | yes | yes | yes | `core/models.py:30` uncommented; `Base.metadata` lists the 5 `crumb_*` tables |
| migration 0013 off 0012 | yes | yes | yes | `0013_crumb_crm_pipeline.py` revision="0013" down_revision="0012"; `alembic current` → `0013 (head)` |
| modules_seed row, order 50, disabled, not duplicated | yes | yes | yes | `modules_seed.py:28 ("crumb","CRUMB — CRM",False,50)`; grep count = 1 |

### SC2 Leads (AC1) — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| create/view/edit/archive | yes | yes | yes | `service/leads.py`; router `/crumb/leads` CRUD+archive; Leads.tsx UI + Vitest |
| qualified lead links-or-creates Partner.is_customer | yes | yes | yes | verify_crumb (A): both link-existing AND create-new stamp partner_id, status "qualified", new_partner.is_customer True |
| converts to opportunity, server-enforced + audited | yes | yes | yes | verify_crumb (B): both sides stamped, no-customer → 422; verify_crumb_api (A): lead.converted audit row attributable |

### SC3 Opportunity pipeline (AC2) — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| customer/value/close/stage fields | yes | yes | yes | models `crumb_opportunity`; migration cols; OpportunityCreate schema |
| server-enforced stage FSM, invalid → 4xx audited | yes | yes | yes | verify_crumb (C): qualify→proposal→won ok; off-terminal + disallowed-skip → 422; verify_crumb_api (B): stage_changed audit |
| per-stage grouped list | yes | yes | yes | `list_pipeline`; Pipeline.tsx; Pipeline.test.tsx asserts opp lands under its stage column |
| Won opportunity spawns a quote | yes | yes | yes | verify_crumb (C): spawn on non-won → 422, on won → Draft quote linked to opp+customer (D-V3-15) |

### SC4 Quotes (AC3 minus SO) — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| header + PLUM/free-text lines, qty, unit price | yes | yes | yes | models `crumb_quote`/`crumb_quote_line`; QuoteLineEditor.tsx |
| price defaults cost×1.30 markup, editable; null-cost→0 | yes | yes | yes | verify_crumb (E): 100→130 markup 30, override 42.5 persists, null-snapshot→0, no-release→0; QuoteDetail.test shows default+total |
| line + total value | yes | yes | yes | verify_crumb (G): Σ line_total == total_value 387.5 Decimal-exact |
| FSM Draft→Sent→Accepted/Rejected/Expired | yes | yes | yes | verify_crumb (D): valid walk ok, sent→draft → 422 |
| auto-number QUOTE-#### numeric-safe | yes | yes | yes | verify_crumb (F): boundary 0009→0010, survives non-QUOTE-[0-9]+ junk row, true numeric MAX+1 |

### SC5 Communication log (AC5) — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| append-only interactions (type/UTC/actor/body) | yes | yes | yes | verify_crumb (H): actor_id + UTC stamp; router has only POST create + GET timeline — no PATCH/DELETE path (append-only by construction) |
| references customer + optional lead/opp/quote | yes | yes | yes | InteractionCreate schema; migration soft-link FKs |
| per-customer timeline read | yes | yes | yes | verify_crumb (H): newest occurred_at first; Communications.test asserts timeline render |

### SC6 Audit + RBAC (AC7, CORE-05) — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| every mutation writes attributable audit at router | yes | yes | yes | verify_crumb_api: lead.created/converted, opportunity.created/stage_changed, quote.created/status_changed, interaction.logged — all rows attributable to writer, correct target_type |
| endpoints gated, refused server-side (HTTP) | yes | yes | yes | verify_crumb_api (E/F): mutations 403 reader / 401 anon; reads 200 reader / 403 noperm / 401 anon across all four entities |

### SC7 Frontend + regression — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| CRUMB nav gated (enabled ∩ crumb:read) | yes | yes | yes | CrumbNav.tsx via AppShell gating pattern (unchanged); routes in App.tsx |
| leads/pipeline/quotes/comm-log pages | yes | yes | yes | Leads, Pipeline, Quotes, QuoteDetail, Communications + components (line editor, dialogs) |
| Vitest green | yes | yes | yes | `npm run test -- routes/crumb`: 4 files, 4 tests pass |
| build clean | yes | yes | yes | `npm run build` (tsc -b && vite build) exits 0 |
| 13/13 verify_*.py exit 0 | — | — | yes | all 13 regression scripts PASS |

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC1 wiring | registry import check + `alembic current` + verify_crumb_api (perms gate live) |
| SC2 leads | verify_crumb.py (A)(B); verify_crumb_api.py (A); Leads.test.tsx |
| SC3 pipeline | verify_crumb.py (C); verify_crumb_api.py (B); Pipeline.test.tsx |
| SC4 quotes | verify_crumb.py (D)(E)(F)(G); verify_crumb_api.py (C); QuoteDetail.test.tsx |
| SC5 comm log | verify_crumb.py (H); verify_crumb_api.py (D); Communications.test.tsx; append-only = structural (no mutate endpoint) |
| SC6 audit+RBAC | verify_crumb_api.py (A–F) — the HTTP-level proof |
| SC7 FE+regression | 4 Vitest files + `npm run build` + 13 verify_*.py |

## Test suite
- `verify_crumb.py`: 20/20 PASS (service-level, live Postgres)
- `verify_crumb_api.py`: 50/50 PASS (HTTP RBAC 200/401/403 + attributable AuditLog per mutation)
- 13 regression verify_*.py: all exit 0
- `npm run test -- routes/crumb`: 4 files / 4 tests pass
- `npm run build`: exit 0
- Lint: not run — both project lint gates are known-nonfunctional (CLAUDE.md / BACKLOG p1), not a phase regression

## Deferral boundary (11a does not claim 11b work)
Confirmed honest. No `sales_order`/`reservation`/`reserved` code in `backend/app/modules/crumb/`
(sole grep hit is a "free-text line" comment). Quotes reach `accepted` with no SO-conversion path.
PLAN "Out of scope" and requirements-progress.md both explicitly mark AC4 (sales orders +
soft-reservation) and the accepted-quote→SO tail as deferred to 11b (D-V3-10). No silent claim.

## Gaps
1. **Minor — CLAUDE.md:95** — Suite Status table still shows `CRUMB (CRM) | — | Planned`; the
   module now exists (backend + frontend, live-verified). Actively misleading. Fix: update the
   row to "Building" with live locations `backend/app/modules/crumb/`, `frontend/src/routes/crumb/`.
2. **Minor — .zj/codebase/MAP.md** — does not list the registered `crumb` backend module; lines
   52/130 still describe `crumb/` only as a repo-root placeholder dir. Fix: add crumb to the
   registered-modules description (mousse is also absent there — same sweep).
3. **Minor — docs/tasks/feature-crumb-crm-pipeline.md** — checklist is complete (19/19 checked)
   but not yet archived to `docs/tasks/_completed/`. Acceptable while phase verification is
   pending; archive on phase close per CLAUDE.md convention.

Non-gap notes: `StarletteDeprecationWarning` for `HTTP_422_UNPROCESSABLE_ENTITY` fires across
crumb (and all sibling modules) — cosmetic, already logged in PLAN "Noticed" for a future sweep.

## Resolution (fix loop) — 2026-07-16, commits a697c69 + efcf2e6

The manager triage merged this report with REVIEW.md. All gaps fixed and re-verified:

| # | Sev | Finding | Fix | Pinned by |
|---|-----|---------|-----|-----------|
| R1 | major | Part-less quote line with a price but no description accepted (unlabeled customer-facing line, D-V3-14) | `quotes.py:_resolve_line_amounts` — identity guard runs BEFORE the explicit-price early return | verify_crumb E2 (reject) + E3 (legit free-text accepted) |
| R2 | minor | `convert_to_opportunity` skipped `_resolve_customer` (is_customer bypass, AC6) | `leads.py` re-resolves the customer before creating the opportunity | verify_crumb (A/B) exercise the path; guard matches create_opportunity |
| R3 | minor | Bogus `opportunity_id` on quote create → HTTP 500 (retry re-raised the FK IntegrityError) | `quotes.py:create_quote` validates opportunity_id up front (404) | verify_crumb_api (C): nonexistent id → 404 |
| Q1 | question | Spawned quote got no `quote.created` audit row (asymmetry) | owner chose YES — `router.py:spawn_quote_endpoint` writes both `opportunity.quote_spawned` and `quote.created` | verify_crumb_api (C2): both audit rows asserted |
| D1 | minor(doc) | CLAUDE.md Suite Status showed CRUMB "Planned" | updated to Building + Phase 11a scope | — |
| D2 | minor(doc) | MAP.md omitted the registered crumb module | registry line, crumb service-package note, migration 0013, frontend route folder all added | — |

Final re-verification after fixes (full re-run, not partial): verify_crumb **22/22**,
verify_crumb_api **54/54**, 13/13 regression exit 0, crumb Vitest 4/4, `npm run build` exit 0.
Verdict: **PASS**.
