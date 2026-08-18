# Verification: Phase 05 — Human click-through UAT (NFR-8)
Date: 2026-08-17 | Commits: `4171605..d3e68e2` (70 commits: 55 build + 15 fix-loop)
Verdict: PASS — 0 blocker, 0 major, 6 minor

**Re-verification pass.** The first pass (at `1954b56`) returned GAPS FOUND — 5 major, 5 minor.
The owner ran the full fix loop; the tip moved to `d3e68e2`. This document is a complete
rewrite of the verdict against the tree as it stands. **All ten gaps I raised are closed**,
and I re-drove the evidence myself rather than reading the engineers' reports. Six new minor
findings came out of the re-check — none of them blocking, all named below.

Two corrections to my own first pass are folded in: the manifest has **46** fixture keys, not
47 (I double-counted a table header), and G-5's code sites were `inventory.py:618-621` /
`mousse/service.py:607-610`, not the `:826-827` / `:998-999` I cited. The engineers caught both.

---

## Judgment on the D-P5-11 rescope (unchanged, and now tidier)

**The amendment remains legitimately recorded, not a quiet redefinition.** Every test it passed
in the first pass it still passes, and the one residue I flagged has been fixed: **SC9's text
now reads "the p1 BACKLOG UAT item **deliberately left open** and re-pointed"**, with the
struck original and its reasoning preserved in parentheses (`PLAN.md:37`, `d3e68e2`). The
criterion no longer contradicts Task 38's behaviour.

| Test of legitimacy | Result |
|---|---|
| Owner-attributed decision exists | ✅ `.zj/DECISIONS.md:1200` — "D-P5-11 … (owner, 2026-08-17, driven by the new `QA docs: non-blocking` preference)" |
| Names the decisions it supersedes | ✅ supersedes D-P5-6 and D-P5-7's status-table clause, both named |
| Original SC wording preserved | ✅ SC1, SC4, SC6, SC7 **and now SC9** each carry the struck original with its reason |
| The cost is stated, not buried | ✅ "**Consciously accepted cost:** NFR-8 is now satisfiable by a checklist nobody has run" |
| Downstream docs repeat the limitation | ✅ SRD NFR-8 "NOT evidenced" bullet; ROADMAP "NOT delivered, by design"; `requirements-progress.md` status cell; BACKLOG p1 item deliberately open |
| The honest caveats it promised to keep were kept | ✅ `.zj/SRD.md:164`, `:195` still read "UI flow still UAT-pending, so status stays `partial`" |

**What is and is not evidenced, precisely.** Unchanged from the first pass, and now stronger on
the "runnable" half: 61 human checks exist, are judgeable, quote literals a reproducible seed
actually produces, and cite machine assertions that exist and assert what is claimed. The prod
artifact they target is up, at HEAD, and healthy. **Not evidenced: that any human has exercised
any UI flow.** `.zj/QA.md` §6 holds zero readings, and NFR-8 as re-worded does not claim
otherwise. A `/zj:milestone` reader should read NFR-8's "NOT evidenced" bullet before deciding
whether v4.0 ships.

---

## Criteria

### SC1 — one consolidated, requirement-keyed checklist — **PASS** *(now machine-pinned)*

| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `.zj/QA.md` is the single standing checklist | ✅ | ✅ | ✅ | 1,772 lines at `d3e68e2` |
| Exactly **61** numbered checks | ✅ | ✅ | ✅ | Re-counted: 61 `#### C-…` headings, 61 unique `C-*` IDs |
| Each check carries fixture / cited proof / residue / recordable result | ✅ | ✅ | ✅ | `verify_qa_citations.py` now asserts **every check owns exactly one `✅ Machine already proved` block** — 61 blocks for 61 checks; I re-sampled `C-SC6-a/b/c/d`, `C-CORE-07/08/09`, `C-PLUM-07`, `C-SYERP-14`, `C-CRUMB-02` by hand |
| Coverage map is arithmetically true | ✅ | ✅ | ✅ | **`backend/scripts/verify_qa_doc.py` — 15 assertions, all PASS**, run by me on the host: 47 requirements in SRD, 31 covered by 31 §4 sections, 16 across 4 §5 buckets. Both-direction set equality asserted |
| Numbering is navigable | ✅ | ✅ | ✅ | `4.1`–`4.7` suite banners now sit inside `## 4`, with a new `4.1 CORE`; `## 5` / `## 6` / `## 7` no longer collide. I grepped every `§n` reference in the file — `§1`, `§2`, `§4.7`, `§5` — **all four resolve** |
| `UAT-v1.0/v2.0/v4.0` pointer lines | ✅ | ✅ | ✅ | all three carry `> **Superseded for execution by [.zj/QA.md](QA.md)**` |

### SC2 — fixtures, idempotent on a fresh volume — **PASS** *(now CI-pinned, and now guarded)*

| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Second run changes nothing (manifest) | ✅ | ✅ | ✅ | **Re-driven on a genuinely fresh DB** (`uatverify`, created + migrated + app-seeded by me): two full seeds → manifests **byte-identical, 361 lines** |
| Second run writes no rows at all (census) | ✅ | ✅ | ✅ | **47-table whole-database census identical** across the two runs — the check that catches an audit row per run, which the manifest alone cannot see |
| Same, in CI, on CI's own fresh Postgres | ✅ | ✅ | ✅ | CI run `32072598536` job `verify-scripts`: `manifest byte-identical across two runs on a fresh database`, `361 manifest-1.txt`, `47 census-1.txt` |
| The seed cannot land on real books — gate 1 (stack opt-in) | ✅ | ✅ | ✅ | **Driven three ways.** Isolated DB without `BNS_ALLOW_UAT_SEED` → **exit 3**, `REFUSED: the target stack is not a UAT stack.`, **zero rows written** (partners/parts/users/JEs all `0`). **On the owner's real prod stack** → same, exit 3. With `-e BNS_ALLOW_UAT_SEED=1` (the documented `C-CORE-08` path) → exit 0 |
| gate 2 (foreign ledger) | ✅ | ✅ | ✅ | Ran `verify_purchasing.py` against the isolated DB (it leaks orphan JEs), then re-seeded → **exit 3**, `REFUSED: this database already holds 2 journal entries this script did not post.`, naming both `po_receipt` rows, **stdout empty** |
| `--manifest` exempt from both gates | ✅ | ✅ | ✅ | Ran with `env -u BNS_ALLOW_UAT_SEED` → exit 0, output byte-identical to the seeding run's manifest. Also works on the prod stack with no override |
| **The actor clause is load-bearing** *(asked for)* | — | — | ✅ | **Confirmed independently.** The seeded ledger holds **8** journal entries, **all** carrying `actor_id = 00000000-…-05a7` (`SEED_ACTOR_ID`), and **only 2** carry a `UAT-` memo (`UAT-JE-0`, `UAT-JE-1`). The other six are service-generated: `AR invoice INV-0001`, `Shipment 1 — SO SO-0002 COGS`, `AP payment <uuid>`, `PO receipt <uuid>`, `AP bill BILL-0001`, `AR receipt <uuid>`. A prefix-only predicate would read all six as foreign and refuse every second run — **breaking the idempotency contract SC2 rests on**. The predicate is `actor_id IS DISTINCT FROM :actor AND memo NOT LIKE 'UAT-%'`, i.e. foreign ⇔ neither test passes. Correct, and the second seed demonstrably succeeds |
| The gate did not break the owner's fixtures | — | — | ✅ | Owner's manifest **byte-identical** to my pre-fix-loop reading, before and after an override re-seed |
| Literals still match the manifest | ✅ | ✅ | ✅ | Re-spot-checked ~25 across suites, all exact (`99.15`, `-59.66`, flat `UAT-P102` qty `11`, `6.669231`, `86.700003`, `57.75`/`264.5`, `139.5`/`84.25`, TB `8447.25`, BS `7991.75 = 57.75 + 7934`, `324.51`, `6.15`) |
| Manifest shape | — | — | ✅ | 23 table rows + **46** fixture keys + **275** derived literals = 361 lines. *(My first pass said 47 fixture keys — I had counted the `\| category \| key \|` header row. The engineers' 46 is correct.)* |

### SC3 — machine pre-flight map — **PASS** *(now CI-pinned)*

| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `PREFLIGHT.md` maps each check or marks it `machine-unproven` | ✅ | ✅ | ✅ | unchanged, 218 lines |
| Citations resolve | ✅ | ✅ | ✅ | **`backend/scripts/verify_qa_citations.py`, run by me: 224 citations across 61 blocks — 11 file, 21 pytest test, 47 scenario, 145 title — all resolving.** Plus my first pass's 20 hand-sampled citations, all of which also resolve |
| Citations assert what is claimed | ✅ | ✅ | ✅ | first pass read 3 bodies in full (BomTree footer, AppShell wildcard, `verify_mousse.py (G)`); all genuine |
| The pin is not vacuous | ✅ | ✅ | ⚠️ | **Two RED drives, both for the intended reason.** (a) I broke a citation *in `.zj/QA.md`* → `FAIL: every citation resolves inside the file it names`. (b) I renamed the test title *in the test file* — the realistic rot direction — → same FAIL, naming the file and the missing title exactly. **But a third probe found a hole:** stripping the quotes off a citation makes it a silently-"skipped span" and the run still exits 0. See finding **N-2** |
| Scope: `.zj/QA.md` only, not `PREFLIGHT.md` | — | — | ✅ | **Right call.** `PREFLIGHT.md` is a phase-local historical artifact superseded by `.zj/QA.md`; the standing document is the one whose citations must not rot. That is why the count is 224, not my ~309 |

### SC4 — every check judgeable; §6 records readings — **PASS**

Unchanged from the first pass and re-sampled after the renumbering. `C-SC6-a` now additionally
records the two server-side rejections behind the picker with their verbatim 422 texts.
`C-SC6-d` still opens "⚠ This check is an OBSERVATION, not a confirmation. Do not try to make
it pass." §6 remains a usable 5-column log with **zero readings** — which amended SC4 permits.

### SC5 — every defect fixed with a revert-failing pin — **PASS**

All three pins were driven RED-on-revert in the first pass (U0: 3 of 4 fail; U1: behavioural
RED with the exact `ix_users_email` `UniqueViolationError`; U2: `Containerfile never COPYs
frontend/.npmrc`). All three re-run green at HEAD inside the 245-test suite. The **U1 live
re-drive** on the prod artifact still returns **409** `"User 'admin@example.com' already
exists."` with the user list unchanged.

`.zj/QA.md` §7 now carries **U2's SHAs** — `8d61cca` (Containerfile) and `f82ec38`
(`test_containerfile_config.py`) — so the "All fix/pin SHAs verified resolvable" footnote is
true of all three rows.

### SC6 — the three Phase-4 bin pickers, incl. GELATO-off — **PASS**

All four checks present, correctly keyed, and their zero-vs-nonzero pool contrasts re-confirmed
against the live manifest. `C-SC6-a` (`4.3 SYERP` → SYERP-10), `C-SC6-b` (SYERP-10), `C-SC6-c`
(`4.4 MOUSSE` → MOUSSE-01), `C-SC6-d` (CORE-07). The renumbering did not orphan any of them —
`verify_qa_doc.py` asserts every §3-covered requirement owns a §4 section, and passes.

### SC7 — prod stack healthy at :8000 on a fresh volume — **PASS** *(re-established at HEAD)*

⚠️ **I found the artifact stale and fixed it.** The image serving `:8000` was built at 15:24,
i.e. **before `fd7ca87`** — a `backend/app/` change. The PLAN's own Risk says "any commit
touching `backend/app/` or `frontend/src/` after Task 34 → re-run 34–36", and the fix loop did
not. I verified the running container lacked the archived-bin branch (`grep -c "is archived"` →
`0`), then rebuilt and redeployed. Recorded as finding **N-6**. Re-driven afterwards:

| Truth | Result |
|---|---|
| Image builds clean at HEAD | `podman build` exit 0; **grepped the log for `Error: building at STEP` / `failed to solve` / `npm error` — none** (never trusting exit status, per U2) |
| Redeploy preserves the volume | `podman-compose -f compose/compose.yml up -d --force-recreate`; `compose_pgdata` untouched |
| Container is at HEAD | `grep -c "is archived; a binned"` inside the container → `1` |
| `/health/ready` | `{"status":"ok","db":"connected"}` |
| `alembic current` | **`0017 (head)`** |
| SPA at `/` | **200**, references `/assets/index-BQmUVhcG.js` |
| Bundle byte-identical to host dist | sha256 `2eac7014…` both sides; a fresh `npm run build` reproduces the same hash (no `frontend/src` change in the fix loop) |
| Admin login on the shipped artifact | 200, 411-char access token |
| Authed read | `/plum/parts` → 15 UAT parts; fixtures survived the redeploy |
| Fixtures still pristine | `--manifest` **byte-identical** to the pre-fix-loop reading |
| Human smoke (one write per suite) | **Not performed** — a parallel to-do per amended SC7, authored as `C-CORE-08` |

### SC8 — `post_adjustment` rejects a bin that doesn't exist, doesn't belong, or is archived — **PASS** *(widened)*

| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Raw-SQL probe, widened to `SELECT active` | ✅ | ✅ | ✅ | `inventory.py:441-472` — `text("SELECT active FROM gelato_bin WHERE id = :bin_id AND location_id = :location_id")`, branching `bin_row is None` → "does not exist at location", `not bin_row[0]` → "is archived" |
| **Still no gelato model import** (D-P12a-3) | ✅ | — | ✅ | re-grepped after `fd7ca87`: imports are `fastapi`, `sqlalchemy`, `app.modules.syerp.service.{_common,items,locations}` only; `grep -n gelato` returns comments and the raw table name |
| Runs before any write | ✅ | ✅ | ✅ | after `get_item`/`get_location`, before the `FOR UPDATE` lock |
| Foreign-location bin → 422 | ✅ | ✅ | ✅ | **live on the HEAD prod artifact:** `"Bin 1 does not exist at location 4; a binned adjustment must name a bin belonging to that location."` HTTP 422 |
| Archived bin at its own location → 422 | ✅ | ✅ | ✅ | **live:** `bin_id: 3` (`UAT-BIN-A3`, `active: false`, location 2) at location 2 → `"Bin 3 is archived; a binned adjustment must name an active bin."` HTTP 422 |
| Nothing persisted by either | ✅ | ✅ | ✅ | `/onhand` after both: total still `19.000000`, LOC-A `15`, NOBIN `4` |
| `bin_id = None` genuinely untouched *(asked for)* | ✅ | ✅ | ✅ | Code path skips the probe entirely when `bin_id is None`; **and scenario (G4) asserts it live** — "bin_id=None is UNTOUCHED by the membership probe … still posts, raising that pool by exactly 3". D-P4-1 and the SC6 zero-pool fixtures are safe |
| Pinned by scenario (G5), RED on revert *(asked for)* | ✅ | ✅ | ✅ | **I reverted `fd7ca87`'s `inventory.py` hunk and re-ran `verify_gelato.py`: G5 FAILED with `status=None rows 3->4`** — no exception raised at all, ledger row appended. Exactly the claimed signature. **G1–G4 all still PASS in the same run**, so the RED is attributable to the archived-bin branch alone and no other guard hijacked it. Restored → exit 0 |

### SC9 — bookkeeping — **PASS** *(criterion text now consistent)*

SRD NFR-8 stamped with the corrected evidence numbers; module rows keep "UI-flow UAT-pending";
`requirements-progress.md` row present; ROADMAP row records the rescope and the corrected CI
citation; D-P5-1..11 present; p1 BACKLOG UAT item deliberately open and re-pointed; archived
task checklist in place. **SC9's own wording amended (`d3e68e2`)** so it no longer demands the
tick that D-P5-11 declines to make.

---

## Every first-pass gap, re-checked

| Gap | Claimed fix | My verdict |
|---|---|---|
| **G-1** major — coverage arithmetic unpinned | `ba4c074` `verify_qa_doc.py` | **CLOSED.** 15 assertions, exit 0. **RED-driven twice by me:** injecting a bogus `CORE-99` row fired **six** independent assertions with precise messages; renaming a §4 heading fired two. Non-vacuous |
| **G-2** major — fresh-volume idempotency unpinned | `3a0d386` two steps in `verify-scripts` on its own `uatseed` DB | **CLOSED.** Re-driven locally (manifest + 47-table census identical on a fresh DB) and confirmed green in CI run `32072598536`. Putting it in the existing job rather than a new one is the right call — `verify-scripts` is already a required context, so it gates now |
| **G-3** major — citations never re-grepped | `8352858` `verify_qa_citations.py` | **CLOSED**, with a caveat. 224 citations resolve; two RED drives fire for the intended reason. See **N-2** for the vacuity edge and **N-3** for the 3 WEAK advisories |
| **G-4** major — nothing in CI builds the image | `b72efc5` `container-image` job | **CLOSED.** **Green on a real runner for the first time** — CI `32072598536`, job `container-image`, 37 s. I read the log: it really built (`COPY frontend/package*.json frontend/.npmrc ./`, `RUN npm ci`, `RUN npm run build`, 24 steps, layers exported, image written), then grepped for `Error: building at STEP` / `failed to solve` **and** positively asserted `docker image inspect` succeeds. Not vacuous. Caveat: **not a required status context** (needs a repo-settings change), so it can be merged past |
| **G-5** major — promised p2 backlog item never filed | `bf0bb0b` | **CLOSED.** Item filed under p2 with the **correct** sites — I verified `inventory.py:618-621` is `post_transfer`'s "The BIN is NOT validated here…" and `mousse/service.py:607-610` is `issue_components`'. **My original line numbers were wrong** (`:826-827`/`:998-999` are `post_putaway`/`post_issue`). One sub-claim in the new item does not hold — see **N-4** |
| **G-6** minor — stale contradictory blockquote | `4a62889` | **CLOSED.** Reduced to `> CORE-07 (module enable/disable) has no check of its own — it is exercised through C-SC6-d's module toggle.` The CORE-09-as-audit-trail error, the §3/§5 contradiction and the dangling §1.1 are all gone |
| **G-7** minor — scrambled section numbering | `4a62889` | **CLOSED.** `4.1`–`4.7` under `## 4`, new `4.1 CORE` banner, §5/§6/§7 unambiguous. **No dangling cross-reference** — all four `§n` references in the file resolve, and `verify_qa_doc.py` (which requires `## 3` / `## 4. The checks` / `## 5` verbatim) passes |
| **G-8** minor — U2 ledger row missing SHAs | `4a62889` | **CLOSED.** Row now reads `8d61cca (Containerfile …); pinned by backend/tests/test_containerfile_config.py (f82ec38)` |
| **G-9** minor — "129 literals" | `dacd19f` | **CLOSED** in the five live docs (SRD, ROADMAP, requirements-progress, STATE — the sixth site they found — and the paired "125"→271). I re-counted from the live manifest: **275** derived literals, confirmed. One historical instance remains — see **N-5** |
| **G-10** minor — stale CI citation + pre-U0 env contract | `dacd19f`, `aa8749b`, `50e14b5` | **CLOSED.** SRD/ROADMAP/requirements-progress/STATE now cite `32064085911` @ `1954b56` and explain why `32059723558` does not cover U2. `CLAUDE.md:80,190,191` and `MAP.md:67,68,79` describe the `.env` + `.env.db` split and name `scripts/uat.sh`. Two MAP.md lines still lag — see **N-5** |

---

## Regression protection

| Criterion | Pinned by | Class |
|---|---|---|
| **SC1** — coverage arithmetic, 61 checks, one proof block each | `backend/scripts/verify_qa_doc.py` (15 assertions) + `verify_qa_citations.py`'s one-block-per-check assertion — both auto-globbed by CI `verify-scripts`, a **required** context. RED-driven by me | **pinned** |
| **SC2** — seed idempotency on a fresh volume | CI `verify-scripts` → isolated `uatseed` DB, two seeds, **manifest diff + 47-table census diff**. Plus `test_compose_config.py`'s two opt-in assertions (prod never sets `BNS_ALLOW_UAT_SEED`, dev sets `"1"`) | **pinned** |
| **SC3** — citations resolve | `backend/scripts/verify_qa_citations.py`, 224 citations, CI-globbed. RED-driven both directions | **pinned** (see N-2 for the erosion edge) |
| **SC4** — checks judgeable | editorial judgment; the checks live in `.zj/QA.md` §4 where a tester finds them | manual |
| **SC5** — defects fixed and pinned | `test_compose_config.py` (U0), `tests/auth/test_user_duplicate_email.py` (U1), `test_containerfile_config.py` (U2) — CI `backend-tests`; all three RED-driven | **pinned** |
| **SC6** — bin-picker checks authored | manual: `C-SC6-a/b/c/d` in `.zj/QA.md`. Behaviour pinned by three colocated vitests + `verify_gelato.py (E)(F)(F2)(F3)(G1–G5)` + `verify_mousse.py (G)` | manual + pinned behaviour |
| **SC7** — prod stack up on a fresh volume | `container-image` CI job (real `docker build` + failure-string grep) — **new, green on a runner**; plus `test_compose_config.py` (U0 env split) and `test_containerfile_config.py` (U2 `.npmrc`). The full `compose up` on a fresh volume is still hand-driven | **pinned (build) + observed (deploy)** |
| **SC8** — bin existence + membership + **active** | `verify_gelato.py` scenarios **(G1)–(G5)**, CI-globbed; (G5) RED-driven by me | **pinned** |
| **SC9** — bookkeeping | doc review | observed |

Four of the five criteria that were `observed`/`MISSING` at the first pass are now genuinely
`pinned`, and each pin was proven non-vacuous by mutation rather than accepted on its exit code.

---

## Test suite

Every gate re-run by me at `d3e68e2`.

| Gate | Command | Result |
|---|---|---|
| Backend tests | `backend/.venv/bin/python -m pytest -q` (host venv → throwaway `postgres:17-alpine` on `:55433`) | **245 passed, 0 skipped**, 210.93 s — matches the claim (243 → 245 from the two new compose assertions) |
| Backend lint | `backend/.venv/bin/ruff check .` | `All checks passed!`, exit 0 |
| Frontend lint | `npm run lint` | exit 0 |
| Frontend tests | `npm run test` | **45 files / 148 tests passed** |
| Frontend build | `npm run build` | exit 0; reproduces `index-BQmUVhcG.js` / `index-BM4CDVzX.css` |
| `verify_*` non-API | 17 scripts | **17/17 exit 0** — but only when run from a repo checkout; **15/17 in-container**, see **N-1** |
| `verify_*` API | 9 `*_api.py`, against an isolated HEAD API container on its own DB | **9/9 exit 0** (26/26 total) |
| Container image | `podman build -f Containerfile .` | exit 0, log grepped clean |
| CI at HEAD | `gh run view 32072598536` @ `d3e68e2` | **success — 5/5 jobs**: `backend-lint`, `frontend`, `verify-scripts`, `backend-tests`, and the new **`container-image`** |

**One self-inflicted artifact, corrected:** my first pytest attempt reported `5 failed, 215
passed, 25 errors`. That was my own doing — I had two pytest processes sharing one
`TEST_POSTGRES_DB`. Re-run serially on a dedicated database it is a clean **245 / 0 skipped**.
Recorded so nobody mistakes it for a regression.

All throwaway containers and databases (`verif_pg`, `verif_seed`, `verif_api2`, `uatverify`,
`verifydb2`, `verif_head_api:latest`) were removed. The owner's stack is up, healthy, at HEAD,
with fixtures byte-identical to before this verification.

---

## New findings (all minor; none blocking)

### N-1 · minor · the two new QA scripts fail when run the project's documented in-container way
`verify_qa_doc.py` and `verify_qa_citations.py` resolve `.zj/QA.md` / `.zj/SRD.md` from
`Path(__file__).resolve().parents[2]`. Inside the api image the repo root is `/app` and `.zj/`
is not present (the Containerfile copies only `backend/` and `frontend/`), so both die with an
unhandled `FileNotFoundError: '/.zj/QA.md'`. PLAN `## Context` documents
`podman exec -e PYTHONPATH=/app compose_api_1 python scripts/<name>.py` as *the* in-container
script recipe, and the project has reported "N/N verify_* exit 0" from exactly that command for
five phases. It is now **15/17 in-container, 17/17 on a checkout**. CI is unaffected (it runs on
a checkout), so the pins still gate — this is an ergonomics and honest-count problem, not a
coverage one.
**Fix:** guard both scripts — if the `.zj` path is absent, print `SKIP: verify_qa_*.py needs a
repository checkout (.zj/ is not in the runtime image); run it from backend/ on the host` and
exit 0 — and add a line to the PLAN/QA recipe noting the two doc scripts are host-only.

### N-2 · minor · `verify_qa_citations.py` can erode silently
The extractor classifies each code span in a `✅` block against a set of citation forms; a span
matching none is recorded as a "skipped span" and the run still exits 0. I removed the quotes
from one citation: the checked-citation count dropped from 224 to 223, skipped rose 23 → 25, and
the script printed **`All assertions PASSED`**. So a reformat that changes a citation's *shape*
(rather than its target) silently drops it out of the pinned set. The dominant rot mode — a
renamed test — is caught, which is what G-3 asked for; but the pin's own coverage can shrink
unobserved.
**Fix:** assert a floor on the citation count (e.g. `>= 220`, updated deliberately), or fail on
any skipped span inside a `✅` block that contains a `.py`/`.tsx`/`.ts` path or a quoted phrase.

### N-3 · minor · three citations are only weakly pinned
`verify_qa_citations.py` reports `WEAK (advisory, not a failure)` for `verify_gl.py (A)`, `(B)`
and `(M1)` (`.zj/QA.md:1225`) — they match mid-line, but `verify_gl.py` declares no scenario
markers. This is precisely PLAN `## Noticed` #9(a): six `verify_*` scripts use `check()`-label
substrings instead of scenario letters, so their citations "break silently if anyone reformats a
label". The advisory makes the weakness visible, which is an improvement, but the hardening
(give those scripts scenario letters) is still not done.
**Fix:** give `verify_gl.py` scenario letters, or downgrade those three citations to the
`path "label"` form the script can verify strictly.

### N-4 · minor · one sub-claim in the new p2 backlog item does not hold
`bf0bb0b` states that `issue_components`' "`post_issue` primitive repeats it at
`inventory.py:1019-1022`, where 'checked by the caller' is simply false for the MOUSSE caller."
**MOUSSE never calls `post_issue`.** `grep -rn "post_issue(" backend/app` returns exactly one
call site — `gelato/service/shipments.py:630` — and `mousse/service.py` imports only
`_COST_QUANTUM`, `_adjustment_violates_floor`, `_gl_account_id_by_code`, `get_bin_on_hand`,
`post_journal_entry`, then writes its `InventoryTxn` itself at `:764`. `post_issue`'s
"checked by the caller" claim is therefore about GELATO, its sole caller, and may well be true.
The item's two **primary** sites are correct and I verified both; only this tertiary sentence is
wrong, and it would send a future implementer to the wrong file.
**Fix:** drop the `post_issue` clause, or re-scope it to "GELATO's ship path" and verify
separately whether that caller does validate.

### N-5 · minor · residual stale lines the sweep missed
- `.zj/codebase/MAP.md:50` still lists only `scripts/uat.ps1` in the tree ("one-command
  dev-stack launcher (PowerShell)") with no `uat.sh`, and `:127` Concern 6 still asserts "the
  **only** stack launcher is PowerShell (`scripts/uat.ps1`); requires `pwsh`" — false since
  `565588a`. `:69` still cites `scripts/uat.ps1:58` for the dev-stack command. The load-bearing
  env-contract lines (`:67`, `:68`, `:79`) *were* fixed. MAP.md's broader refresh is already
  BACKLOG p3.
- `.zj/phases/05-human-uat/PLAN.md:482` (Task 35's `Done` note) still reads "all **129**
  literals byte-identical to the Task-8 record". The engineers deliberately left historical
  build records alone, which is defensible for the archived task file — but PLAN.md is the
  phase's live plan and is read by `/zj:*` tooling.
**Fix:** three MAP.md lines and one PLAN.md number.

### N-6 · minor · the prod artifact was stale again — found and closed during this verification
`fd7ca87` changed `backend/app/modules/syerp/service/inventory.py` **after** Tasks 34–35 built
and deployed the image. The PLAN's own Risk register says "any commit touching `backend/app/` or
`frontend/src/` after Task 34 → re-run 34–36 … exactly the v1.0 G2 failure", and the fix loop
did not. I confirmed the running container lacked the fix (`grep -c "is archived" → 0`), rebuilt
from HEAD, redeployed onto the same volume, and re-drove SC7 — so **the artifact is correct
now**. Recorded because the rule was missed, not because the state is wrong.
**Fix:** none needed today. Whoever lands the next `backend/app/` or `frontend/src/` commit on
this branch must re-run Tasks 34–35 before SC7 can be claimed again. Worth considering a
`C-CORE-08` precondition line saying "the image must be newer than the last product commit."

---

## QA checklist deliverable

Per this project's convention there is **no per-phase QA file**; `.zj/QA.md` is itself the
artifact under verification. I have **not** written a new QA file. Re-audit at `d3e68e2`:

- **Reflects the phase as shipped?** **Yes, now.** The gap I named in the first pass is closed:
  `C-SC6-a` records both server-side rejections with their verbatim 422 texts — `"Bin N does
  not exist at location M…"` and `"Bin N is archived; a binned adjustment must name an active
  bin."` — and the no-ledger-write oracle. I confirmed both strings live against the HEAD
  artifact. §1 now warns that `uat.sh` brings up the dev overlay, so `C-CORE-08` needs
  `compose.yml` alone, and documents the `BNS_ALLOW_UAT_SEED` opt-in with the per-run override
  for the prod-artifact path.
- **Coverage map (§5) tells the truth?** Yes, and it is now machine-asserted every CI run.
  The contradictory blockquote is gone.
- **§6 usable as a result log?** Yes. Still empty, which D-P5-11 permits.
- **§7 holds all three defects linked to fix commits?** **Yes — all three now carry SHAs.**
- **Every `manual` criterion's check actually lives in `.zj/QA.md`?** Yes: SC4's judgeability
  and SC6's four bin-picker checks are all in §4 under `4.1`–`4.7`.

**No further edits are required to `.zj/QA.md`.** The five I named in the first pass all landed.
The remaining minors (N-1 … N-6) are in scripts, the backlog, MAP.md and PLAN.md, not in the
checklist.
