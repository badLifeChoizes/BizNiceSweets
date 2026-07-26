# UAT — v4.0 milestone (consolidated: CORE · PLUM · SYERP · MOUSSE · CRUMB · GELATO)

**This is the single UAT runbook.** Per **D-P5-6** it consolidates and supersedes
`.zj/UAT-v1.0.md` (PLUM) and `.zj/UAT-v2.0.md` (SYERP inventory & purchasing) for
*execution*; both are retained as history. Closes SRD **NFR-8**.

**48 checks.** Budget ~2–3 h of clicking. You can stop at any point — the
[status table](#status-table--the-resumable-state) is the resumable state, so a paused run
picks up exactly where it left off.

---

## 1. How to run

### 1.1 Bring the stack up on a fresh volume

```bash
cd /home/zack/Projects/BizNiceSweets

# 1. Destroy the old volume. This is deliberate — the fixtures are only
#    authoritative on a volume they were seeded into from empty.
podman-compose -f compose/compose.yml -f compose/compose.dev.yml down -v

# 2. Bring it back up. Both env files must exist (.env and .env.db — D-P5-10);
#    if .env.db is missing the database will not initialize at all.
podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d

# 3. Wait for ready (a few seconds), then confirm the schema is at head.
curl -sS http://localhost:8000/health/ready          # {"status":"ok","db":"connected"}
podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && alembic current'
#                                                   → 0017 (head)

# 4. Seed the named fixtures. Takes about 40 seconds on an empty database —
#    it is not hung. Run it TWICE if you like; the second run changes nothing.
podman exec -e PYTHONPATH=/app compose_api_1 python scripts/seed_uat_fixtures.py
```

### 1.2 Open the app and log in

Click through at **http://localhost:5173** — the Vite dev server, not `:8000`
(D-P5-2 / D-P7-1). Under the dev overlay `:8000` serves the API only and **no SPA at all**,
because the `../backend:/app` bind mount shadows the image's built bundle. HMR also means a
fix can be re-checked in seconds.

Log in as the admin, using the values in your `.env`:

| | |
|---|---|
| Email | `BNS_ADMIN_EMAIL` (default `admin@example.com`) |
| Password | `BNS_ADMIN_PASSWORD` |

> The **prod-stack** smoke at `:8000` is a separate, later exercise — see
> [§7 Prod smoke](#7-prod-stack-smoke-8000).

### 1.3 Re-reading the fixtures mid-run

Any time you want to re-check a number without changing anything:

```bash
podman exec -e PYTHONPATH=/app compose_api_1 python scripts/seed_uat_fixtures.py --manifest
```

That prints the manifest and **writes nothing**.

> ⚠ **Do not run any `backend/scripts/verify_*.py` script during the run.** They create and
> clean up their own data, but `verify_purchasing.py` leaves its receipt journal entries
> behind — measured at **+50.00** on total debit, total credit and total liabilities. That
> shifts the trial-balance and balance-sheet aggregates in §1.4 and would make `C-SYERP-19`
> look broken when it is not. The per-document literals are unaffected.

### 1.4 How to read this runbook

Every check has the same shape:

- **Fixture** — what to open, named exactly as it appears on screen.
- **✅ Machine already proved** — with its citation. **Do not re-check these.** The
  arithmetic, the payloads and the rejections are already asserted by
  `backend/scripts/verify_*.py`, `backend/tests/` and the vitests; the map is
  `.zj/phases/05-human-uat/PREFLIGHT.md`.
- **👁 You are confirming** — the residue only a human can judge: actual wording, colour, a
  badge's presence, a toast's *absence*, sort order as rendered, empty-state copy, whether a
  list refreshed without F5, whether an affordance is reachable at all.
- **✗ Would be wrong** — the specific failure to watch for, usually a defect a previous UAT
  actually found.

**Report per check:** the check ID, **PASS** or **FAIL**, and for a FAIL *what you actually
saw* — the verbatim label, number, colour, or absent element. A screenshot is welcome; the
verbatim observation is what is required. Never a guess, never "looks right".

---

## 2. Named fixtures

Every literal below is quoted from the **Task-8 fresh-volume manifest** recorded in
`docs/tasks/chore-human-uat.md`. That manifest is the single source of truth: if a number on
screen disagrees with it, the manifest is right and the screen is the finding. Document
numbers differ from any earlier dev-database run — those are stale.

### 2.1 Login + people

| Fixture | Value |
|---|---|
| Admin | `BNS_ADMIN_EMAIL` / `BNS_ADMIN_PASSWORD` from `.env` |
| Non-admin user | `uat-plum-user@example.invalid` / password `uat-plum-user-pw` |
| Its role | `UAT-PLUM-ONLY`, permissions `plum:read` **only** |
| Its full name | `UAT PLUM-only User` |

> This user's address uses the reserved `.invalid` TLD, which the Users API rejects on
> *create*. Logging in is unaffected. **Do not delete it** — you will not be able to re-add
> it at that address.

### 2.2 Partners

| Code | Name | Role | Active |
|---|---|---|---|
| `UAT-VEND-1` | UAT Vendor One | vendor | yes |
| `UAT-VEND-2` | UAT Vendor Two | vendor | yes |
| `UAT-VEND-ARCH` | UAT Vendor Archived | vendor | **no** (archived) |
| `UAT-CUST-1` | UAT Customer One | customer | yes |
| `UAT-CUST-2` | UAT Customer Two | customer | yes |

### 2.3 PLUM parts

**Cost / shared-sub-assembly tree** — `UAT-P104` is the one to open:

```
UAT-P104  ──3×──►  UAT-P103  ──2×──►  UAT-P102  ──3×──►  UAT-P101  (material 2.75)
   ├──────5×──────────────────────►  UAT-P102        ← shared sub-assembly
   └──────7×──────────────────────►  UAT-P105        (material 1.20)
```

| Literal | Value |
|---|---|
| `UAT-P104` rolled-up cost | `99.15` |
| `UAT-P104` effective-cost source | `roll-up` |
| `UAT-P104` sale price | `40` |
| `UAT-P104` margin | `-59.15` |
| `UAT-P104` margin % | `-59.66` (exact: `-59.65708522440746343923348462`) |
| Flat BOM row count | `4` |
| Flat `UAT-P102` | qty **`11`**, extended `90.75` ← the dedupe |
| Flat `UAT-P101` | qty `33`, extended `90.75` |
| Flat `UAT-P103` | qty `3`, extended `49.5` |
| Flat `UAT-P105` | qty `7`, extended `8.4` |

**Where-used chain** — open `UAT-P203`: parents are `UAT-P202` **direct**, then `UAT-P201`
**indirect via UAT-P202**.

**Released part** — `UAT-P301`, revision `A`, status `released`, snapshot `26.4`, live
roll-up `26.4`, sale price `35`, margin `8.6` (**above** cost — the non-red control).

**AVL** — `UAT-P401` has **0** vendor links (the Add-Vendor happy path). `UAT-P402` has
**2**:

| | |
|---|---|
| `UAT-VEND-1` | **preferred**, price breaks `qty>=1:7.3, qty>=100:6.15` |
| `UAT-VEND-2` | not preferred, no price breaks |
| `UAT-P402` manual material cost | `9.99` |
| `UAT-P402` selected break index | `1` |
| `UAT-P402` effective cost | **`6.15`**, source `vendor price` |
| `UAT-P402` sale price / margin | `12` / `5.85` |

**MOUSSE build target** — `UAT-P501` (`A`, released), children `2× UAT-P502` and
`3× UAT-P503`. All other `UAT-P…` parts are revision `A (draft)`.

### 2.4 Stock locations, items, bins

| Location | Active | Bins |
|---|---|---|
| `Main` | yes | none |
| `UAT-LOC-A` | yes | **4** — `UAT-BIN-A1`, `UAT-BIN-A2`, `UAT-BIN-STAGE` active; `UAT-BIN-A3` **archived** |
| `UAT-LOC-ARCH` | **no** (archived) | — |
| `UAT-LOC-NOBIN` | yes | **0** — deliberately bin-free |

| Item | On hand | Moving avg | On-hand value | Notes |
|---|---|---|---|---|
| `UAT-ITEM-1` | `Main 7`, `UAT-LOC-A 6`, total `13` | `6.669231` | `86.700003` | PLUM-linked to `UAT-P101` |
| `UAT-ITEM-2` | `Main 4`, total `4` | `12.25` | `49` | standalone |
| `UAT-ITEM-3` | total `0` | `0` | `0` | **archived** |
| `UAT-ITEM-4` | `UAT-LOC-A 15`, `UAT-LOC-NOBIN 4`, total `19` | `3.1` | `58.9` | fully binned at `UAT-LOC-A` |
| `UAT-ITEM-5` | `UAT-LOC-A 20`, `UAT-LOC-NOBIN 10`, total `30` | `5` | `150` | MOUSSE component A |
| `UAT-ITEM-6` | `UAT-LOC-A 30`, `UAT-LOC-NOBIN 15`, total `45` | `1.5` | `67.5` | MOUSSE component B |
| `UAT-ITEM-7` | total `0` | `0` | `0` | MOUSSE finished good |
| `UAT-ITEM-8` | `UAT-LOC-A 25`, total `25` | `6.4` | `160` | sellable, binned in `UAT-BIN-A2` |
| `UAT-ITEM-9` | `Main 13`, total `13` | `7.25` | `94.25` | AP-matched |
| `UAT-ITEM-10` | `UAT-LOC-A 11`, total `11` | `4.75` | `52.25` | AR-invoiced (20 received, 9 shipped) |

**Bin contents at `UAT-LOC-A`:**

| Bin | Holds |
|---|---|
| `UAT-BIN-A1` | `UAT-ITEM-4` **9**, `UAT-ITEM-5` **20** |
| `UAT-BIN-A2` | `UAT-ITEM-4` **6**, `UAT-ITEM-8` **25** |
| `UAT-BIN-A3` | `0` (archived) |
| `UAT-BIN-STAGE` | `0` |

**Unbinned pools** — this is the SC6 crux:

| Item @ location | Unbinned pool | Consequence |
|---|---|---|
| `UAT-ITEM-4` @ `UAT-LOC-A` | **`0`** | a draw **must** name a bin, or it is rejected |
| `UAT-ITEM-1` @ `UAT-LOC-A` | `6` | a draw with no bin named succeeds |
| `UAT-ITEM-5` @ `UAT-LOC-A` | **`0`** | its issue line **must** name a bin |
| `UAT-ITEM-6` @ `UAT-LOC-A` | `30` | its issue line needs no bin |
| `UAT-ITEM-4` @ `UAT-LOC-NOBIN` | `4` | no bins exist there at all |

Roll-up at `UAT-LOC-A` for `UAT-ITEM-4`: `bins 15 + unbinned 0 == location total 15`.

### 2.5 Purchase orders

| PO | Notes marker | Status | Lines | Total | Outstanding |
|---|---|---|---|---|---|
| `PO-0001` | `UAT-PO-DRAFT` | `draft` | `UAT-ITEM-1` ordered `10` @ `5`; `UAT-ITEM-2` ordered `3` @ `12` | `86` | `13` |
| `PO-0002` | `UAT-PO-APPROVED` | `approved` | `UAT-ITEM-2` ordered `9` @ `8`, received `0` | `72` | **`9`** |

`PO-0001` is the approve check's subject. `PO-0002` is the receive / partial / over-receipt
subject — **leave it alone until `C-SYERP-11`**.

> **A third PO exists** and is already fully received — it is what `BILL-0001` was matched
> against, drawing `UAT-ITEM-9` (`13` @ `7.25`, giving `Main 13` and value `94.25`). Its
> number is deliberately **not quoted here**: the seed manifest records numbers only for the
> two POs above, so any number for the third would be hearsay. Identify it on screen by its
> vendor `UAT-VEND-1` and its `received` status, and do not mistake it for `PO-0002`.

### 2.6 Work orders

| WO | Status | Planned | Target location | Components |
|---|---|---|---|---|
| `WO-000001` | `released` | `4` | `UAT-LOC-A` | `UAT-ITEM-5` qty_per `2` required **`8`**; `UAT-ITEM-6` qty_per `3` required **`12`** |
| `WO-000002` | `draft` | `2` | `UAT-LOC-NOBIN` | **none yet** — a BOM is snapshotted at *release*, so `0` components on a Draft is correct |

Full-issue WIP value for `WO-000001`: **`58`**.

### 2.7 CRUMB pipeline

| Fixture | Value |
|---|---|
| Lead | `UAT-LEAD-1`, company `UAT Prospect Co`, status `new` |
| Opportunity (mid-stage) | `UAT-OPP-1`, stage `proposal`, estimated `4250` |
| Opportunity | `UAT-OPP-2`, stage `qualify`, estimated `1875` |
| Quote (still acceptable) | `QUOTE-0001`, status `sent`, total **`324.51`** — line 1 `qty 7 @ 38.28 markup 45 = 267.96`, line 2 `qty 3 @ 18.85 markup 30 = 56.55` |
| Quote (already accepted) | `QUOTE-0002`, status `accepted`, total `100` — `qty 5 @ 20 markup none = 100` |
| Sales order | `SO-0001`, status `confirmed`, total `107.25` — `UAT-ITEM-8` ordered `11` @ `9.75`, **reserved `11`**, shortage `0` |
| Communication log | `2` entries on `UAT-CUST-1`, newest first: `email: UAT-COMM-2 follow-up email with the quote`, then `call: UAT-COMM-1 first contact call` |

### 2.8 The books

| Fixture | Value |
|---|---|
| Manual JE | `UAT-JE-1 manual journal entry (professional services accrual)`, 2 lines, `412.75` each side |
| Opening capital JE | `UAT-JE-0 opening capital contribution`, `8250` |
| Bill (posted) | `BILL-0001`, ref `UAT-BILL-POSTED`, total `94.25`, paid `36.5`, **open `57.75`** |
| Bill (draft) | `BILL-0002`, ref `UAT-BILL-DRAFT`, total `264.5`, open `264.5` |
| Payment | ref `UAT-BILL-POSTED-PAY-1`, amount `36.5`, 1 allocation |
| AR sales order | `SO-0002`, status `fulfilling` — ordered `9`, shipped `9`, invoiced `9` @ `15.5` |
| Invoice | `INV-0001`, status `posted`, total `139.5`, **open `84.25`** |
| Receipt | ref `UAT-SO-2-RCPT-1`, amount `55.25`, 1 allocation |

**Reports** — read these off the screen:

| Report | Expected |
|---|---|
| AP aging | current `0`, **31-60 `57.75`**, 61-90 `0`, 90+ `0`, total `57.75`; 2110 control `57.75`; in balance |
| AR aging | current `0`, 31-60 `0`, **61-90 `84.25`**, 90+ `0`, total `84.25`; 1120 control `84.25`; in balance |
| Trial balance | debit **`8447.25`** == credit **`8447.25`**, net `0`, `9` rows, in balance |
| Balance sheet | assets `7991.75` == liabilities `57.75` + equity `7934`; in balance |
| Income statement | revenue `139.5`, expense `455.5`, net income `-316` (365-day window) |

---

## 3. Ordering rule — read this before you start

**Read-only checks first, mutating checks last. A check must never poison a later check's
fixture.** Two orderings are load-bearing:

1. **Read the books before you post to them.** `C-SYERP-14` … `C-SYERP-19` quote exact
   balances. Run them **before** `C-SYERP-11`/`12` (receiving posts to the GL) and before
   §6's money-loop tail.
2. **The money loop runs last, in dependency order:**

   ```
   C-CRUMB-07   confirm SO-0001, soft reservation
        ↓        (GELATO fulfils a confirmed SO)
   C-GELATO-03  pick → pack → ship SO-0001
        ↓        (AR invoices a shipment)
   C-SYERP-20   bill / pay / invoice / collect, then re-read the TB
   ```

   Each step consumes what the previous one produced. Running `C-GELATO-03` before
   `C-CRUMB-07` leaves it with nothing to pick; running the AR tail first leaves it with
   nothing to invoice.

The suite order below already satisfies both. **Follow it top to bottom** and you cannot go
wrong. If you must jump, check the dependency note on the individual check.

### Things that look like defects but are not

Build-time observations, so you do not report them as findings:

| You will see | It is correct because |
|---|---|
| `UAT-ITEM-3` (archived) shows an **empty** per-location table, not rows of zero | zero-net locations are omitted by documented policy |
| `UAT-BIN-A3` is **absent** from every bin picker but **visible** on the Bins screen with *Show archived* on | pickers deliberately exclude archived bins |
| `WO-000002` (Draft) has **0 components** | a BOM is snapshotted at *release*, not at create |
| Receipts and payments have **no document number** — only a reference string | they genuinely have no number field; the reference is the identifier |
| `SO-0002` shows **reserved `0`** although it shipped `9` | the reservation is consumed by the pick |
| Quote lines number from **0**, PO lines from **1** | a real inconsistency, but cosmetic and known |
| Seeding takes **~40 s** on an empty database | it is not hung |

And one **known candidate minor** — recognise it, do not re-report it as new:

> The pool-floor rejection toast names the location by **numeric id** (e.g. *"…at location
> 374"*) rather than `UAT-LOC-A`. Already logged. If you see it, note "as expected" against
> `C-SC6-a` rather than raising a new defect.

---

## 4. Status table — the resumable state

**This table is the phase's state (D-P5-7).** Every row starts `todo`. A run may be paused
at any point; resume at the first `todo`. **Zero `todo` rows at close** is SC4 — every check
ends as `pass`, `pass (U# fixed <commit>)`, or `U# → BACKLOG`.

| Check | Flow (req) | Suite | Status | Notes |
|---|---|---|---|---|
| C-CORE-01 | Login + bad-password copy (CORE-02) | CORE | ⬜ todo | |
| C-CORE-02 | Session survives access-token expiry (CORE-03) | CORE | ⬜ todo | needs a 15-min wait |
| C-CORE-03 | Users admin list / create / role / deactivate (CORE-04) | CORE | ⬜ todo | |
| C-CORE-04 | Users admin duplicate-email re-entry (CORE-04) | CORE | ⬜ todo | U1 fixed `f508554` — expect a clean 409 |
| C-CORE-05 | RBAC nav filtering as the non-admin user (CORE-05) | CORE | ⬜ todo | |
| C-CORE-06 | Settings save + persist (CORE-06) | CORE | ⬜ todo | FE machine-unproven |
| C-CORE-07 | Home / nav shell + unknown-path fallback (CORE-08) | CORE | ⬜ todo | FE machine-unproven |
| C-PLUM-01 | Parts list search / filter / empty state (PLUM-01) | PLUM | ⬜ todo | |
| C-PLUM-02 | Part detail header + revision selector (PLUM-02, PLUM-03) | PLUM | ⬜ todo | |
| C-PLUM-03 | BOM tree expand / collapse (PLUM-04) | PLUM | ⬜ todo | tree must NOT dedupe |
| C-PLUM-04 | Flat BOM dedupe + Total-BOM-Cost footer (PLUM-05) | PLUM | ⬜ todo | v1.0 **D1** |
| C-PLUM-05 | Where-Used direct / indirect labels + sort order (PLUM-06) | PLUM | ⬜ todo | v1.0 **G1** |
| C-PLUM-06 | Cost & Margin across all three sources (PLUM-08) | PLUM | ⬜ todo | |
| C-PLUM-07 | Below-cost margin rendered red (PLUM-09) | PLUM | ⬜ todo | colour — machine-unproven by design |
| C-PLUM-08 | Released revision BOM + cost read-only (PLUM-03, PLUM-06) | PLUM | ⬜ todo | v1.0 never ran this |
| C-PLUM-09 | New revision + FSM advance (PLUM-03) | PLUM | ⬜ todo | mutating |
| C-PLUM-10 | BOM add / remove on a Draft (PLUM-04) | PLUM | ⬜ todo | mutating |
| C-PLUM-11 | AVL add + Preferred badge + duplicate re-add (PLUM-07) | PLUM | ⬜ todo | v1.0 **D2**; mutating |
| C-PLUM-12 | Import / export + list refresh without F5 (PLUM-10) | PLUM | ⬜ todo | v1.0 **D3**/**G2**; mutating |
| C-SYERP-01 | Vendors / Customers lists + search + show-archived (SYERP-01) | SYERP | ⬜ todo | |
| C-SYERP-02 | Partner create / edit / archive (SYERP-01) | SYERP | ⬜ todo | mutating |
| C-SYERP-03 | Inventory items: auto `ITEM-####`, PLUM link, show-archived (SYERP-10) | SYERP | ⬜ todo | |
| C-SYERP-04 | Item detail on-hand / moving average / value (SYERP-10) | SYERP | ⬜ todo | |
| C-SYERP-05 | Read-only append-only ledger (SYERP-10) | SYERP | ⬜ todo | |
| C-SYERP-06 | Stock locations incl. `Main` + archive (SYERP-10) | SYERP | ⬜ todo | |
| C-SYERP-07 | Stock adjust + floor rejection toast (SYERP-10) | SYERP | ⬜ todo | mutating; see also C-SC6-a |
| C-SYERP-08 | Stock transfer + over-draw toast + unbinned destination (SYERP-10) | SYERP | ⬜ todo | mutating; see also C-SC6-b |
| C-SYERP-09 | PO create — vendor picker lists only vendors (SYERP-11) | SYERP | ⬜ todo | mutating |
| C-SYERP-10 | PO approve — illegal actions hidden (SYERP-11) | SYERP | ⬜ todo | mutating |
| C-SYERP-11 | Receive partial → `Partially Received` (SYERP-11) | SYERP | ⬜ todo | mutating; posts to GL |
| C-SYERP-12 | Receive remainder → `Received`; over-receipt rejected (SYERP-11) | SYERP | ⬜ todo | mutating; posts to GL |
| C-SYERP-13 | PO list vendor filter + close (SYERP-11) | SYERP | ⬜ todo | |
| C-SYERP-14 | GL accounts list (SYERP-12) | SYERP | ⬜ todo | FE machine-unproven |
| C-SYERP-15 | Journal entry post + reverse; account register (SYERP-12) | SYERP | ⬜ todo | read first, then mutate |
| C-SYERP-16 | Bills + bill detail + AP aging footer tie-out (SYERP-12) | SYERP | ⬜ todo | read-only |
| C-SYERP-17 | Pay a bill; overpayment blocked (SYERP-12) | SYERP | ⬜ todo | mutating |
| C-SYERP-18 | Invoices + detail + receipts + AR aging (SYERP-13) | SYERP | ⬜ todo | read-only |
| C-SYERP-19 | Financial reports TB / BS / IS, TB nets zero on screen (SYERP-12) | SYERP | ⬜ todo | read BEFORE any posting |
| C-SYERP-20 | Money-loop tail: bill → pay → invoice → collect → re-read TB (SYERP-12, SYERP-13) | SYERP | ⬜ todo | **runs last** |
| C-MOUSSE-01 | WO list + create from a PLUM BOM (MOUSSE-01) | MOUSSE | ⬜ todo | mutating |
| C-MOUSSE-02 | Release a Draft WO → components snapshot (MOUSSE-01) | MOUSSE | ⬜ todo | mutating |
| C-MOUSSE-03 | Issue components (MOUSSE-01) | MOUSSE | ⬜ todo | mutating; see also C-SC6-c |
| C-MOUSSE-04 | Complete a WO — WIP visibly clears to zero (MOUSSE-01) | MOUSSE | ⬜ todo | mutating |
| C-CRUMB-01 | Leads list + create + convert (CRUMB-01) | CRUMB | ⬜ todo | mutating |
| C-CRUMB-02 | Lead detail (CRUMB-01) | CRUMB | ⬜ todo | machine-unproven |
| C-CRUMB-03 | Pipeline board + stage move (CRUMB-01) | CRUMB | ⬜ todo | mutating |
| C-CRUMB-04 | Opportunity detail (CRUMB-01) | CRUMB | ⬜ todo | machine-unproven |
| C-CRUMB-05 | Quotes list (CRUMB-01) | CRUMB | ⬜ todo | machine-unproven |
| C-CRUMB-06 | Quote detail: PLUM-derived pricing + FSM + accept (CRUMB-01) | CRUMB | ⬜ todo | mutating |
| C-CRUMB-07 | Sales orders + SO detail confirm + soft reservation (CRUMB-01) | CRUMB | ⬜ todo | **head of the money loop** |
| C-CRUMB-08 | Communication log append-only-ness (CRUMB-01) | CRUMB | ⬜ todo | |
| C-GELATO-01 | Bins CRUD + archive toggle (GELATO-01) | GELATO | ⬜ todo | mutating |
| C-GELATO-02 | Putaway incl. the suggestion (GELATO-01) | GELATO | ⬜ todo | mutating |
| C-GELATO-03 | Fulfilment pick → pack → ship `SO-0001` (GELATO-01) | GELATO | ⬜ todo | **after C-CRUMB-07** |
| C-GELATO-04 | Post-ship state (GELATO-01) | GELATO | ⬜ todo | after C-GELATO-03 |
| C-SC6-a | `StockAdjustDialog` bin picker + pool floor (SC6) | SC6 | ⬜ todo | run with C-SYERP-07 |
| C-SC6-b | `StockTransferDialog` from-bin picker (SC6) | SC6 | ⬜ todo | run with C-SYERP-08 |
| C-SC6-c | `IssueComponentsDialog` per-line bin picker (SC6) | SC6 | ⬜ todo | run with C-MOUSSE-03 |
| C-SC6-d | GELATO-off degraded path + module toggle (SC6, CORE-07) | SC6 | ⬜ todo | **must end with GELATO back ON** |

---

## 5. Defects

`U#` IDs. Blocker/major → fixed in-phase with a pinning test. Minor → BACKLOG with the ID.

| ID | Check | Symptom | Severity | Status | Fix / link |
|---|---|---|---|---|---|
| **U0** | — (found at Task 8) | On a **fresh volume** the `db` container never received `POSTGRES_PASSWORD` and Postgres refused to initialize (`Database is uninitialized and superuser password is not specified`). Invisible on an existing volume, so it broke only a first-ever deploy — and would have broken the SC7 prod smoke identically. | blocker | **fixed** | `4ace2c4`; pinned by `backend/tests/test_compose_config.py` (`d870233`). D-P5-10 |
| **U1** | C-CORE-04 | `POST /auth/users` with an existing email returned **HTTP 500** from an unhandled `ix_users_email` `UniqueViolationError` instead of a clean rejection. The v1.0 **D2** pattern. | major | **fixed** | `f508554`; pinned by `backend/tests/auth/test_user_duplicate_email.py` (`f67f085`) |

> Both were found by **engineer** tasks before the owner run — U0 by the fresh-volume
> idempotency proof, U1 by the SC3 pre-flight. They are listed here because SC5 requires the
> ledger to link every defect this phase found to its fix.

---

## 6. The checks

*(authored in Tasks 12–15)*

---

## 7. Prod-stack smoke (:8000)

*(authored at Task 36)*
