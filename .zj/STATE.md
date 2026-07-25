# STATE — BizNiceSweets
Updated: 2026-07-24 (**v4.0 Phase 3 BUILD COMPLETE — `/zj:build 3`.** Branch `chore-ci-pipeline` cut
off the plan-carrying tip `8a27a46` (code-identical to `4960d32` + the plan doc; trivial T0 deviation,
matches 2a/2b). **All 9 tasks (0–8) done, atomic commits; tree clean** (only the owner's
`.vscode/settings.json` unstaged). **`.github/workflows/ci.yml` live** — 4 independent jobs (no `needs:`):
`frontend` (npm ci→lint→tsc -b→vitest→build, Node 22), `backend-lint` (`ruff check .`, Py 3.13),
`backend-tests` (`pytest -q` vs a live `postgres:17` service — **232 passed / 0 skipped**; conftest
self-provisions `biznice_test`), `verify-scripts` (migrate+seed `biznice`, then the **14 non-API
`verify_*` — 14/14 exit 0**; glob excludes `*_api.py`). **All 6 SCs proven on REAL Actions runs:**
all-green **run 30140504003** (SC1/2/5); broken test → **30140642516** red (only `backend-tests`) →
revert **30140733237** green (SC3); lint violation (ruff F401 + eslint no-unused-vars) → **30140870255**
red (`backend-lint`+`frontend`) → revert **30140959653** green (SC4); **PR #4 → `master`** required-status
gated — four checks green, PR **BLOCKED→CLEAN**, branch protection `contexts=[frontend, backend-lint,
backend-tests, verify-scripts]` (SC6); final wrap-up **run 30141201881** all-green. **Two build deviations:**
(1) **MATERIAL → owner, D-P3-4** — the plan's "pytest self-provisions from a bare postgres" was wrong on a
*fresh* server: conftest's reachability probe hit the not-yet-created `biznice_test` and aborted before
provisioning (2a/2b "232 passed" only worked because the DB persisted locally); owner chose to fix the probe
to target the maintenance `postgres` DB (test-infra only, no `backend/app/` change) — verified fresh
`postgres:17` self-provisions → 232/0. (2) **build correction** — the plan's verify-scripts recipe omitted
`PYTHONPATH` (scripts do `from app…`) and the **seed step** (scripts need the app-lifespan CoA seeds — "GL
account 5100 not seeded" otherwise); added both. **Noticed:** Node-20 action-deprecation warning
(cosmetic); duplicate check runs per PR (both `push`+`pull_request` fire for a same-repo branch) — Phase 4+
scoping nicety. Checklist `docs/tasks/chore-ci-pipeline.md` (all 9 ticked; archive at finish/ship). SRD NFR-4
→ **done (pending `/zj:verify 3`)**, requirements-progress NFR-4 row + footer added, D-P3-4 recorded. **PR #4
left OPEN — merge is out of scope** (Phase 3 delivers the demonstrated blocking pipeline, not the merge).
**Next action:** `/zj:verify 3`.)

Prior: 2026-07-24 (**v4.0 Phase 3 PLANNED — `/zj:plan 3`.** Phase 3 = **CI pipeline (GitHub
Actions, NFR-4, D-M4-2)** — every push/PR runs a blocking pipeline: ruff + eslint + `tsc -b` +
vitest + `npm run build` + `pytest`-against-live-`postgres:17` (0 silent skips, 232 passed) + a
**service-layer `verify_*` regression job** (the D-P2a-2 concurrency-proof CI home). **9 tasks**
(`.zj/phases/03-ci-pipeline/PLAN.md`), sequential (one shared `ci.yml` + live-demo deps): T0 branch
cut → T1 frontend+backend-lint jobs → T2 backend-tests job → T3 verify-scripts job → T4 push+prove
all-green → T5 broken-test-red → T6 broken-lint-red → T7 real PR→master + required-status branch
protection → T8 flip NFR-4 → done. **3 owner decisions (AskUserQuestion, all Rec.) → D-P3-1..3:**
(1) CI runs the **14 non-API `verify_*` only** (the 9 `*_api.py` need a booted uvicorn; their
RBAC/audit was ported to pytest in 2b — redundant); (2) backend runner = **setup-python@3.13 + pip
+ `postgres:17` service** (not a baked image — matches conftest's documented localhost invocation,
self-provisions `biznice_test`); (3) **full live demo + branch protection** (gh authed as
`badLifeChoizes`; owner-authorized outward push of the unmerged stack's branch). **DB-naming risk
resolved:** pytest self-creates/migrates `biznice_test` off the maintenance `postgres` DB; the
non-API `verify_*` assume a pre-migrated `biznice` and self-create nothing → **separate jobs, each
its own `postgres:17` service** (verify job sets service `POSTGRES_DB=biznice` + runs `alembic
upgrade head` first). Secrets are test-only throwaway `env:` values (no repo Secrets). No
`## Decisions needed` open; plan checked goal-backward (every SC → ≥1 task, every task → SC + NFR-4,
real files + runnable verify). **Branch (D-P3):** fresh `chore-ci-pipeline` off the 2b tip
`chore-port-verify-cruxes` HEAD (`4960d32`) so the repaired harness + ported cruxes are present for a
meaningful `pytest` run; unmerged v4.0 stack. **Next action:** `/zj:build 3`.)

Prior: 2026-07-24 (**v4.0 Phase 2b RETRO'D — `/zj:retro 2b`. Phase closed `[done]`.** Roadmap
Phase 2b flipped `[verified]` → `[done — verified + retro'd]`. **LEARNINGS Phase 02b banked (2
surprises + 2 repeats):** (1) *a crux whose arithmetic divides evenly can't guard its own advertised
mutation* — the wrong formula yields the right number (MOUSSE 210/10), so the residual sibling
(100/3) is the real red-on-revert guard; pick indivisible-remainder fixtures or the happy-path test
is decorative; (2) *the SC2 mutation table is the highest-signal audit artifact* — the one real
defect surfaced from reading its claims against the arithmetic, not from re-running (a green suite
hides a vacuous test); (repeat) lift the `verify_*` fixture builders + independent oracles verbatim;
(repeat) spend known keepers (drive-the-real-flow D-P2b-5) at plan time, not after a bug. **Deferred
→ BACKLOG p2:** CRUMB `crumb_lead`/`crumb_opportunity` latent TRUNCATE-skip (FK cycle drops them from
`sorted_tables`; mitigated this phase, will bite the first ported test that touches
leads/opportunities). Nothing changed the roadmap picture — Phase 3 (CI, NFR-4) unchanged. **Next
action:** `/zj:plan 3` (CI pipeline — ruff + eslint + `tsc -b` + vitest + `npm run build` + `pytest`
on push/PR, NFR-4, D-M4-2). Optional: `/zj:log phase 2b` to file the formal work log. Verify detail
in the prior entry below.)

Prior: 2026-07-24 (**v4.0 Phase 2b VERIFIED — `/zj:verify 2b`. Verdict PASS**, tag
`zj/good-02b-port-verify-cruxes`. Verifier + reviewer ran in parallel, both **empirically** (not
trusting the build report): all 6 SCs PASS — verifier ran the full suite twice in-container
(**232 passed / 0 skipped** both runs), read all 7 crux tests (each headline Decimal asserted via
the REAL service path against an independent oracle anchored to a literal), independently re-drove
**3/7 SC2 mutations** (inventory/CRUMB/GELATO — each flips a NAMED pytest test RED, all reverted,
`backend/app/` clean), 23/23 `verify_*` exit 0, ruff exit 0, cold boot ok, `git diff -- backend/app/`
**empty** (TEST-ONLY honored), NFR-5 caveats dropped + D-P2b-1..6 recorded (SC6). **Reviewer: 0
blocker / 0 major / 1 minor** — MOUSSE happy-path `test_wip_clears_to_zero_crux` divides evenly
(210/10) so the documented WIP credit-source mutation leaves it green; its SC2 regression guard is
the sibling residual test `test_under_issue_override_clears_wip_and_ties_subledger` (100/3), which
DOES flip RED — the crux stays protected. **Fix loop (minor, `0cb625f`, docstring-only):** corrected
the file-header red-on-revert claim to point at the (D) test, confirmed no sequential `verify_*`
assert was dropped under D-P2b-2, logged both to `## Noticed`; MOUSSE file re-run green (2 passed).
SRD NFR-5 stamped `- **Verified (2b portion):** 0cb625f`; ROADMAP Phase 2b → `[verified]`; artifacts
`VERIFICATION.md` + `REVIEW.md` committed. **Next action:** `/zj:retro 2b` (bank the
"a crux that divides evenly can't guard its own residual mutation — the residual sibling is the real
guard" keeper) or `/zj:plan 3` (CI pipeline, NFR-4). Full build detail in the prior entry below.)

Prior: 2026-07-24 (**v4.0 Phase 2b BUILD COMPLETE — `/zj:build 2b`.** All 17 tasks on branch
`chore-port-verify-cruxes` (off `3f71900`); TEST-ONLY, **`git diff -- backend/app/` empty**. The DoD-named
`verify_*` cruxes now run inside the ordinary `pytest` suite (7 new service-layer crux files + 5 HTTP
audit/RBAC files + shared `seeded_ledger_db` fixture); **SC2 non-vacuity proven** — 7 product mutations each
flip a NAMED pytest test RED, all reverted. Gates: **full suite 232 passed / 0 skipped ×2**, 23/23 `verify_*`
exit 0, ruff exit 0, cold boot ok, `test_harness_selfcheck` green. SRD NFR-5 → **done**, D-P2b-1..6 recorded,
requirements-progress NFR-5 row added. Engineers serialized (shared `biznice_test` DB). **Next action:**
`/zj:verify 2b`. Full task/commit detail in the `## Position` build-complete entry below.)

Prior: 2026-07-24 (**v4.0 Phase 2b PLANNED — `/zj:plan 2b`.** Phase 2b = **port the DoD-named `verify_*`
cruxes into the repaired pytest suite** (NFR-5, the 2b half of the D-P2a-2 split) so reverting a crux turns
a *pytest* test RED, not only a `verify_*` script. **17 tasks** (`.zj/phases/02b-port-verify-cruxes/PLAN.md`),
3 waves: **A** (Tasks 1–8) = one NEW service-layer test file per crux — inventory moving-avg SERVICE path,
GL/AP/AR posting ties, MOUSSE WIP-clears (+1130↔subledger+5190), CRUMB reservation math, GELATO ship-COGS —
plus a shared opt-in `seeded_ledger_db` fixture (the repaired `_isolate` truncates the CoA/location every
test, seeds auth only); **B** (Tasks 9–13) = one HTTP audit/RBAC test per NEW module surface
(MOUSSE/CRUMB/GELATO/AR) + inventory, driving the `client` fixture for 401/403/2xx + attributable `AuditLog`;
**C** (Tasks 14–16) = per-crux non-vacuity sweep (7 documented product mutations each flip a NAMED pytest RED,
then revert — `git diff -- backend/app/` empty), full-suite 0-skip ×2 + 23/23 verify_* still-green + selfcheck +
cold boot, then drop the SRD "script-only" caveats (NFR-5 → done) + `requirements-progress`. **TEST-ONLY phase**
— zero product-code change expected; a surfaced product bug gets a minimal flagged fix, a schema/Alembic need
STOPS-and-flags. **Owner calls at plan (3 AskUserQuestion):** (1) **single phase 2b** (no sub-split — each crux
is a bounded sequential assertion, no concurrency to port); (2) coverage depth = **headline + key supporting
asserts** per crux (control↔subledger EQUALITY, negative-path rejects — not a full re-port, not minimal-only);
(3) audit/RBAC = **one HTTP test per NEW module** + inventory (rest service-layer). Concurrency mutation-proofs
STAY in `verify_*` (D-P2a-2). **6 decisions D-P2b-1..6** (owner 1–3 + architect: local RBAC identities not the
shared roster; AR fixture drives the REAL ship flow — the 11a/11b dead-through-UI keeper; new test files leave
the pure ones untouched) captured in PLAN `## Decisions`, recorded to DECISIONS.md at Task 16. No
`## Decisions needed` open; plan checked goal-backward (every SC → ≥1 task, every task → an SC + NFR-5, real
files + runnable `pytest` verify). **Branch (D-P2b):** build on a fresh `chore-port-verify-cruxes` off the
current `chore-pytest-harness-repair` tip `f97b21a` (retro docs atop verified 2a code `14d838b`, tag
`zj/good-02a-pytest-harness-repair`); unmerged v4.0 stack. **Next action:** `/zj:build 2b`.)

Prior: 2026-07-22 (**v4.0 Phase 2a RETRO'D — `/zj:retro 2a`. Phase CLOSED, ROADMAP `[done — verified]`.**
Banked **LEARNINGS Phase 02a** — 5 keepers: (repeat) pre-decide the *mechanism* not just the diagnosis
when repairing already-diagnosed infra (D-P2a-1 locked the isolation model before a line was written →
zero Wave-A surprises); parallel empirical verifier+reviewer converged on the same design seam (no-DB
contradiction). (surprises) **"all 6 SCs PASS" ≠ phase done** — first-pass green still needed 1+2+2 fixes,
because SCs measure *works now* not *stays working/self-consistent*; **a phase fixing "X silently passes"
MUST ship a test that goes RED when X regresses** — else the exact bug recurs invisibly (the reason
`test_harness_selfcheck.py` exists); **an autouse fixture needing a resource silently makes it mandatory**
and turns any graceful-degrade path into dead code (→ DB is a hard requirement, `skip_if_no_db` retired);
**`"python"` isn't on PATH on standard Debian/CI → `sys.executable`**. Truing-up: the **p1 BACKLOG item
"PLUM live-DB test harness never runs" → RESOLVED + checked off** (2a paid this exact debt); two residual
harness checks (back-to-back rerun automation; committed non-vacuity) folded p3 into the CI backlog item,
their natural home. No roadmap resize — 2b and Phase 3 (CI) stand as-is. **Next action:** `/zj:plan 2b`
(port the DoD-named `verify_*` cruxes into the repaired suite) — the harness it needs is now green. Optional:
`/zj:log phase 2a` to file the formal work log.)

Prior: 2026-07-22 (**v4.0 Phase 2a VERIFIED — `/zj:verify 2a`. Verdict PASS**, tag
`zj/good-02a-pytest-harness-repair`. Verifier + reviewer ran in parallel, both **empirically** (not
trusting the build report): all 6 SCs PASS — full suite **217 passed / 0 skipped twice back-to-back**
(SC4/SC5), `git diff zj/good-01..HEAD -- backend/app/` **empty** (the "zero product-code changes" claim
is TRUE — RBAC test rewrites are genuine strengthenings, not force-green), non-vacuity **re-driven**
(`partners.py is_vendor=False` → `test_create_vendor` RED → revert GREEN, tree clean), 23/23 `verify_*`
exit 0, cold boot `boot-ok`, `biznice_test` migrated head 0017 with live `biznice` intact, no hard-coded
host. **Fix loop closed 1 verifier major + 2 minors + 2 reviewer majors** (commit `a2bb5a6`, TEST-ONLY):
(1) provisioning shelled out to a bare `python` (absent on standard Debian/CI hosts → `FileNotFoundError`
aborts the session, defeating SC6) → `sys.executable`; (2) **owner decision — DB is now a HARD
REQUIREMENT**: no-DB runs `pytest.exit` loud instead of silently skipping; `skip_if_no_db` retired to a
documented no-op alias (avoids a 28-file param-strip); docstrings de-staled; (3) **new
`tests/test_harness_selfcheck.py`** asserts `db_available() is True` so a re-introduced DSN break fails
loud not skips — pins the phase's own zero-silent-skip invariant (verifier's "central deliverable
unprotected" major); (4) SRD NFR-5 → `partial (2a done/2b pending)` stamped `a2bb5a6`, MAP.md test row
de-staled. **Re-verified after fix: full suite 219 passed / 0 skipped** (217 + 2 self-check), ruff exit
0, cold boot ok. SRD NFR-5 stamped; ROADMAP Phase 2a → `[done — verified]`. **Next action:** `/zj:retro
2a` (bank the fix-loop learnings — the silent-skip-invariant-needs-its-own-test keeper + the
DB-hard-requirement decision), or `/zj:plan 2b` (port the `verify_*` cruxes). 2b porting stays deferred.)

Prior: 2026-07-21 (**v4.0 Phase 2a PLANNED — `/zj:plan 2`.** Phase 2 (NFR-5, pytest harness repair)
**split 2a/2b** at plan (owner, D-P2a-2 — mirrors 9a/b/c & 11a/b). **This plan = 2a only:** repair the
harness so the ~100 already-written-but-silently-skipped auth/plum/syerp/core DB-backed tests RUN
0-silent-skip green, fixing the four D-P7-4 root causes. **2b** (separate later phase) ports the
DoD-named `verify_*` cruxes; the **concurrency mutation-proofs STAY in `verify_*`** (not ported, D-P2a-2)
— which is what keeps 2a's isolation model simple. **13 tasks** (`.zj/phases/02a-pytest-harness-repair/PLAN.md`),
3 waves: **A** = 4 root-cause fixes at the harness layer (SC1 DSN probe → libpq kwargs; SC2 NullPool
test engine resolving the app's `get_db`/`AsyncSessionLocal`; SC3+SC4 per-test TRUNCATE…RESTART IDENTITY
CASCADE + reseed on a dedicated `biznice_test` DB, incl. a seeded `User(id="admin-user")`); **B** = green
each package (auth/core/plum/syerp/root), triaging the LATENT breakage these never-run tests will surface
(fix or xfail-with-reason, no blanket skips); **C** = non-vacuity mutation proof + env-pointability (SC6,
in-container `db` AND CI localhost) + regression keepers (cold boot + 23/23 `verify_*` + full 0-skip suite).
**Owner calls at plan:** split 2a/2b; port depth = DoD-named set (2b); concurrency stays in `verify_*`;
isolation = dedicated-DB truncate-reset over savepoint (D-P2a-1, service layer commits pervasively).
**Architect recon de-risked SC3:** RBAC resolves permissions from the DB user, not the token claim
(`dependencies.py`), so tokens minted `subject="admin-user"` need a real `User(id="admin-user")` row
(D-P2a-4). No `## Decisions needed` open; D-P2a-1..4 recorded. **Branch (D-P2a-3):** `chore-pytest-harness-repair`
off `zj/good-01-lint-gates-clean` @ `dd401d1`; unmerged stack. **Next action:** `/zj:build 2a`.)

Prior: 2026-07-21 (**v4.0 Phase 1 RETRO'D — `/zj:retro 1`.** Phase closed `[done — verified +
retro'd]`; tag `zj/good-01-lint-gates-clean` stands. **3 LEARNINGS keepers banked** (LEARNINGS.md
"Phase 01"): (1) a lint plugin's `recommended` preset is a moving target across majors — pin the
major before scoping (react-hooks v7 `recommended` bundled the React-Compiler ruleset = 54 errors/42
behavior-sensitive; `^5` pin/D-P1-1 restored the classic 2-rule set); (2) autofix on a self-registering
modular monolith needs guard-first (`# noqa: F401` side-effect imports before `--fix`) + a cold-boot
gate (`import app.main`) — trust the boot, not the linter's "unused"; (3) re-derive the post-`--fix`
residual from `--statistics` (safe-fix left ~71, not the 18 hand-enumerated — map every rule category to
an owning task, none riding the backstop). **Deferred items homed:** SC4 enforce-smoke + `.npmrc`
global peer-masking → Phase 3 CI backlog item (BACKLOG:18); both stale-doc gaps already fixed at verify
close-out. ROADMAP Phase 1 → `[done]`. **Next action:** `/zj:plan 2` (NFR-5 pytest harness repair +
port `verify_*`). Optional: `/zj:log phase 1` for the formal work log.)

Prior: 2026-07-21 (**v4.0 Phase 1 VERIFIED — `/zj:verify 1`.** Verdict **PASS**, tag
`zj/good-01-lint-gates-clean`. Verifier + reviewer both ran **empirically** (not trusting the build
report): all 5 SCs pass — SC1 flat config/devDeps/deleted `.eslintrc.cjs`/fixed `lint` script wired
(print-config confirms rules loaded); SC2 `npm run lint` **exit 0**; SC3 `ruff 0.15.18 check .` **exit
0**; SC4 both gates' red→green enforce proof **re-run independently** (planted → exit 1, revert → exit
0, tree left clean); SC5 **23/23 `verify_*`** in-container + **Vitest 131/131** (the build's "44/131"
resolved to 44 files/131 tests, **0 fail/skip**) + `tsc -b && vite build` exit 0 + cold-boot `import
app.main` BOOT_OK. **Reviewer: 0 findings** — F401 import sets byte-identical in every load-bearing file
(only I001 reorder, `# noqa: F401` guards intact, full FK graph resolves), F821 via real `TYPE_CHECKING`,
`seeded_db` collapse scope-safe, `l`→`line` rename complete, removed F841 locals side-effect-free, 4
deleted exhaustive-deps disables genuinely stale. `npm ci --dry-run` exit 0 with tracked `.npmrc`.
**3 minor gaps, none undermine the goal — 2 fixed in the verify close-out:** stale `CLAUDE.md:72`
("lint gates non-functional") corrected; `BACKLOG.md:44` p1 item marked resolved (CI item stays open).
**Logged (not built):** SC4 has no standing automated enforce-test → deferred to Phase 3 CI (PLAN.md
`## Noticed`). SRD NFR-6 → **verified** + stamped `ee11674`; ROADMAP Phase 1 → `[verified]`; artifacts
`VERIFICATION.md`/`REVIEW.md` committed. **Next action:** `/zj:retro 1` (bank the D-P1-1 react-hooks-preset
+ F401-side-effect-guard lessons), then `/zj:plan 2` (NFR-5 pytest harness repair + port `verify_*`).)

Prior: 2026-07-21 (**v4.0 Phase 1 BUILD COMPLETE** — `/zj:build 1` on branch `chore-lint-gates-clean`
(cut off the plan-carrying tip `a6ee1fb`, code-identical to `origin/master`; Task-0 branch-point
deviation logged). **All 13 tasks (0–12) done, atomic commits, tree clean.** NFR-6 delivered: **both
lint gates fixed-to-clean + proven enforcing.** Wave A (frontend ESLint 10 flat gate): flat
`eslint.config.js`, `.eslintrc.cjs` deleted, `lint` de-`--ext`'d, `npm run lint` **exit 0**. Wave B
(backend `ruff` gate): ~1159 violations fixed-to-clean (1139 safe-autofix + F821×4 via `TYPE_CHECKING` +
F811 `seeded_db`→`tests/auth/conftest.py` + E741/F841 hand-fixed + 51 load-bearing `syerp/service`
re-exports `# noqa: F401`), `ruff check .` **exit 0**. Wave C: **23/23 `verify_*` exit 0** in-container +
**cold boot** (`/health/ready` 200, `import app.main` BOOT_OK) + Vitest **44/131** + `tsc -b && vite
build` exit 0; **red→green enforce proof** on both gates (planted violation → non-zero, revert → 0).
**One MATERIAL deviation → owner decision D-P1-1:** installed `eslint-plugin-react-hooks@7.1.1`
redefined `recommended` to bundle the React-Compiler ruleset (54 errors/41 files) — out of NFR-6 scope;
owner chose **pin to `^5`** (classic 2-rule recommended = plan intent). Added `frontend/.npmrc`
`legacy-peer-deps=true` (v5 peer-declares eslint≤^9) + re-declared `@testing-library/dom` — **both flagged
for NFR-4/Phase-3 CI** (`npm ci` must keep them). SRD NFR-6 → `implemented` (CI-wiring clause deferred to
NFR-4/Phase 3); `requirements-progress.md` NFR row added; checklist archived to
`docs/tasks/_completed/2026-07-21-chore-lint-gates-clean.md`. Unrelated `.vscode/settings.json` cosmetic
edit **stashed** at owner request (restore with `git stash pop`). **Noticed (non-blocking):** the
transient-red intermediate commit `e7c6e18` (testing-lib restored next commit; tip green); root
`tests/conftest.py` + `tests/core/conftest.py` predate the ABOUTME-header standard (future sweep).
**Next action:** `/zj:verify 1`.)

Prior: 2026-07-20 (**v4.0 Phase 1 PLAN COMPLETE** — `/zj:plan 1`. Phase 1 = **lint gates
fixed-to-clean (NFR-6)**; artifacts in `.zj/phases/01-lint-gates-clean/PLAN.md`. **13 tasks** (Task 0
branch + 12 work) in 3 waves — **A: frontend gate** (add `@eslint/js`/`eslint-plugin-react-hooks`/
`eslint-plugin-react-refresh`; write flat `eslint.config.js`; fix the `--ext`-broken `lint` script;
delete `.eslintrc.cjs`; fix to zero) · **B: backend gate** (ruff availability + convention; safe
`--fix`; audit/`# noqa`-guard side-effect imports FIRST; resolve the ~71 survivors — F821×4, F811/E741/
F841, UP035×~23, 2 unsafe) · **C: regression + enforce-proof** (23/23 verify_* in-container + Vitest +
build + **cold boot**; red→green gate proof; flip NFR-6 status). **Recon done at plan** (grounds the
scope): FE is near-clean already (`tsc -b` `noUnusedLocals`/`strict` keeps unused out; only 6
pre-existing `react-hooks/exhaustive-deps` disables, which prove react-hooks was the intended
ruleset) — deps `eslint@10.5.0`+`typescript-eslint@8.62.0` already installed, just no flat config;
BE has **1159 ruff violations, 1088 SAFE-auto-fixable**, config already committed in `pyproject.toml`
(E/F/I/UP), ruff pinned in `requirements-dev.txt` but absent from `.venv`/image. **Top risk (handled):**
blind F401 `--fix` could strip a load-bearing side-effect import (module self-registration /
`app/main.py` `import app.core.models`) and re-introduce the Phase-13 cold-boot 500 — sequenced as
audit-and-`# noqa`-first (Task 6) → review every deleted-import line (Task 7) → empirical cold-boot +
23/23 gate (Task 10). **3 owner decisions bound at plan:** D-M4-3 fix-to-clean (not ratchet);
**rule strictness = recommended sets only** (no tseslint recommendedTypeChecked, no ruff B/SIM/RUF);
**formatter scope = lint-check only** (no `ruff format`/`prettier --check`; E501 stays ignored).
No `## Decisions needed` open (one conditional escalation: if an F821 is a real runtime bug, stop +
surface). **Branch:** cut fresh `chore-lint-gates-clean` off `origin/master` (current
`feature-syerp-ar-invoicing` is fully merged, 0 ahead; it may be deleted). **Next action:**
`/zj:build 1`.)

Prior: 2026-07-20 (**v3.0 SHIPPED to master** — `/zj:ship`. The 11a→13 stack (135 commits) merged to
`master` via **PR #3**, fast-forward `3b762ba..87fb79d` preserving SHAs (same known-good pattern as v2.0's
PR #2) — `origin/master == 87fb79d`, PR #3 MERGED, all `zj/good-*` tags + annotated `v3.0` (→`e92b91d`)
pushed and reachable from master. **The standing `/zj:ship` master-merge debt is now CLEARED** (it had
carried since v2.0). Preflight was a fresh green on the branch tip: **23/23** live `verify_*` exit 0 +
**131/131** Vitest / 44 files + `npm run build` exit 0 (lint gates still non-functional, BACKLOG p1 — the
v4.0 headline). Changelog already carried v3.0 (generated at milestone close); `.zj/` + `docs/tasks/`
artifacts shipped in the merge per repo convention.

**v4.0 "Infra-debt + quality paydown" SPEC'D** (`/zj:spec`, 2026-07-20) — DoD confirmed into 5 clauses,
**NFR-4..8** written under new **PRD-12** (trustworthy engineering baseline; no new end-user capability).
Scope (D-M4-1, owner): NFR-4 CI (GitHub Actions, D-M4-2) + NFR-5 pytest-harness repair & `verify_*`
ported into the suite + NFR-6 both lint gates fixed-to-clean (D-M4-3) + NFR-7 shared inventory
FOR-UPDATE lock & inbound bin-blind fix + NFR-8 human UAT; **CRISP/offline deferred.** Proposed 5-phase
mapping in ROADMAP (lint → harness → CI → race-safety → UAT; dependency-first). Owner note: asked what
"CI" was → confirmed the milestone hardens the foundation, adds nothing users click. **Next action:**
`/zj:plan 1` (Phase 1 = lint gates fixed-to-clean, NFR-6). Post-merge housekeeping: delete the merged
`feature-syerp-ar-invoicing` branch when Phase 1 branches off master.

Prior: 2026-07-19 (**Milestone v3.0 "Customer & logistics" CLOSED + tagged `v3.0`** — `/zj:milestone`
done. DoD audited goal-backward (`.zj/MILESTONE-v3.0-AUDIT.md`): the WHOLE money loop driven on ONE
sales order end-to-end (order→reserve→pick→pack→partial-ship→invoice-from-shipment→post→partial+full
receipt→auto-Paid), all 3 clauses MET, 19/19 + 23/23 live `verify_*` + build + 131 Vitest. **Two gaps
found, BOTH FIXED at close (owner, D-M3-1/2, `97b977b`):** GAP-1 (AR aging falsely tripped a negative
1120 tie-out when a receipt predated its invoice_date — prepayment reclassified in `ar_aging_report`,
pinned by `verify_ar` scenario G, load-bearing) + GAP-2 (invoice picker bare UUID → resolved
`item_label`). **Records:** CHANGELOG v3.0 + milestone-close fixes, `.zj/logs/milestone-v3.0.md`
(130 commits, ~14.6h/10 sessions), LEARNINGS `## Milestone v3.0` (headline: review-not-verify caught
the defect on all 5 phases), DECISIONS D-M3-1..4 + index regenerated 73→134. Phases 11a/11b/12a/12b/13
archived to `.zj/history/v3.0/`. **Next milestone = v4.0 Infra-debt + quality paydown (D-M3-3).**
**Next action:** `/zj:spec` (sharpen the v4.0 DoD into clauses) then `/zj:plan 1`. Optional: `/zj:ship`
to merge the 11a+11b+12a+12b+13 stack to master.

Prior: 2026-07-19 (**Phase 13 RETRO'D** — `/zj:retro 13`. Roadmap already marked
`[done — verified 2026-07-19]`; no future phase resized. **LEARNINGS Phase 13 banked (1 surprise +
3 patterns):** (1) **the headline — mirroring a broad `except IntegrityError → retry` is only sound
if the mirrored fn can't raise a *different* IntegrityError, and adding a nullable FK the exemplar
lacks silently breaks that** (`create_invoice` copied `create_bill`'s number-collision retry but also
took an unvalidated `sales_order_id` FK → a bad id raised an FK error the retry misread as a collision
→ unbounded recursion/500; keeper = narrow the except to the specific constraint + bound it, AND
up-front-validate every FK the mirror doesn't have); (2) **a mandated adjacent-untouched-surface
regression assertion caught a real production-boot 500** the phase that introduced it (12a) had
mislabeled a "dev-only `--reload` race" — the `syerp_inventory_txn.bin_id→gelato_bin` metadata gap,
fixed by importing `app.core.models` at boot; keeper = the "assert the neighbour still works" task is
the only gate that exercises a cold process like production; (3) **dead-through-UI trap caught in-build
a 2nd straight phase** (`qty_invoiced`) — counter-measure now reliable; (4) **5th consecutive phase
where the review, not the verify suite, caught the defect that mattered** — budget both every phase.
Deferred items homed → BACKLOG p3: invoice void/credit-memo functional gap, dead `partially_paid` FE
badge, late-invoice COGS/revenue period split. **Phase 13 was the FINAL v3.0 phase (DoD clause 3
closed) — v3.0 milestone is now complete pending close-out.** Artifacts:
`.zj/phases/13-syerp-ar-invoicing/{PLAN,VERIFICATION,REVIEW}.md`, `.zj/LEARNINGS.md` Phase 13.
**Next action:** `/zj:milestone` (audit the v3.0 DoD, tag the release, archive phases 11–13, roll the
roadmap to the next milestone). Optional: `/zj:log phase 13` (formal work log); `/zj:ship` to merge the
11a+11b+12a+12b+13 stack to master.)

Prior: 2026-07-19 (**Phase 13 VERIFIED** — `/zj:verify 13`, tag `zj/good-13-syerp-ar-invoicing`.
Both checks ran in parallel; all 7 SYERP-13 success criteria PASS empirically — `verify_ar.py` 17/17
+ `verify_ar_api.py` 29/29 + **23/23 full regression**, aging ties Decimal-exact to the debit-normal
1120 (no negation), TB nets zero WITH AR posted, BS balances, RBAC 401/403/200 on all 8 routes,
attributable audit rows; verifier mutation-proved the record_receipt lock (revert `for_update` →
over-collected 120/100). **Fix loop landed 1 REVIEW MAJOR + 3 doc gaps:** `create_invoice` took a
client-supplied nullable `sales_order_id` FK **unvalidated** → a bad id failed only on the header flush,
was misread as an invoice-number collision, and **recursed forever** (RecursionError/500); fixed with
up-front 404 validation + a one-attempt-bounded retry (`7610e63`), pinned by new `verify_ar.py` scenario
**(D2)** (bogus id → clean 404, persists nothing); doc gaps closed — SYERP-13 row added to
`requirements-progress.md`, SRD:478 flipped `planned`→`verified` (stamped `7610e63`), MAP migration head
refreshed `0012`/`0014`→`0017`. Closes v3.0 DoD clause 3 (the FINAL v3.0 phase). Artifacts:
`.zj/phases/13-syerp-ar-invoicing/{VERIFICATION,REVIEW}.md`. **Next action:** `/zj:retro 13` (banks the
mirror-exemplar-shares-no-FK-surface + unvalidated-FK→unbounded-retry learnings), then v3.0 milestone.)

Prior: 2026-07-19 (**Phase 13 BUILD COMPLETE** — `/zj:build 13` on fresh branch
`feature-syerp-ar-invoicing` (cut off the code-identical 12b tip carrying the plan; a bare-tag branch
would have dropped the plan — 12a/12b precedent). **All 18 tasks shipped**, SYERP-13 AR & sell-side
books end-to-end; **v3.0 DoD clause 3 closed**. Wave A: Invoice/InvoiceLine + Receipt/ReceiptAllocation
models + `qty_invoiced` accumulator on `crumb_sales_order_line` (dead-through-UI keeper: model→schema→FE
render→Vitest) + migration **0017** (clean up/down round-trip) + AR schemas. Wave B: `service/ar.py`
(`create_invoice` FOR-UPDATE lock on SO-line rows + price locked to SO `unit_price` + stamps qty_invoiced;
`post_invoice` → **Dr 1120 / Cr 4110** JE `entry_date=invoice_date`; `record_receipt` FOR-UPDATE lock on
invoice rows + reused `bills._is_overpayment` + **Dr cash / Cr 1120** JE + auto-Paid at zero) + `ar_aging_report`
(**NO negation** — 1120 debit-normal) + thin RBAC router `/syerp/ar/*` audit-after-commit. Wave C:
`verify_ar.py` **16 asserts green** — end-to-end tie-out (asserts the 12b COGS-on-ship JE, does not rebuild),
aging **grand_total == 1120 control Decimal-exact**, over-invoice/over-receipt 422, and **BOTH concurrency
locks mutation-proven** (revert record_receipt lock → 120-vs-100 over-collect; revert create_invoice lock →
joint 12-vs-10 over-invoice + qty_invoiced lost-update; restore → one success/one 422) — the 12b "only the
guard under test can reject" discipline honored; `verify_ar_api.py` **29 asserts** (HTTP 401/403/200 triad on
all 8 routes + attributable audit + inventory-receipt regression lock); **full regression 23/23 green**, TB
nets zero, BS balances. Wave D: Invoices list/create-from-shipment/detail + Receipts + AR Aging screen + nav +
routes; FE **44 files / 131 tests green**, `npm run build` exit 0. **Two material handlings, both fixed:**
(1) the AR `ReceiptCreate` schema (Task 5) **shadowed** the inventory costed-receipt `ReceiptCreate`, silently
breaking `POST /inventory/items/{id}/receipts` → renamed to `ArReceiptCreate`, regression-locked in
verify_ar_api; (2) the Task-13 regression assertion surfaced a **pre-existing 12a production 500** —
`syerp_inventory_txn.bin_id → gelato_bin` FK unresolvable on a fresh process (lazy gelato model imports +
importlib registration) → fixed in `main.py` by importing the `app.core.models` aggregator at boot
(**D-P13-8**; D-P12a-3 preserved). Plus a phantom-`partially_paid` docstring corrected (real FSM is
draft→posted→paid). Lint gates still non-functional (BACKLOG p1); correctness rests on verify_* (23/23) +
Vitest (131). Checklist (all 18 ticked): `docs/tasks/feature-syerp-ar-invoicing.md`. **Next action:**
`/zj:verify 13`.)

Prior: 2026-07-19 (**Phase 13 PLAN COMPLETE** — `/zj:plan 13` on branch
`feature-gelato-pick-pack-ship` (planning artifacts; build branches fresh). **Phase 13 = SYERP-13 AR &
sell-side books, the FINAL v3.0 phase** — closes v3.0 DoD clause 3. **Single phase** (owner, D-P13-1 — not
sub-split; AR aging is a thin copy of AP aging, TB/P&L/BS already exist from 9c). **18 tasks in 4 waves**
(`.zj/phases/13-syerp-ar-invoicing/PLAN.md`): Wave A schema (Invoice+InvoiceLine, Receipt+ReceiptAllocation
models mirroring Bill/Payment, `qty_invoiced` accumulator on `crumb_sales_order_line`, migration **0017**,
schemas) → Wave B service (`service/ar.py`: uninvoiced-shipments query, `create_invoice`, `post_invoice`
→ Dr 1120 AR/Cr 4110 Revenue JE, `record_receipt` + allocations + FOR-UPDATE guard → Dr cash/Cr 1120 JE +
auto-Paid; `ar_aging_report` in reports.py; thin RBAC router `/syerp/ar/*` audit-after-commit) → Wave C
verify (`verify_ar.py` control-tie + invoice-from-shipment match + overpayment reject + COGS-on-ship tie +
**two load-bearing concurrency scenarios** — over-receipt AND double-invoice, both mutation-proven;
`verify_ar_api.py` HTTP RBAC/audit; full regression + TB nets zero) → Wave D frontend (Invoices
list/create-from-shipment/detail, Receipts, AR Aging screen + nav; Vitest asserts real payload shape incl.
`qty_invoiced` render). **Key facts:** COGS-on-ship JE (Dr 5100/Cr 1130) **already shipped in 12b** —
Phase 13 asserts it, doesn't rebuild (D-P13-3); invoice price **locks to SO-line `unit_price`** (owner,
D-P13-2); `qty_invoiced` claimed at draft-create mirroring AP (D-P13-5); AR aging control-tie has **NO sign
negation** (1120 debit-normal — top risk, D-P13-7). All 5 recurring keepers baked in (concurrency-from-start
with the 12b "only the guard under test can reject" fixture discipline, subledger↔control as EQUALITY not
zero, dead-through-UI field wired end-to-end in Task 3, non-optional HTTP audit/RBAC script, full regression
gate). Decisions D-P13-1..7 recorded; no `## Decisions needed` open; plan checked goal-backward at manager
review (every SC → ≥1 task, every task → an AC, real files + runnable verify). **Branch (D-P13-6):** build
on a fresh `feature-syerp-ar-invoicing` off tag `zj/good-12b-gelato-pick-pack-ship` (`553bcfb`); migration
0017. **Next action:** `/zj:build 13`.)

Prior: 2026-07-19 (**Phase 12b RETRO'D** — `/zj:retro 12b` on branch
`feature-gelato-pick-pack-ship`, tag `zj/good-12b-gelato-pick-pack-ship` over `553bcfb`. Roadmap
marked `[done — verified + retro'd]`; **CRUMB→GELATO outbound loop complete** (v3.0 DoD clause 2 closed).
**LEARNINGS Phase 12b banked (4 keepers):** (1) **the headline — a forced-interleave concurrency test can
pass for the WRONG reason and mask the exact bug it targets**: scenario g's staging bin was seeded to
*exactly* the ship qty, so `post_issue`'s floor guard (a *bystander* guard) rejected the duplicate while
the real defect — an UNLOCKED shipment-status FSM gate letting two ships of one packed shipment double-post
COGS — sailed through untested; keeper = build concurrency fixtures so ONLY the guard under test can reject
(scenario h: order 10 ship 5, ample staging, only the shipment-row lock can 409 the duplicate; mutation-proven);
(2) **mirroring an exemplar's lock is safe only if your transition shares its safety property** — MOUSSE
`issue_components`' status-before-lock shape is safe because issuing is *repeatable*; ship is a *one-shot
terminal* transition, so the copied item locks are necessary-but-not-sufficient — the fix locks the Shipment
row (`SELECT … FOR UPDATE`) before the FSM gate; (3) **the dead-through-UI trap was caught IN-BUILD this time**
(qty_shipped serialization on `SalesOrderLineRead`) — the counter-measure works; (4) **parallel
verifier+reviewer, reviewer-blocker-overrides-PASS, is load-bearing 4 phases running** (11a/11b/12a/12b).
Deferred items all homed at verify, trued up at retro: pick-path races Q1/Q2 → BACKLOG p2; bin-blind-desync
p2 **outbound half now closed** (inbound `post_transfer`/`post_adjustment`/MOUSSE-issue still open); downgrade
test → p3. Artifacts: VERIFICATION.md + REVIEW.md + LEARNINGS.md Phase 12b. **Next action:** `/zj:plan 13`
(SYERP-13 AR + invoice-from-shipment + customer receipts + AR aging tie-out — closes v3.0 DoD clause 3).
Optional: `/zj:log phase 12b` (formal work log); `/zj:ship` to merge the 11a+11b+12a+12b stack.)

Prior: 2026-07-19 (**Phase 12b VERIFIED** — `/zj:verify 12b` PASS on branch
`feature-gelato-pick-pack-ship`, tag `zj/good-12b-gelato-pick-pack-ship` over `553bcfb`. Verifier +
reviewer ran in parallel; the **reviewer caught a BLOCKER the verifier's concurrency test masked**:
`execute_ship` gated on an UNLOCKED shipment status and locked only the `InventoryItem` rows, so two
concurrent ships of ONE packed shipment could both pass the FSM gate → **double inventory issue +
double Dr 5100 / Cr 1130 COGS JE + double reservation relief**. Scenario g missed it (its staging bin
held exactly the ship qty, so `post_issue`'s floor guard incidentally rejected the duplicate). **Fixed**
(`553bcfb`): load the shipment `SELECT … FOR UPDATE` before the FSM gate. **New durable test**
`verify_gelato_ship.py` scenario (h) — one packed shipment partially fulfilling its SO (order 10, ship 5)
shipped twice concurrently; mutation-proven (reverting the lock → 2 JEs / qty_shipped 10 / staging drawn
twice). Full regression re-run **21/21 verify_* exit 0**, TB nets zero WITH the ship COGS JE, 1130 ties
to subledger; `verify_gelato_ship.py` **21/21**, `verify_gelato_ship_api.py` **23/23**. Two lower-severity
pick-path shipment-header races (review Q1/Q2) → BACKLOG p2; migration-downgrade automated-test gap → p3;
all recorded in PLAN `## Noticed`. Closes v3.0 DoD clause 2 (warehouse fulfillment outbound). Artifacts:
VERIFICATION.md + REVIEW.md in the phase dir. **Next action:** `/zj:retro 12b` (banks the "review catches
what the verifier's own test masks" keeper + the same-shipment-lock class) then `/zj:plan 13`.)

Prior: 2026-07-18 (**Phase 12b BUILD COMPLETE** — `/zj:build 12b` done on branch
`feature-gelato-pick-pack-ship` (cut off the 12a docs-on-top tip `bde5b77`, code-identical to tag
`zj/good-12a-gelato-bins-putaway`, D-P12b-8). **All 15 tasks shipped**, GELATO outbound pick → pack →
ship end-to-end. Wave A: migration **0016** (Shipment + ShipmentLine tables, `qty_picked`/`qty_shipped`
on `crumb_sales_order_line`) round-trips clean; shipment schemas. Wave B: NEW SYERP bin-aware
`post_issue` (single signed `issue` leg, item-master FOR-UPDATE before floor read); GELATO
`service/shipments.py` pick (net-zero pick-bin→staging via `post_putaway`, stamps qty_picked, SO
confirmed→fulfilling) / pack (FSM picking→packed, partial-pack trims staged qty) / **ship** (bin-aware
`post_issue` from staging + ONE balanced **Dr 5100 COGS / Cr 1130 Inventory** JE atomic via single
`db.commit()`, relieves qty_reserved + stamps qty_shipped, FSM→shipped); thin RBAC-gated router with
`write_audit(target_id=str(shipment.id))`. Wave C: `verify_gelato_ship.py` **22 asserts green**
(accounting crux Decimal-exact, reservation relief, partial-ship, negative space, control↔subledger tie,
**load-bearing concurrency Barrier — mutation-proven**) + `verify_gelato_ship_api.py` **23 asserts**
(HTTP 401/403/200 + attributable audit + int-PK target_id string guard); **full regression 19/19 green,
TB nets zero WITH the ship COGS JE, 1130 ties to subledger**. Wave D: shipment hooks + Fulfillment
pick→pack→ship screen + SO-detail Fulfill/Ship affordance; FE **38 files / 116 tests green**, `npm run
build` exit 0. **Three material handlings:** (1) `post_putaway` had no `commit` param → added
backwards-compatible `commit=True` so pick batches atomically (engineer correctly STOPPED, forced fix,
Deviations); (2) task-4 shipment FK schema fields mistyped `Optional[int]` → `Optional[str]` (String(36));
(3) **the recurring dead-through-UI trap CAUGHT** — SO-detail `qty_shipped` column rendered from a field
`SalesOrderLineRead` did not serialize → added `qty_picked`/`qty_shipped` to the read schema. Lint gates
remain non-functional (BACKLOG p1); correctness rests on verify_* (19/19) + Vitest (116), per project
convention. Noticed (non-blocking): belt-and-suspenders redundant ship locks; a dev-only `--reload`
FK-race on `syerp_inventory_txn.bin_id→gelato_bin` (production unaffected). **Next action:**
`/zj:verify 12b`.)

## Position

- **Step:** build — **v4.0 Phase 3 (CI pipeline, NFR-4) BUILD COMPLETE** (`/zj:build 3`, 2026-07-24).
  Branch `chore-ci-pipeline` off the plan tip `8a27a46`. All 9 tasks done; `.github/workflows/ci.yml`
  with four blocking jobs proven green on real Actions runs (all-green 30140504003; 232 passed / 0
  skipped; 14/14 verify_*), broken-test red (30140642516) + lint red (30140870255) each reverted
  green, and a required-status-gated PR #4 → master (BLOCKED→CLEAN). D-P3-4 (owner): conftest DB probe
  → maintenance `postgres` DB so a fresh CI Postgres self-provisions (test-infra only). SRD NFR-4 →
  done (pending `/zj:verify 3`). PR #4 left open — merge out of scope. **Next action:** `/zj:verify 3`.

- **Step:** build — **v4.0 Phase 2b (port `verify_*` cruxes into pytest, NFR-5) BUILD COMPLETE**
  (`/zj:build 2b`, 2026-07-24). Branch `chore-port-verify-cruxes` cut off `3f71900` (the plan-doc
  tip carrying PLAN.md, not the bare `f97b21a` — trivial deviation, PLAN `## Deviations`). **All 17
  tasks (0–16) done, atomic commits, tree clean** (only owner's `.vscode/settings.json` unstaged).
  TEST-ONLY phase — **`git diff -- backend/app/` empty (zero product-code change).**
  **Wave A** (1–8, service-layer cruxes, 0 skips): scaffold+`seeded_ledger_db` (`521648f`),
  inventory moving-avg (`6a50420`), GL ties (`0ae185b`), AP GR/IR-clears (`0777467`), AR aging↔1120
  via REAL ship flow (`e589bbd`), MOUSSE WIP-clears+5190 (`0335fb0`), CRUMB reservation (`6a63194`),
  GELATO ship-COGS (`e7fcb3a`). **Wave B** (9–13, HTTP audit/RBAC per surface, 401/403/2xx +
  attributable AuditLog): MOUSSE (`6241fa3`), CRUMB (`beff018`/`56ae777`), GELATO int-PK
  (`0cadde4`), AR (`8cde0fe`), inventory receipt — new, no prior coverage (`13a27cf`). **Wave C**:
  SC2 non-vacuity — 7 product mutations each flip a NAMED pytest RED, all reverted, tree clean
  (`79b56e7`); regression — **full suite 232 passed / 0 skipped ×2**, 23/23 verify_* exit 0, ruff
  exit 0 (one I001 fixed `56ae777`), cold boot ok; SRD NFR-5 → **done**, D-P2b-1..6 recorded,
  requirements-progress NFR-5 row added (`15382ae`). Engineers serialized (shared `biznice_test`
  DB). Checklist: `docs/tasks/chore-port-verify-cruxes.md` (all 17 ticked). **Next action:**
  `/zj:verify 2b`.

- **Step:** plan — **v4.0 Phase 2b PLANNED** (`/zj:plan 2b`, 2026-07-24). 17 tasks / 3 waves in
  `.zj/phases/02b-port-verify-cruxes/PLAN.md`; TEST-ONLY. Owner decisions: single phase,
  headline+supporting depth, one HTTP audit/RBAC test per new module. Concurrency stays in
  `verify_*` (D-P2a-2).

- **Step:** verify — **v4.0 Phase 2a (pytest harness repair, NFR-5) VERIFIED — Verdict PASS**, tag
  `zj/good-02a-pytest-harness-repair`. All 6 SCs pass empirically; fix loop closed 1 major + 2 minors +
  2 reviewer majors (commit `a2bb5a6`, test-only — DB now a hard requirement, `sys.executable`,
  `test_harness_selfcheck.py` self-check); re-verified full suite **219 passed / 0 skipped**, 23/23
  `verify_*`, cold boot ok. **Next action:** `/zj:retro 2a` or `/zj:plan 2b`. (Prior build detail below.)

- **Step:** build — **v4.0 Phase 2a (pytest harness repair, NFR-5) BUILD COMPLETE** on branch
  `chore-pytest-harness-repair` (cut off `93de57d`, code-identical to `zj/good-01-lint-gates-clean`
  / `dd401d1`; Task-0 deviation to carry PLAN.md). **All 13 tasks (0–12) done, atomic commits, tree
  clean** (only the owner's `.vscode/settings.json` stays unstaged). **Headline: the ~100 never-run
  DB-backed tests now RUN — full suite 217 passed / 0 failed / 0 skipped on one shared DB, 167s.**
  Wave A fixed the four D-P7-4 root causes at the harness layer: DSN probe→libpq kwargs (`afa5798`);
  dedicated migrated `biznice_test` DB (head `0017`, app `biznice` untouched, `fe6a223`); NullPool test
  engine wired to the app's `get_db`/`AsyncSessionLocal` — no InterfaceError (`6ad45c9`); per-test
  `TRUNCATE … RESTART IDENTITY CASCADE` + reseed + seeded `User(id="admin-user")` (`871998c`). Wave B
  greened all packages — first run 32 failed, ALL triaged as TEST drift (zero product-code changes):
  auth 65 (`592faac`+`7ebf821`), core 13 (`3ce7394`), root (`52e7926`), plum 40 (`39d1ec0`), syerp 99
  (`b12d711`). **Owner decision D-P2a-5** (the never-run tests assumed claim-based tokens; shipped RBAC
  derives perms from the DB user): seeded a test-identity roster (min churn) + forced `BNS_ADMIN_*` creds
  + per-package domain-drift fixes. Wave C: non-vacuity proven (mutate `create_partner.is_vendor` →
  `test_create_vendor` RED → revert green, Task 10); env-pointability documented, no hard-coded host
  (SC6, Task 11); **regression gate green — cold boot `BOOT_OK` + 23/23 `verify_*` exit 0 + 217/0/0
  suite** (Task 12); ruff gate held (one auto-fixed I001). **No xfail/skip needed.** Container dev-deps
  install is ephemeral (bake a test image → Phase 3). **Next action:** `/zj:verify 2a`.
  Checklist: `docs/tasks/chore-pytest-harness-repair.md`.

- **Step:** milestone — **v3.0 "Customer & logistics" CLOSED + tagged `v3.0`** (`/zj:milestone`,
  2026-07-19). DoD audited goal-backward — whole money loop on one order end-to-end, all 3 clauses MET,
  19/19 + all 23 `verify_*` + build + 131 Vitest; 2 audit gaps BOTH fixed at close (D-M3-1/2, `97b977b`,
  pinned by `verify_ar` scenario G + FE tests). Records produced; phases 11a/11b/12a/12b/13 archived to
  `.zj/history/v3.0/`; roadmap + PROJECT rolled to **v4.0 Infra-debt + quality paydown (D-M3-3)**.
  **Next action:** `/zj:spec` (sharpen the v4.0 DoD into clauses) then `/zj:plan 1`. Optional:
  `/zj:ship` to merge the 11a+11b+12a+12b+13 stack to master.

- **(historical) Step:** **RETRO'D** — **Phase 13 (SYERP-13 AR & sell-side books — the FINAL v3.0 phase) closed
  2026-07-19** (`/zj:retro 13`), tag `zj/good-13-syerp-ar-invoicing`. Roadmap marked
  `[done — verified 2026-07-19]`; **v3.0 DoD clause 3 closed → v3.0 milestone complete pending close-out.**
  LEARNINGS Phase 13 banked (mirror-a-retry-only-safe-if-no-new-FK headline; adjacent-surface regression
  caught a real boot 500; in-build dead-through-UI catch a 2nd phase; review-caught-the-defect 5 phases
  running). Deferred → BACKLOG p3: invoice void/credit-memo, dead `partially_paid` badge, late-invoice
  COGS/revenue period split. **Next action:** `/zj:milestone` (v3.0 close). Optional: `/zj:log phase 13`;
  `/zj:ship` to merge the 11a+11b+12a+12b+13 stack.

- **(historical) Step:** **BUILD COMPLETE** — **Phase 13 (SYERP-13 AR & sell-side books — the FINAL v3.0 phase)
  built 2026-07-19** (`/zj:build 13`) on branch `feature-syerp-ar-invoicing`. All 18 tasks, **v3.0 DoD
  clause 3 closed**. Delivers the invoice (Dr 1120/Cr 4110) + receipt (Dr cash/Cr 1120) JEs + AR aging
  tying Decimal-exactly to the 1120 control (the COGS-on-ship JE was asserted, not rebuilt — D-P13-3).
  Proof: `verify_ar.py` 16 asserts (both concurrency locks mutation-proven) + `verify_ar_api.py` 29 asserts
  + **23/23** full regression (TB nets zero, BS balances) + FE **44 files / 131 tests** + `npm run build`
  exit 0. Decisions D-P13-1..8 (D-P13-8 = the app.core.models boot import). Plan + checklist all ticked.

- **(historical) Step:** **RETRO'D** — **Phase 12b (GELATO outbound: pick → pack → ship) closed 2026-07-19**
  (`/zj:retro 12b`), tag `zj/good-12b-gelato-pick-pack-ship` at `553bcfb`. Roadmap marked
  `[done — verified + retro'd]`. **v3.0 DoD clause 2 (warehouse fulfillment outbound) closed** and the
  sell-side **COGS** JE (Dr 5100 / Cr 1130) posts atomically on ship. Retro banked LEARNINGS Phase 12b
  (4 keepers — the forced-interleave-test-passes-for-the-wrong-reason headline, the mirror-an-exemplar's-lock
  caveat for one-shot vs repeatable transitions, the in-build dead-through-UI catch, and review-overrides-PASS
  now load-bearing 4 phases running). Deferred items homed: pick-path races Q1/Q2 → BACKLOG p2;
  bin-blind-desync outbound half closed (inbound still open, p2); downgrade test → p3. **Next action:**
  `/zj:plan 13` (SYERP-13 AR + invoice-from-shipment). Optional: `/zj:log phase 12b`; `/zj:ship` to merge
  the 11a+11b+12a+12b stack.

- **(historical) Step:** **BUILD COMPLETE** — **Phase 12b (GELATO outbound: pick → pack → ship) built 2026-07-18.**
  All **15 tasks** on branch `feature-gelato-pick-pack-ship`. Closes the v3.0 DoD clause 2 (warehouse
  fulfillment outbound) and posts the sell-side **COGS** JE (Dr 5100 / Cr 1130). Proof: `verify_gelato_ship.py`
  22 asserts + `verify_gelato_ship_api.py` 23 asserts + **19/19** full regression (TB nets zero with the
  new JE, 1130↔subledger tie) + FE **38 files/116 tests** + `npm run build` exit 0. Checklist (all 15
  ticked): `docs/tasks/feature-gelato-pick-pack-ship.md`.

## (historical) Position

- **(historical) Step:** **PLAN COMPLETE** — **Phase 12b (GELATO outbound: pick → pack → ship) planned 2026-07-18.**
  Closes the v3.0 DoD clause 2 (warehouse fulfillment outbound) and posts the sell-side **COGS** JE
  (Dr 5100 / Cr 1130) — the first half of SYERP-13's sell-side books; invoice-from-shipment + AR stay
  Phase 13. **15 tasks:** Wave A schema (Shipment + ShipmentLine models, `qty_picked`/`qty_shipped` on
  `crumb_sales_order_line`, migration **0016**, schemas) → Wave B backend (NEW SYERP bin-aware
  `post_issue` → GELATO `shipments.py` pick/pack/ship → router+boot) → Wave C verify
  (`verify_gelato_ship.py` incl. the accounting crux + control-vs-subledger tie + reservation-relief +
  partial-ship + the load-bearing Barrier; `verify_gelato_ship_api.py` HTTP RBAC/audit; full regression
  + TB-nets-zero) → Wave D frontend (shipment hooks, a Fulfillment pick→pack→ship screen, an SO-detail
  ship affordance, colocated Vitest asserting the real payload shape). Recurring keepers baked in: real
  router/UI payload shape in verify + Vitest (11a/11b/12a trap); the non-optional HTTP audit/RBAC script
  + `write_audit(target_id=str(shipment.id))` (12a int-PK bug — Shipment is int-PK); the pre-planned
  FOR-UPDATE lock + `asyncio.Barrier` two-concurrent-ship scenario; a control-account-ties-to-subledger
  assertion (not just TB nets zero — Phase 10 keeper). **Next action:** `/zj:build 12b`.

- **Branch (D-P12b-8):** build 12b on a fresh `feature-gelato-pick-pack-ship` cut off the verified 12a
  tip (tag `zj/good-12a-gelato-bins-putaway`, `52eb481`) — 11a/11b/12a unmerged; 12b stacks. Lint gates
  remain non-functional (BACKLOG p1); correctness rests on verify_* + Vitest, per project convention.

## (historical) Position

- **(historical) Step:** **RETRO'D** — **Phase 12a (GELATO bins & directed putaway) closed 2026-07-18** (`/zj:retro 12a`),
  tag `zj/good-12a-gelato-bins-putaway` at `52eb481`. Roadmap marked `[done — verified + retro'd]`. Retro banked
  **LEARNINGS Phase 12a**, five keepers: (1) **the headline lesson — adding a new dimension (`bin_id`) to a
  shared ledger silently corrupts it for every existing writer that ignores the dimension, and it's a
  SEQUENTIAL-correctness bug, not a race** (bin-blind `post_transfer`/`post_adjustment`/MOUSSE-issue leave the
  bin overstated + unbinned pool negative even single-threaded; the SC3 roll-up identity stays exact so every
  green assertion missed it — same shape as the 09c/10 zero-sum-identity blindness, now on a physical
  dimension); (2) **a value clamp that hides the symptom can break the invariant you just proved** — clamping
  `get_bin_on_hand` would have broken SC3, so the mitigation surfaced-and-pinned the boundary (scenario E)
  instead; (3) **the paired HTTP script earned its keep a 3rd suite running — GELATO's `Bin` is the first
  int-PK audited entity and its int→`VARCHAR(36)` `target_id` coercion bug 500'd the mutation after commit;
  keeper: `write_audit(target_id=...)` must `str()` the id** (reviewer confirmed no other int-PK target exists,
  so no repo sweep owed); (4) **concurrency pre-empted by design → clean review on that axis, the 9b rule
  paying off a 3rd time**; (5) **reverse-hub string table-name FK** avoids the import cycle when a hub-core
  table must reference a satellite table. Deferred items all homed: bin-split MAJOR → BACKLOG p2 (added at
  verify); int-PK audit sweep resolved (folded to LEARNINGS, no backlog entry); 422 sweep already BACKLOG p3.
  Artifacts: `.zj/phases/12a-gelato-bins-putaway/{PLAN,VERIFICATION,REVIEW}.md`, `.zj/LEARNINGS.md` Phase 12a.
  **Next action:** `/zj:plan 12b`. Optional: `/zj:log phase 12a` (formal work log); `/zj:ship` to merge the
  11a+11b+12a stack.

- **(historical) Step:** **BUILD COMPLETE** — **Phase 12a (GELATO bins & directed putaway) built 2026-07-17.**
  All **14 tasks** shipped on a fresh `feature-gelato-bins-putaway` branch (cut off HEAD `da9474e` = the
  verified 11b code tip + plan docs; see PLAN Deviations — bare tag `fec334f` would have dropped the plan).
  Delivered: `gelato` module self-registers (mirrors mousse/crumb new-module package shape); migration
  **0015** adds `gelato_bin` + nullable `bin_id` on `syerp_inventory_txn` (hub-inversion string FK,
  D-P12a-3), round-trips clean; `gelato:read`/`gelato:write` seeded; bin CRUD (unique-within-location,
  archive-hides) + directed putaway. The **SYERP-owned bin-aware primitive** `post_putaway`/`get_bin_on_hand`
  (D-P12a-7) clones `post_transfer` intra-location + bin-dimensioned, **locks `InventoryItem` FOR UPDATE
  before the floor read** (corrected from the plan's "InventoryTxn" prose — the append-only ledger isn't the
  contention point); GELATO's thin `service/` validates bins-belong-to-location then delegates. Router thin,
  RBAC-gated, audit-after-commit. **Proof:** `verify_gelato.py` (roll-up Decimal-exact + net-zero + floor +
  the **Barrier two-concurrent-putaway scenario, proven load-bearing** — lock removed → 2 successes → FAIL,
  restored → green) + `verify_gelato_api.py` (30 asserts, HTTP 401/403/200 + attributable audit) + all 17
  existing verify_* → **19/19 green**, Trial Balance `in_balance` True (12a posts **NO GL**); FE full suite
  **37 files/108 tests**, `npm run build` exit 0; nav gating data-driven (enabled ∩ `gelato:read`).
  **Two material findings, both handled:** (1) the paired HTTP script **caught a real router-audit bug** —
  bin routes passed integer `Bin.id` to `write_audit(target_id=...)` (VARCHAR col) → asyncpg `DataError`,
  bins committed then 500'd on the audit write (audit-trail violation); fixed `str(bin_.id)`, commit
  `136e98d` (the 9a/11a keeper recurring — GELATO's `Bin` is the **first int-PK audited entity**, worth a
  repo-wide `write_audit(target_id=)` sweep, logged under PLAN `## Noticed`); (2) the 11b dead-through-UI
  trap pre-empted — verify + the Putaway Vitest both assert the **real `PutawayRequest` payload shape**.
  **Next action:** `/zj:verify 12a`.

- **Branch (D-P12a-4, amended):** `feature-gelato-bins-putaway` off HEAD `da9474e` (code-identical to tag
  `zj/good-11b-crumb-sales-orders`/`fec334f`, docs on top). 11a/11b unmerged; 12a stacks. Checklist (all 14
  ticked): `docs/tasks/feature-gelato-bins-putaway.md`. Lint gates remain non-functional (BACKLOG p1) —
  correctness rests on verify_* (19/19) + Vitest (108), per project convention.

## (historical) Position

- **(historical) Step:** **PLAN COMPLETE** — **Phase 12a (GELATO bins & directed putaway) planned 2026-07-17.**
  Phase 12 (GELATO-01, 8 ACs) **split 12a/12b at plan** (D-P12a-1, owner — mirrors 9a/b/c + 11a/b):
  **12a** = bins CRUD + directed putaway (inbound foundation; covers GELATO-01 AC1/AC2 + the putaway
  portion of AC7/AC8; **NO GL, NO sales-order/reservation, NO pick/pack/ship**); **12b** = pick → pack
  → ship + reservation relief + COGS JE (the outbound + GL crux; AC3/4/5 + ship-side AC7/AC8). Three
  owner decisions set the shape: (1) **split 12a/12b, plan 12a now**; (2) **bin_id on the existing
  `syerp_inventory_txn` ledger** — one ledger, one bin dimension, roll-up to the location total
  guaranteed by construction (D-P12a-2); (3) **full staging-bin moves in 12b** (D-P12a-4, binds 12b).
  PLAN.md = **14 tasks** in 4 waves (models → migration 0015 [`gelato_bin` + `bin_id` col] → perms →
  schemas → SYERP `post_putaway`/`get_bin_on_hand` primitive → thin GELATO `service/` package → router
  + self-register → `verify_gelato.py` + `verify_gelato_api.py` → full regression → FE nav/Bins/Putaway/
  tests). Recurring keepers baked in: verify inputs built in the **real router/UI payload shape** (the
  11a/11b dead-through-UI trap), the non-optional **HTTP-level audit/RBAC** script, and a **load-bearing
  `asyncio.Barrier` concurrency** scenario on putaway-vs-putaway (FOR UPDATE, D-V3-18). Decisions
  D-P12a-1..9 recorded; no `## Decisions needed` open. Plan checked goal-backward at manager review
  (every SC → ≥1 task, every task → an SC, real files + runnable verify). **Next action:** `/zj:build 12a`.

- **Branch (D-P12a-5):** build 12a on a fresh `feature-gelato-bins-putaway` cut off the verified 11b
  tip (tag `zj/good-11b-crumb-sales-orders`, `fec334f`) — 11a/11b unmerged; 12a stacks. Lint gates
  remain non-functional (BACKLOG p1, known); correctness rests on the verify_* suite + Vitest.

- **(historical) Step:** **RETRO'D** — **Phase 11b (CRUMB sales orders + soft-reservation) closed 2026-07-17**,
  tag `zj/good-11b-crumb-sales-orders` (`fec334f`). **CRUMB-01 complete (all ACs).** Roadmap marked
  `[done — verified + retro'd]`. Retro banked three keepers (LEARNINGS Phase 11b): (1) **verify built
  its inputs in a shape the UI never sends** — `item_id=` hand-fed while the UI sends `plum_part_id`
  only — so 17/17 green certified a dead-through-UI headline feature; the 11a "green-but-broken"
  pattern recurred with a nameable mechanism (verify inputs must match the real router/UI contract);
  (2) **run verifier + reviewer in parallel and let a reviewer BLOCKER override a verifier PASS** — it
  has now caught the one defect that mattered on two consecutive phases; (3) **a multi-entry invariant
  needs one shared resolver wired into every door** (the `_resolve_and_validate_item_id` fix).
  Deferred items each have a home: quote→SO idempotency guard → BACKLOG p3; `plum_part_id` non-unique
  → accepted for single-shop; Closed-SO stale `qty_reserved` → cosmetic, recorded. **Next action:**
  `/zj:plan 12` (GELATO warehouse core — ship posts the COGS JE; realizes the D-P8-3 bin deferral).
  Optional: `/zj:log phase 11b` to file the formal work log; `/zj:ship` to merge the 11a+11b stack.

- **(historical) Step:** **BUILD COMPLETE** — **Phase 11b (CRUMB sales orders + soft-reservation) built 2026-07-17.**
  All **17 tasks** shipped on branch `feature-crumb-sales-orders` (cut off the verified 11a code tip
  `a8191cf`; tag `zj/good-11a-crumb-crm-pipeline` is docs-behind at `7c573d3`, code identical — see PLAN
  Deviations). CRUMB-01 completed (all ACs): SO models + migration 0014; direct SO CRUD + `SO-####`
  numeric-safe numbering + FSM (Draft→Confirmed→Fulfilling→Closed, +Cancelled from Draft/Confirmed);
  accepted-quote→SO conversion (item_id resolved from `plum_part_id`, free-text→NULL, source_quote/opp
  stamped); the **soft-reservation crux** — confirm reserves `min(qty_ordered, available)` with
  `available = get_item_on_hand − Σ open (confirmed/fulfilling) reservations ≥ 0`, `InventoryItem` rows
  `FOR UPDATE` locked in sorted-id order BEFORE the read (bills.py template), cancel releases; router
  audit + `crumb:read`/`crumb:write` RBAC; SO list/create/detail (ordered/reserved/shortage) + Convert-to-SO
  affordance. 11b posts **NO GL** (TB still nets zero). **Mandated Task-8 adversarial review → VERDICT
  PASS** (`REVIEW-task8.md`): invariant holds under concurrency; Medium finding (reservation not
  serialized vs raw stock write-offs) = **D-V3-18 by-design** (narrow lock; SYERP floor-guard deferred
  to Phase 12). **Proof:** backend `verify_crumb_so.py` (25 asserts incl. concurrency scenario F,
  mutation-tested load-bearing) + `verify_crumb_so_api.py` (40 asserts HTTP RBAC+audit) + all 15 existing
  verify_* → **17/17 green**; FE full suite **35 files/100 tests**; `npm run build` exit 0. **Next
  action:** `/zj:verify 11b`.

- **Branch (D-V3-19):** `feature-crumb-sales-orders` — 11a is unmerged; 11b stacks on it. Checklist
  (all ticked): `docs/tasks/feature-crumb-sales-orders.md`. Lint gates remain non-functional (BACKLOG
  p1, known) — correctness rests on the verify_* suite + Vitest, per project convention.

- **(historical) Step:** **RETRO'd** — **Phase 11a (CRUMB CRM & pipeline) verified + retro'd 2026-07-16.** Branch
  `feature-crumb-crm-pipeline` (cut off master `039c409`, D-V3-13), tip `efcf2e6`, tagged
  `zj/good-11a-crumb-crm-pipeline`. Retro (`/zj:retro 11a`) appended LEARNINGS Phase 11a
  (new-module-as-a-package from day one; mirror the newest exemplar; the two-tier verify pair earns
  SC6; **and the keeper — 20 green verify assertions missed a major defect that the code review
  caught**, so the adversarial review is not redundant with verify). Deferred items homed: the Task-2
  alembic unique-constraint drift and the 422 deprecation sweep were re-hit by crumb and noted on the
  existing p1/p3 BACKLOG entries (not duplicated); AC4 (sales orders + soft-reservation) +
  accepted-quote→SO conversion remain Phase 11b (D-V3-10). All 19 build tasks + the fix loop
  (`a697c69`, `efcf2e6`, 4 gaps) committed; VERIFICATION.md + REVIEW.md written. **Proof (post-fix):**
  `verify_crumb.py` **22/22** + `verify_crumb_api.py` **54/54** (SC6 HTTP RBAC+audit gate) + 13/13
  regression verify_* exit 0 + FE crumb Vitest 4/4 + `npm run build` exit 0. **Next action:**
  `/zj:plan 11b`. Phase 11
  (CRUMB-01, the largest single FR) was **split into 11a + 11b** at plan (D-V3-10): **11a** = the
  inventory-free CRM chain (leads → opportunities → quotes + communication log), **11b** = sales
  orders + accepted-quote→SO conversion + the soft-reservation crux. PLAN.md for 11a holds **19 tasks**
  in 5 waves (models → migration 0013 → perms → schemas → 4-entity `crumb/service/` package →
  router+register → `verify_crumb.py` + `verify_crumb_api.py` + regression → frontend nav/4 pages/tests).
  Every in-scope CRUMB-01 AC (1/2/3−/5/6/7) maps to a task; **AC4 (sales orders + reservation) is
  deferred to 11b**. Six decisions recorded (**D-V3-10..15**). Plan reviewed goal-backward; one
  architect error caught and fixed at manager check — the hub FK columns are `String(36)` (Partner/
  plum_part PKs are UUIDs, not int).

- **Project:** BizNiceSweets
- **Milestone:** **v3.0 Customer & logistics — CLOSED + tagged `v3.0`** 2026-07-19 (all phases verified +
  retro'd; DoD audited goal-backward, 2 gaps fixed at close; phases archived to `.zj/history/v3.0/`).
  **Next milestone = v4.0 Infra-debt + quality paydown (D-M3-3).** v2.0 + v1.0 closed + tagged.
- **Branch:** v4.0 Phase 2a **BUILD COMPLETE** on `chore-pytest-harness-repair` (off `93de57d`,
  code-identical to tag `zj/good-01-lint-gates-clean`/`dd401d1`). All 13 tasks committed, tree clean.
  Unmerged v4.0 stack (Phase 1 + 2a) ships at milestone close. The merged `feature-syerp-ar-invoicing`
  branch may be deleted.
- **Last update:** 2026-07-22
- **Next action:** **`/zj:retro 2a`** (bank the fix-loop learnings) or **`/zj:plan 2b`** (port the
  `verify_*` cruxes). Phase 2a is **verified — Verdict PASS**, tag `zj/good-02a-pytest-harness-repair`.
  (Historical verify target, now satisfied:) verify v4.0 Phase 2a goal-backward against the 6 SCs:
  SC1 DSN probe connects (`afa5798`); SC2 no InterfaceError, one loop-safe NullPool engine shared by
  direct-session fixtures AND the ASGI `client` (`6ad45c9`); SC3 token identities resolve (admin-user +
  D-P2a-5 roster, `871998c`/`592faac`); SC4 back-to-back reruns, 0 IntegrityError (truncate-reset);
  SC5 **217 passed / 0 failed / 0 skipped** + non-vacuity proven (Task 10); SC6 env-pointable, no
  hard-coded host (Task 11). Regression: cold boot `BOOT_OK` + **23/23 `verify_*`** + ruff exit 0.
  D-P2a-5 recorded (RBAC test-identity roster). **Watch at verify:** container dev-deps are ephemeral
  (Phase-3 test-image bake); `_isolate` reseeds auth+roster only (GL tests self-seed COA); all 32
  first-run failures were TEST drift (no product code touched) — confirm none masks a real bug.
  Porting `verify_*` cruxes stays **2b**.

## Next action (detail)

**`/zj:plan 13`** — SYERP-13 AR + invoicing from the shipment/SO — the last v3.0 clause. **Alternative —
pay down infra debt first:** the BACKLOG **p1** items (CI, live-DB pytest harness repair, both lint gates)
are now two milestones old; a debt-paydown phase is reasonable if the owner wants it (raise at `/zj:ideate`).
Also standing: the pick-path shipment-header races (BACKLOG p2, Q1/Q2) and the inbound half of the
bin-blind-desync item (p2) — weigh the shared cross-path row-lock refactor when a multi-writer deploy nears.

### (historical) Phase 11b verify target
**`/zj:verify 11b`** verified goal-backward against the 6 SCs: SO model/migration/wiring (SC1); direct
CRUD + FSM (SC2); accepted-quote→SO conversion (SC3); the soft-reservation invariant incl. the
concurrency crux (SC4 — re-run `verify_crumb_so.py` scenario F, it is mutation-tested load-bearing);
router audit + RBAC at HTTP level (SC5 — `verify_crumb_so_api.py`); FE + regression 17/17 + TB nets zero
(SC6). Deviations to review: SO list omits a cosmetic "total" column (header schema has no `total_value`);
branch cut off `a8191cf` not the bare tag (code-identical). Noticed follow-ups (all deferred, non-blocking):
Closed-SO stale `qty_reserved` (cosmetic), item→InventoryItem ambiguity (single-shop OK), 422 deprecation
sweep (BACKLOG p3).

### (historical) Phase 11a build — CRUMB-01 inventory-free portion
**`/zj:build 11a`** built a new `crumb` module (mirrors the
MOUSSE new-module pattern, D-P10-6) with a `crumb/service/` package split by entity, leads →
opportunities (stage FSM) → quotes (PLUM-derived 30% markup default, `QUOTE-####` numeric-safe, Draft
→Sent→Accepted/Rejected/Expired FSM), and an append-only customer communication log. Server-enforced
FSMs, audit at the router layer, `crumb:read`/`crumb:write` RBAC. Proven by `verify_crumb.py` (service)
+ `verify_crumb_api.py` (HTTP RBAC + audit) + FE Vitest/build; the 13 existing `verify_*` stay green.

**Before building:** fast-forward `chore-spec-v3-customer-logistics` → `master`, then cut
`feature-crumb-crm-pipeline` off master (D-V3-13).

**After 11a verifies:** `/zj:plan 11b` — sales orders + the soft-reservation crux (`qty_reserved`
accumulator on the SO line, D-V3-11; `available = on-hand − Σ reserved ≥ 0`, D-V3-8) + accepted-quote
→SO conversion. Then Phase 12 (GELATO ship, posts COGS JE) → Phase 13 (SYERP-13 AR). The DoD, not the
phase count, is the contract.

**Alternative — pay down infra debt first:** the BACKLOG **p1** items (CI pipeline, live-DB pytest
harness repair, both lint gates) are now two milestones old. A debt-paydown phase is reasonable if the
owner wants it (raise at `/zj:ideate`).

## Deferred at the v2.0 close (owner-approved — do not lose)

- **Human click-through UAT** (`.zj/UAT-v2.0.md` 14 checks + owed v1.0 round-2) → BACKLOG **p1**
  pre-public-release gate (D-M2-2). Tag rests on backend live-proof + the wired-UI audit; extend the
  checklist with GL/AP/reports/MOUSSE UI flows before running it.
- **BACKLOG p1 infra debt** — no CI, live-DB pytest harness broken (100 skips, D-P7-4), both lint
  gates non-functional. Correctness rests on `verify_*` + Vitest. Carried into v3.0.
- **`/zj:ship` master-merge** (D-M2-3) — **RESOLVED 2026-07-16** (PR #2, fast-forward to `35f9b66`).

## Standing context

- **Stack for verification:** `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`;
  run verify scripts in-container: `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/<name>.py`.
  Vite dev server for UI/UAT at `http://localhost:5173`.
- **v2.0 tag placement (D-M2-3, mirrors D-M1-1):** the `v2.0` tag (`d6c91cb`) was applied on the
  then-unmerged branch tip; the fast-forward ship (PR #2) preserved the SHA and it is now reachable
  from `master`. Debt cleared.
- **Adoption note:** adopted from GSD 2026-07-04; prior systems archived under `archive/`. `.zj/` is
  self-contained.
