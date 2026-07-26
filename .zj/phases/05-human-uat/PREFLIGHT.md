# Pre-flight: check → machine-assertion map (Phase 05, SC3)

**Purpose (SC3).** *No check may ask the human to confirm something a machine could have
confirmed.* Every planned check in `.zj/UAT-v4.0.md` appears below with (a) the **existing**
assertion that already proves its backend or payload, and (b) the **residue** — the part only
a human can judge. Where nothing covers a surface it is marked **`machine-unproven`** with a
reason and a disposition.

## Conventions — read this first

- **Check IDs are `Cnn`-prefixed by suite and are NOT requirement IDs.** `C-CORE-01` is a
  *check*; `CORE-01` is a *requirement* in `.zj/SRD.md`. The `C-` prefix exists purely so the
  two can never be confused in an owner's report or a grep. Numbering is **suite-local and
  gapped by design** (`C-PLUM-01`, `C-PLUM-02`, …) so Tasks 11–15 can insert a check without
  renumbering anything the owner has already reported against.
- **Tasks 11–15 must adopt these IDs verbatim.** The owner reports "C-PLUM-04 FAIL", so the
  IDs are frozen from this commit.
- **Citation forms** (all verified greppable — see the Verification section at the end):
  - `verify_x.py (S)` — scenario letter `S` in `backend/scripts/verify_x.py`.
  - `verify_x.py "phrase"` — a `check()` label in a script that has no scenario letters.
  - `path::test_name` — a pytest test.
  - `path "title"` — a vitest `it(...)` title.
- **Residue is written as an observation, never as an arithmetic claim.** "The footer
  *displays* `99.15` and not `239.40`" is residue; "the roll-up is 99.15" is
  `verify_*`'s job and must not be handed to a human.
- **Fixture literals** all come from the Task-8 fresh-volume manifest recorded in
  `docs/tasks/chore-human-uat.md`. That manifest is authoritative; nothing here restates a
  number it does not contain.

## Summary

| | count |
|---|---|
| Planned checks | **48** |
| Rows with a machine citation | **41** |
| Rows marked `machine-unproven` | **7** |
| … of which probed in Task 10 | **1** (`C-CORE-05`, `getVisibleModules`) |
| … of which deliberately left unprobed | **6** (all pure-appearance or human-judgment; reasons per row) |

Two findings the pre-flight produced *before* any human clicked — both recorded in the rows
that own them, and both worth reading before the owner run starts:

1. **`C-CORE-04` will fail.** Creating a user with an existing email returns **HTTP 500**
   (unhandled `UniqueViolationError`), not a clean 409. Measured live, transcript in the row.
   This is the v1.0 **D2** pattern the plan told us to weight checks toward.
2. **`C-CORE-06`'s fixture user cannot be re-created through the UI.**
   `uat-plum-user@example.invalid` is rejected by `UserCreate.email` (`EmailStr` refuses the
   reserved `.invalid` TLD). Login is unaffected (the login form takes a plain `username`
   string), but the owner must not "fix" the user by deleting and re-adding it.

---

## CORE (D-P5-8) — 6 checks

| Check | Flow (req) | Machine already proves | Residue for the human |
|---|---|---|---|
| **C-CORE-01** | Login with the admin credentials; bad-password path (CORE-02) | `tests/auth/test_login.py::test_login_success`, `::test_login_bad_password`, `::test_login_unknown_email`; `src/auth/Login.test.tsx "calls setAccessToken and navigates on successful login"`, `"shows bad-credentials error copy on 401"` | The error copy's **actual wording** on a wrong password, and that no Create-account / Forgot-password affordance is present. Whether the redirect lands on the page you came from. |
| **C-CORE-02** | Session survives access-token expiry — wait past 15 min, keep clicking (CORE-03) | `tests/auth/test_refresh.py::test_token_refresh`, `tests/auth/test_refresh_rotation.py::test_refresh_rotation_invalidates_old_token`, `::test_reuse_detection_revokes_chain` | That the refresh is **invisible** — no flash of the login page, no lost scroll position, no toast. A machine can prove the token rotates; only a human can see whether the app *blinked*. |
| **C-CORE-03** | Users admin list + create + assign role + deactivate (CORE-04) | `tests/auth/test_user_admin.py::test_admin_create_user`, `::test_admin_list_users`, `::test_admin_update_user_full_name`, `::test_admin_assign_role`, `::test_user_deactivation`, `::test_deactivation_revokes_refresh_tokens`; `src/auth/Users.test.tsx "renders users in a table when data is returned"` | Whether a deactivated user is **visibly** distinguishable in the list, and whether the role picker offers `UAT-PLUM-ONLY`. Empty-state copy on the Users screen. |
| **C-CORE-04** | Users admin **duplicate-email re-entry** (CORE-04) — the v1.0 D2 pattern | **`machine-unproven` → and known-failing.** No guard and no test exist: `grep -n "IntegrityError\|409\|already exists" app/modules/auth/service.py app/modules/auth/router.py` → *no matches*. Measured live: 1st POST `HTTP 201`, 2nd POST same email `HTTP 500`, log `sqlalchemy.exc.IntegrityError … UniqueViolationError: duplicate key value violates unique constraint "ix_users_email"`. | Hand this to the owner **expecting a failure**, and record what the UI actually shows (a raw 500 toast? a silent no-op? a stuck spinner?). The backend defect is already established; the residue is the *user-visible* behaviour. Not probed in Task 10 — a probe would only re-assert a known 500, and the fix is product code, which this phase's tripwires exclude from a test-only task. |
| **C-CORE-05** | RBAC nav filtering as the non-admin fixture user (CORE-05) | **Was `machine-unproven`; probed in Task 10** → `src/components/AppShell.test.tsx` (`getVisibleModules`): `"returns only enabled modules the user has <key>:read for"`, `"treats the admin role as a wildcard over enabled modules"`, `"excludes a disabled module even from an admin"`, `"excludes an enabled module the user lacks <key>:read for"`, `"returns nothing when there is no user"`. Backend side: `tests/auth/test_login.py::test_me_includes_permissions`, `tests/auth/test_rbac.py::test_admin_wildcard_in_permissions` | Log in as `uat-plum-user@example.invalid` / `uat-plum-user-pw` and confirm the sidebar **visibly** shows PLUM alone — and that the other suites are *absent*, not merely disabled-looking. Whether a direct URL to a filtered-out suite is reachable (see `## Noticed` #1 in PLAN: there is no server-side module gate). |
| **C-CORE-06** | Settings save + persist across reload (CORE-06) | `tests/core/test_settings.py::test_list_settings_admin`, `::test_update_setting`, `::test_seed_defaults` | **`machine-unproven` on the FE:** `routes/admin/Settings.tsx` has no vitest. Residue: the save affordance's feedback, and that the value survives a hard reload. **Deliberately unprobed** — the API layer is covered above, so a vitest would only re-assert the same payload through a mock; the untested part is precisely "does the screen wire the mutation up", which is what the human click *is*. |
| **C-CORE-07** | Home / nav shell + unknown-path fallback (CORE-08) | `src/auth/ProtectedRoute.test.tsx "redirects to /login when user is null (unauthenticated)"`, `"renders Outlet (children) when user is authenticated"`, `"renders loading spinner while auth state is being determined"` | **`machine-unproven` on `routes/Home.tsx`** (no vitest). Residue: what Home actually renders for an admin, and what `/no-such-page` shows. **Deliberately unprobed** — Home is a link surface with no logic worth asserting; its correctness *is* its appearance, which is human residue by definition. |

> `C-CORE-08` (module-toggle propagation) is deliberately **not** in this block — it is
> `C-SC6-d` below, so the toggle's blast radius stays contained in one sitting (Task 26).

---

## PLUM — 12 checks

| Check | Flow (req) | Machine already proves | Residue for the human |
|---|---|---|---|
| **C-PLUM-01** | Parts list: search, status filter, empty state (PLUM-01) | `src/routes/plum/PartsList.test.tsx "renders the Parts heading and Create Part button"`, `"renders the No parts yet empty state when API returns an empty array"` | The empty-state **copy** when a search matches nothing (vs. the no-parts-at-all state — are they the same screen?), and whether the filter chips show which filter is active. |
| **C-PLUM-02** | Part detail header + revision selector (PLUM-02/03) | `src/routes/plum/PartDetail.test.tsx` (5 titles, incl. `"falls back to "`) | That `UAT-P104`'s header shows revision `A (draft)` and the selector lists only its own revisions. |
| **C-PLUM-03** | BOM tree expand / collapse on `UAT-P104` (PLUM-04) | `src/routes/plum/components/BomTree.test.tsx "renders a child row when API returns one BOM node"`, `"renders empty state when API returns no children"`; `verify_plum_vendor_paths.py` for the service layer | That the shared sub-assembly `UAT-P102` appears **twice** in the *tree* (once under `UAT-P103`, once direct) — the tree must NOT dedupe, unlike the flat view. Expand/collapse actually toggles. |
| **C-PLUM-04** | **Flat BOM dedupe + Total-BOM-Cost footer** (PLUM-05) — the v1.0 **D1** triple-count | `src/routes/plum/components/BomTree.test.tsx "flat footer shows the rolled-up cost, not the sum of the rows"`, `"flat footer shows an em dash when no rolled-up cost is available"` | That the footer **displays `99.15`** and *not* `239.40` (the sum of the extended costs — the D1 signature), and that `UAT-P102` appears on **exactly one** row showing qty **11**. |
| **C-PLUM-05** | Where-Used direct/indirect labels **and their sort order** (PLUM-06) — the v1.0 **G1** defect | `src/routes/plum/PartDetail.test.tsx "labels a direct parent "`, `"labels a transitive ancestor "`, `"does not label every parent as direct"`, `"sorts the direct parent above the indirect ancestor"` | On `UAT-P203`: that `UAT-P202` reads *direct* and `UAT-P201` reads *indirect via UAT-P202*, in that visual order. The **wording** of both labels. |
| **C-PLUM-06** | Cost & Margin across all three sources (PLUM-08) | `verify_plum_vendor_paths.py "commit_import upserts the AVL link against the resolved vendor_id"` for the vendor path; the roll-up and vendor-price arithmetic is asserted by the seed's own oracle (`_expect` in `seed_uat_fixtures.py`) | That the source **label** on `UAT-P104` reads *roll-up* and on `UAT-P402` reads *vendor price* — and that `UAT-P402` shows `6.15`, not the manual `9.99` or the index-0 break `7.30`. Which of the three is displayed as "effective". |
| **C-PLUM-07** | Below-cost margin **rendered red** (PLUM-09) | *(nothing — colour is not assertable and should not be)* | **`machine-unproven` by design.** `UAT-P104`'s margin `−59.15` / `−59.66 %` must be visually **red/negative-styled**, and `UAT-P301`'s `+8.60` must not be. **Deliberately unprobed:** pure appearance is the human residue by definition (Task 10's explicit exclusion). |
| **C-PLUM-08** | Released revision — BOM + cost **read-only** (PLUM-03/06) | Service layer proven live during Task 3: `add_bom_line` and `update_cost` against `UAT-P301`'s released revision both raise **422** "BOM lines can only be edited on Draft revisions." (transcript in the Task-3 report) | That the **Add Part / edit-cost affordances are absent** on `UAT-P301`, not merely present-and-failing. A disabled-looking button that 422s is a different defect from a hidden one. See `## Noticed` #4(a) in PLAN: the cost-path 422 message says "BOM lines", which is the wrong noun if it ever surfaces. |
| **C-PLUM-09** | New revision + FSM advance draft → in_review → released (PLUM-03) | `verify_part_numbering.py` (numbering); FSM asserted in the seed's `_ensure_released` path driving the real `advance_revision_status` | The **wording** of each status badge, and that only legal transitions are offered at each step. |
| **C-PLUM-10** | BOM add / remove on a Draft (PLUM-04) | `src/routes/plum/components/BomTree.test.tsx`; cycle rejection in the service (`_would_create_cycle`) | That the child picker excludes the part itself, and the rejection **toast wording** on a cycle attempt. |
| **C-PLUM-11** | AVL add + Preferred badge + **duplicate re-add** (PLUM-07) — the v1.0 **D2** | `verify_plum_vendor_paths.py "validate_import accepts a resolvable vendor_code (no ImportError)"`, `"validate_import reports an unknown vendor_code (lookup really ran)"`; the duplicate/reactivate branches exist in `add_avl_link` (409 on active, reactivate on soft-deleted) | On `UAT-P402`: that `UAT-VEND-1` carries a visible **Preferred** badge and `UAT-VEND-2` does not. Re-adding `UAT-VEND-1` must give a clean *"already linked"* message — **not** a 500. Adding a vendor to `UAT-P401` (0 links) is the happy path. |
| **C-PLUM-12** | Import/Export: **Choose File opens a dialog**, **drag-drop highlights and selects**, re-import → 0 errors → Confirm, list refreshes **without F5** (PLUM-10) — the v1.0 **D3** dead picker | `src/routes/plum/ImportExport.test.tsx "the Choose File button opens the hidden file input"`, `"selects a file dropped onto the dropzone (enables Upload and Preview)"`, `"rejects an unsupported dropped file (Upload stays disabled)"`, `"renders the Export as JSON button"`, `"renders the Export as Excel button"`, `"invalidates the plum parts query after a successful commit"`, `"does NOT invalidate when the commit fails"` | That the OS file dialog **actually opens** (a vitest can only prove the click reaches the input), that the dropzone **visibly highlights** on dragover, and that the parts list repaints **without a manual reload**. Excel export must not 500 (the v1.0 **G2** stale-image defect). |

---

## SYERP — 19 checks

### Partners + inventory (read-only first)

| Check | Flow (req) | Machine already proves | Residue for the human |
|---|---|---|---|
| **C-SYERP-01** | Vendors / Customers lists, search, **show-archived toggle** (SYERP-01) | `src/routes/syerp/Vendors.test.tsx "renders the Vendors heading and Create Vendor button with empty state"`; `src/routes/syerp/Customers.test.tsx "renders the Customers heading and Create Customer button with empty state"`; live HTTP proof in the Task-2 report (`?role=vendor` hides `UAT-VEND-ARCH`; `&include_archived=true` reveals it) | That the toggle **visibly** adds `UAT-VEND-ARCH` and that an archived row is distinguishable from an active one. Search behaviour on a partial code. |
| **C-SYERP-02** | Partner create + edit + archive via the Sheet (SYERP-01) | `verify_purchasing.py "create_partner (vendor) + create_item + create_location built the fix"` | The archive **confirmation** wording, and that the row leaves the default list immediately (no F5). |
| **C-SYERP-03** | Inventory items list: auto `ITEM-####`, PLUM link, show-archived (SYERP-10) | `src/routes/syerp/InventoryItems.test.tsx "renders the heading and Create Item button with empty state"`, `"keeps the item Sheet usable when the PLUM parts fetch errors (PLUM disabled)"`; `verify_part_numbering.py` for the numeric-boundary guarantee | That a newly created item is offered the **next** `ITEM-####` (the `UAT-ITEM-n` fixtures deliberately do not perturb the series), and that `UAT-ITEM-1` shows its PLUM link to `UAT-P101` as a followable affordance. |
| **C-SYERP-04** | Item detail: per-location on-hand, total, moving average, on-hand value (SYERP-10) | `src/routes/syerp/InventoryItemDetail.test.tsx "renders header, per-location on-hand, valuation and the ledger"`; arithmetic by `verify_inventory.py` + the seed oracle | On `UAT-ITEM-1`: that the screen **displays** `Main 7`, `UAT-LOC-A 6`, total `13`, moving average `6.669231`, value `86.700003` — and that the quantities are **not** rendered at raw column scale (`7.000000`). See PLAN `## Noticed` #4(c)/(f). |
| **C-SYERP-05** | The **read-only append-only ledger** on item detail (SYERP-10) | `src/routes/syerp/InventoryItemDetail.test.tsx "renders header, per-location on-hand, valuation and the ledger"` | That there is **no edit or delete affordance on any ledger row** — the append-only guarantee made visible. Row ordering. |
| **C-SYERP-06** | Stock locations list incl. `Main` present out-of-the-box + archive (SYERP-10) | `src/routes/syerp/StockLocations.test.tsx "renders the heading and Create Location button with empty state"`, `"opens the create Sheet with a required Name field"`, `"renders location rows returned by the API"` | That `Main` exists on a fresh deploy without being created, and that `UAT-LOC-ARCH` is hidden by default. |

### Inventory mutating

| Check | Flow (req) | Machine already proves | Residue for the human |
|---|---|---|---|
| **C-SYERP-07** | Stock **adjust** happy path + per-location floor rejection **toast** (SYERP-10) | `src/routes/syerp/components/StockAdjustDialog.test.tsx "renders the location, quantity and reason fields"`, `"blocks submit while the reason is blank"`, `"surfaces a 422 negative-stock rejection and keeps the dialog open"`; `verify_inventory.py "negative adjustment below zero is rejected (raises HTTPException)"`; `verify_inventory_race.py (A)`–`(D)` | The **rejection toast's actual wording** and that the dialog stays open with the entered values intact. See PLAN `## Noticed` #4(g): the message names the location by **numeric id** (`location 374`), not `UAT-LOC-A` — expected to read wrong. |
| **C-SYERP-08** | Stock **transfer** happy path + over-draw rejection + destination lands **unbinned** (SYERP-10, D-P4-5) | `src/routes/syerp/components/StockTransferDialog.test.tsx "renders the from-location, to-location and quantity fields"`, `"blocks submit when source and destination are the same"`, `"surfaces a 422 over-draw rejection and keeps the dialog open"`; `verify_gelato.py (F2)` proves the destination leg lands unbinned and both totals stay exact | That total on-hand is **visibly unchanged** across the transfer, and the same-location rejection wording. |

### Purchasing

| Check | Flow (req) | Machine already proves | Residue for the human |
|---|---|---|---|
| **C-SYERP-09** | PO create — vendor picker lists **only** vendors, auto `PO-####` (SYERP-11) | `src/routes/syerp/PurchaseOrderCreate.test.tsx "renders the heading, vendor Select, and one line row"`, `"blocks submit until a vendor is selected"`, `"POSTs the Draft PO header then the filled line on submit"`, `"excludes inactive items from the line item Select"`, `"adds a line row when "`; `verify_purchasing.py "create_po opens a Draft PO for the vendor"`, `"add_line appended a line qty 10 @ 5 (qty_received starts at 0)"` | That the vendor dropdown shows **no customers** (`UAT-CUST-1/2` absent) and **no archived vendor** (`UAT-VEND-ARCH` absent) — reachability, not payload. |
| **C-SYERP-10** | PO approve — lines become non-editable, illegal actions **hidden** (SYERP-11) | `src/routes/syerp/PurchaseOrderDetail.test.tsx "shows Approve (and hides Close/Receive) for a draft PO"`, `"shows Close + per-line Receive (and hides Approve) for an approved PO"`; `verify_purchasing.py "advance_po_status draft → approved (stamps approver)"` | On `PO-0001` (draft, 2 lines): that Approve is offered and Receive is **absent**. After approving: that the line fields are genuinely not editable, not merely styled as such. |
| **C-SYERP-11** | Receive **partial** → `Partially Received`, on-hand and moving average move (SYERP-11) | `src/routes/syerp/components/ReceiveLineDialog.test.tsx "defaults the quantity to the outstanding balance and renders the location Select"`, `"posts the receipt and closes on success"`; `verify_purchasing.py "after receiving 4 the PO is 'partially_received'"`, `"line.qty_received accumulated to 4 after the first receipt"`, `"moving_avg_cost reflects the receipt unit cost (first receipt → 5.000"` | On `PO-0002` (approved, 9 outstanding of `UAT-ITEM-2`): that the **status badge wording** changes and the item's moving average visibly moves off `12.25`. |
| **C-SYERP-12** | Receive **remainder** → `Received`; then **over-receipt rejected** with nothing posted (SYERP-11) | `src/routes/syerp/components/ReceiveLineDialog.test.tsx "surfaces a 422 over-receipt rejection and keeps the dialog open"`; `verify_purchasing.py "over-receipt (4 + 10 > 10 ordered) RAISES HTTPException 422"`, `"rejected over-receipt left line.qty_received unchanged (still 4)"`, `"rejected over-receipt left on-hand unchanged (still 4)"`, `"after receiving the remaining 6 the PO is 'received'"` | The over-receipt **toast wording**, and that the on-screen received/outstanding figures do not budge after the rejection. |
| **C-SYERP-13** | PO list vendor filter + close (SYERP-11) | `src/routes/syerp/PurchaseOrders.test.tsx "renders the heading, Create PO button, and vendor filter with empty state"`, `"renders a PO row with status badge, total, and resolved vendor name"`; `verify_purchasing.py "list_pos(vendor_id) returns the PO with total == Decimal('50') and st"`, `"a DIFFERENT vendor's filter does NOT return this PO"` | That filtering by `UAT-VEND-2` shows `PO-0002` and hides `PO-0001`, and the Close affordance's placement/label. |

### GL / AP / AR / reports

| Check | Flow (req) | Machine already proves | Residue for the human |
|---|---|---|---|
| **C-SYERP-14** | GL accounts list — 47 seeded accounts, rollup parents (SYERP-12) | **`machine-unproven` on the FE:** `routes/syerp/GLAccounts.tsx` has **no vitest** (measured hole). Backend: `verify_reports.py "rollup-parent accounts that carry children but no direct postings "` | Weight this heavily. Residue: that the tree renders 47 accounts, that rollup parents are visually distinct from posting accounts, and that nothing is editable. **Deliberately unprobed** — the account list is a read-only render of seed data with no logic; a vitest would assert a mock renders, which is the least valuable thing here and would create false confidence in the *screen*. |
| **C-SYERP-15** | Journal entry post + **reverse**; account register (SYERP-12) | `src/routes/syerp/JournalEntries.test.tsx "renders the heading and the posted entries list"`, `"opens the dialog and appends a line"`, `"gates Post on a balanced ≥2-line entry"`; `src/routes/syerp/AccountRegister.test.tsx "renders posting rows with a running balance once an account is selected"`, `"displays the opening and closing balances for the period"`; `verify_gl.py (A)`, `(B)`, `(M1)` | That `UAT-JE-1` (412.75) and `UAT-JE-0` (8250.00) both appear, that the unbalanced-entry Post button is genuinely disabled (not just error-toasting), and that a reversal is **visibly linked** to its original. |
| **C-SYERP-16** | Bills list + bill detail + AP aging **footer tie-out** (SYERP-12) | `src/routes/syerp/Bills.test.tsx "renders bills from a mocked GET with resolved vendor, status, and total"`, `"opens the dialog, matches an unbilled line + a non-PO line, and POSTs the right body"`, `"omits REVENUE accounts from the non-PO account Select"`; `src/routes/syerp/BillDetail.test.tsx` (5 titles); `src/routes/syerp/ApAging.test.tsx "renders per-vendor bucket cells for each vendor"`, `"renders the grand-total footer row"`, `"renders the 2110 tie-out badge when in balance"`, `"refetches with the new as_of when the date changes"`; `verify_ap.py "CRUX: after receive + post_bill the 2150 GR/IR derived balance EQUALS"`; `verify_reports.py "a DRAFT bill (999, not posted) appears in NEITHER the aging total NOR"` | That the aging screen **displays** `57.75` in the **31-60** column (not `current`), that the tie-out badge reads in-balance, and that **`BILL-0002` (draft, 264.50) is absent from the aging** — the divergence guard made visible. |
| **C-SYERP-17** | Pay a bill; overpayment blocked (SYERP-12) | `src/routes/syerp/BillDetail.test.tsx "shows Pay (and hides Post) for a posted bill"`, `"blocks a pay amount above the open balance"`, `"records a valid payment: POST /ap/payments with the correct allocation body"`; `verify_ap.py "a partial payment (20 of 50) leaves the bill 'posted' with open_balan"`, `"the payment JE is a balanced Dr 2110 / Cr 1110 cash for 20 "`, `"the final payment (remaining 30) auto-advances the bill 'posted' -> "` | That `BILL-0001` shows open `57.75` after its `36.50` payment, and the overpayment block's **message**. |
| **C-SYERP-18** | Invoices + invoice detail + receipts + AR aging (SYERP-13) | `src/routes/syerp/Invoices.test.tsx "renders invoices from a mocked GET with resolved customer, status, and total"`, `"picker renders uninvoiced_qty + read-only locked price, then POSTs InvoiceCreate"`; `src/routes/syerp/InvoiceDetail.test.tsx` (3 titles); `src/routes/syerp/Receipts.test.tsx "renders receipts with the resolved account, amount, and allocations"`, `"opens the Record receipt dialog"`; `src/routes/syerp/ArAging.test.tsx` (4 titles); `verify_ar.py (B)`, `(C)`, `(D)`, `(G)` | That `INV-0001` shows total `139.50` / open `84.25`, that AR aging puts it in the **61-90** column, and — per PLAN `## Noticed` #4(k) — **what the Receipts list uses to identify a row**, since a receipt has no document number, only the reference `UAT-SO-2-RCPT-1`. |
| **C-SYERP-19** | Financial reports TB / BS / IS with the **TB netting zero on screen** (SYERP-12) | `src/routes/syerp/FinancialReports.test.tsx "renders the Trial Balance tab with account rows and a balanced totals footer"`, `"renders the Profit & Loss tab with revenue/expense lines and net income"`, `"fires the P&L query with a non-empty From date so it never 422s on first open (G1)"`, `"renders the Balance Sheet tab with assets/liabilities/equity and a balanced total"`; `verify_reports.py "trial_balance total_debit EXACTLY equals total_credit and in_balance "`, `"balance_sheet total_assets EXACTLY equals total_liabilities + total_e"`, `"P&L net_income EXACTLY equals total_revenue − total_expense (report i"`, `"the COMPUTED 3130 'Current Year Net Income' equity line (exactly one,"` | That the TB footer **displays** `8447.25 = 8447.25` and reads as balanced, and the BS shows assets `7991.75` = liabilities `57.75` + equity `7934.00`. **Do not run any `verify_*` script against the stack first** — that shifts the aggregates by 50.00 (Task-8 finding). |

---

## MOUSSE (MOUSSE-01) — 4 checks

| Check | Flow | Machine already proves | Residue for the human |
|---|---|---|---|
| **C-MOUSSE-01** | WO list + create from a PLUM BOM | `src/routes/mousse/WorkOrders.test.tsx "renders work orders from a mocked GET with the part resolved to its number"`, `"creates a work order from the dialog and refetches the invalidated list"`; `src/routes/mousse/components/WorkOrderCreateDialog.test.tsx "POSTs the right body and invalidates the work-order list on submit"`, `"omits inactive locations from the target-location Select"`; `verify_mousse.py (A)` | That the part picker offers only parts with a **Released** revision (`UAT-P301`, `UAT-P501`) — reachability of the constraint, not the payload. |
| **C-MOUSSE-02** | Release a Draft WO → components snapshot | `verify_mousse.py (B)`, `(C)`; `src/routes/mousse/WorkOrderDetail.test.tsx "renders the header + snapshot lines with on_hand and issued_so_far"` | On `WO-000002` (draft, plan 2, `UAT-LOC-NOBIN`): that the component table is **empty before release** and populated after — and that an empty table on a Draft reads as intended, not broken (PLAN `## Noticed` #4(i)). |
| **C-MOUSSE-03** | Issue components | `src/routes/mousse/WorkOrderDetail.test.tsx "issues components: POSTs …/issue and invalidates the detail + list queries"`; `src/routes/mousse/components/IssueComponentsDialog.test.tsx "POSTs the seeded remaining quantities (bin_id: null untouched) and calls onSuccess"`, `"drops an unchecked line from the posted body"`; `verify_mousse.py (D)`, `(E)`, `(G)` | On `WO-000001`: that the required quantities **display** `UAT-ITEM-5 → 8` and `UAT-ITEM-6 → 12`, and that WIP visibly rises. Bin behaviour is `C-SC6-c`. |
| **C-MOUSSE-04** | Complete a WO — **WIP visibly clears to zero** | `verify_mousse.py (F)`; `src/routes/mousse/WorkOrderDetail.test.tsx "completes a fully-issued WO: POSTs …/complete and invalidates the queries"` | That WIP is **shown as 0** after completion (the phase's headline visual), and that the finished good `UAT-ITEM-7` appears in stock at `UAT-LOC-A`. |

---

## CRUMB (CRUMB-01) — 8 checks

| Check | Flow | Machine already proves | Residue for the human |
|---|---|---|---|
| **C-CRUMB-01** | Leads list + create + convert-to-opportunity | `src/routes/crumb/Leads.test.tsx "renders the leads list from a mocked GET, showing each row"`; `verify_crumb.py (A)`, `(B)` | That `UAT-LEAD-1` (status `new`) offers a Convert affordance and that conversion **visibly** moves it to `converted`. |
| **C-CRUMB-02** | Lead detail | **`machine-unproven`:** `routes/crumb/LeadDetail.tsx` has **no vitest** (measured hole). Backend: `verify_crumb.py (A)`,`(B)` | Weight heavily. Residue: that every field entered on create is displayed back, and that the linked customer/opportunity are followable. **Deliberately unprobed** — see the shared reason under `C-CRUMB-04`. |
| **C-CRUMB-03** | Pipeline board + stage move | `src/routes/crumb/Pipeline.test.tsx "renders the four stage columns and groups the opportunity under Proposal"`; `verify_crumb.py (C)` | That `UAT-OPP-1` sits under **Proposal** and `UAT-OPP-2` under **Qualify**, and that only legal forward moves are offered (`won`/`lost` are terminal). |
| **C-CRUMB-04** | Opportunity detail | **`machine-unproven`:** `routes/crumb/OpportunityDetail.tsx` has **no vitest**. Backend: `verify_crumb.py (C)`, `(D)` | Weight heavily. **Deliberately unprobed (shared reason for `C-CRUMB-02`/`04`/`05`):** these three screens' backends are covered by `verify_crumb.py` scenarios A–H, so a vitest would re-assert a mocked payload renders; the untested risk is *wiring and reachability*, which is exactly what a human click tests and a mock cannot. Probing them would consume the budget that `getVisibleModules` — a pure function with real branching logic and zero coverage — actually needed. |
| **C-CRUMB-05** | Quotes list | **`machine-unproven`:** `routes/crumb/Quotes.tsx` has **no vitest**. Backend: `verify_crumb.py (E)`, `(F)` | Weight heavily. Residue: that `QUOTE-0001` (sent) and `QUOTE-0002` (accepted) both list with correct status badges. **Deliberately unprobed** — shared reason above. |
| **C-CRUMB-06** | Quote detail: **PLUM-derived line pricing** + line editor totals + status FSM + accept | `src/routes/crumb/QuoteDetail.test.tsx "renders the line price default and the quote total from a mocked GET"`, `"shows "`, `"hides "`; `verify_crumb.py (E)`, `(F)`, `(G)` | On `QUOTE-0001`: that the lines **display** `7 @ 38.28 = 267.96` and `3 @ 18.85 = 56.55` with total `324.51` — and that the 45 % markup line is visibly distinguishable from the default-30 % line. That Accept is offered on a `sent` quote and gone on an `accepted` one. |
| **C-CRUMB-07** | Sales orders list + SO detail confirm showing the **soft reservation** | `src/routes/crumb/SalesOrders.test.tsx "renders the sales-order list from a mocked GET, showing each row"`; `src/routes/crumb/SalesOrderDetail.test.tsx "renders a draft SO with ordered/reserved/shortage figures, flags, and Confirm + Cancel"`, `"shows Fulfill + Cancel for a confirmed SO"`, `"surfaces each line"`; `verify_crumb_so.py (A)`–`(F)` | On `SO-0001`: that ordered `11` / reserved `11` / shortage `0` are **displayed** and the reservation is labelled in a way a human understands as "soft". |
| **C-CRUMB-08** | Communication log **append-only-ness** | `src/routes/crumb/Communications.test.tsx "renders the timeline newest-first with type, timestamp and body"`; `verify_crumb.py (H)` | That `UAT-COMM-2` (email) appears **above** `UAT-COMM-1` (call), and that **no row offers edit or delete** — append-only made visible. |

---

## GELATO (GELATO-01) — 4 checks

| Check | Flow | Machine already proves | Residue for the human |
|---|---|---|---|
| **C-GELATO-01** | Bins CRUD + archive toggle | `src/routes/gelato/Bins.test.tsx "renders bins for the selected location"`, `"creates a bin via the Sheet and POSTs the payload"`, `"surfaces a duplicate-code 4xx as an error toast"`, `"hides archived bins until the Show archived switch is on"`; `verify_gelato.py (A)`, `(B)` | That `UAT-LOC-A` lists `UAT-BIN-A1/A2/STAGE` with `UAT-BIN-A3` hidden until the toggle — and per PLAN `## Noticed` #4(h), that the archived bin is *correctly hidden* rather than *missing*. |
| **C-GELATO-02** | Putaway incl. the **suggested bin** | `src/routes/gelato/Putaway.test.tsx "renders the unbinned-stock list for the default-selected location"`, `"pre-fills the suggested bin and defaults qty to the full unbinned qty"`, `"posts the EXACT PutawayRequest body on Confirm (the 11b keeper)"`, `"surfaces a 422 over-draw rejection as a toast and keeps the dialog open"`; `verify_gelato.py (A)`, `(B)`, `(C)`, `(D)` | That `UAT-ITEM-4` is **absent** from the unbinned list at `UAT-LOC-A` (pool is 0 — nothing to put away) but **present** at `UAT-LOC-NOBIN` with `4`. The suggestion's rationale being legible. |
| **C-GELATO-03** | Fulfilment **pick → pack → ship** against `SO-0001` | `src/routes/gelato/Fulfillment.test.tsx "renders the pick list with ordered/reserved/picked/shipped for the preselected SO"`, `"pre-fills the suggested source bin in the pick dialog"`, `"posts the EXACT PickRequest body on Confirm (the 11b/12a keeper)"`, `"walks pick → pack → ship, POSTing the ship endpoint after confirmation"`; `verify_gelato_ship.py`, `verify_gelato_ship_api.py` | That the suggested source bin is `UAT-BIN-A2` (holding 25, live-proven in the Task-6 report) and that each stage's affordance appears **only** at the right stage. |
| **C-GELATO-04** | Post-ship state | `src/routes/crumb/SalesOrderDetail.test.tsx "shows Fulfill / Ship when GELATO is enabled ∩ gelato:read on a fulfilling SO"`; `verify_gelato_ship.py` | That `SO-0001` visibly moves to `fulfilling`, `qty_shipped` shows `11`, and the shipment is followable from the SO. |

---

## SC6 — the Phase-4 bin pickers (v4.0's only new UI surface) — 4 checks

These are the reason the phase exists in its current shape: unit-tested, never human-driven.

| Check | Dialog + fixture | Machine already proves | Residue for the human |
|---|---|---|---|
| **C-SC6-a** | `StockAdjustDialog` bin picker — `UAT-ITEM-4` @ `UAT-LOC-A` (pool **0**) vs `UAT-ITEM-1` @ `UAT-LOC-A` (pool **6**) | `src/routes/syerp/components/StockAdjustDialog.test.tsx "POSTs bin_id when a bin is chosen (D-P4-1)"`, `"POSTs bin_id: null when the bin picker is left on "`, `"hides the bin picker and POSTs bin_id: null when the bins query fails"`; `verify_gelato.py (E)`, `(F3)`; the pool floor proven live in Task 5 (`HTTP 422: Adjustment of -1 exceeds the unbinned pool at location 374 (current 0)`) | That the picker **appears only after** a location with active bins is chosen, **defaults to "Unbinned pool"**, and **resets when the location changes**. Then: a negative adjust on `UAT-ITEM-4` with no bin named must be **rejected with a visible toast**, while the same action on `UAT-ITEM-1` succeeds — two items in one dialog, opposite outcomes. Expect the toast to name `location 374` rather than `UAT-LOC-A`. |
| **C-SC6-b** | `StockTransferDialog` **from-bin** picker (D-P4-5) | `src/routes/syerp/components/StockTransferDialog.test.tsx "POSTs from_bin_id when a source bin is chosen (D-P4-1)"`, `"POSTs from_bin_id: null when the picker is left on "`, `"hides the from-bin picker and POSTs from_bin_id: null when the bins query fails"`; `verify_gelato.py (F)`, `(F2)` | Same picker shape as (a); plus that the destination leg lands **unbinned** and total on-hand is **visibly unchanged**. |
| **C-SC6-c** | `IssueComponentsDialog` **per-line** bin picker — `WO-000001`, `UAT-ITEM-5` (pool **0** → bin required) vs `UAT-ITEM-6` (pool **30** → none needed) | `src/routes/mousse/components/IssueComponentsDialog.test.tsx "POSTs bin_id on the line whose bin is chosen, null on the untouched line (D-P4-1)"`, `"hides the bin pickers and POSTs bin_id: null when the bins query fails"`, `"drops an unchecked line from the posted body"`; `verify_mousse.py (G)` | That the bin column appears **per line** and each line's bin is **independently** selectable — and that line 1 (`UAT-ITEM-5`) is rejected without a bin while line 2 (`UAT-ITEM-6`) is not. One dialog, two opposite requirements. |
| **C-SC6-d** | **GELATO-off degraded path** + module-toggle propagation (CORE-07) | `tests/core/test_modules.py::test_list_modules_returns_enabled_flag`, `::test_toggle_module`, `::test_cannot_disable_always_on`, `::test_toggle_requires_admin`; `src/components/AppShell.test.tsx "excludes a disabled module even from an admin"` (Task 10); `src/routes/crumb/SalesOrderDetail.test.tsx "hides Fulfill / Ship when the GELATO module is disabled"` | **Written as an observation, not a confirmation.** Toggle GELATO off, confirm the sidebar drops it, then re-open all three dialogs and **record what actually happens to the bin pickers**. Per PLAN `## Noticed` #1 there is **no server-side module gate**, so `/api/v1/gelato/*` keeps serving and the dialogs' docstring claim ("hidden when the bins query errors (GELATO off)") is probably wrong about the cause. Also try `/gelato/bins` directly. **Must end by toggling GELATO back on and confirming the sidebar restores** — later checks depend on it. |

---

## `machine-unproven` register (7 rows)

| Check | Surface | Probed? | Reason |
|---|---|---|---|
| `C-CORE-04` | duplicate-email user create | **No** | Already established as a **500** by live measurement; the fix is product code, excluded from a test-only task. Hand to the owner expecting failure. |
| `C-CORE-05` | `getVisibleModules` nav filter | **YES — Task 10** | A pure function with real branching (enabled ∩ permitted, admin wildcard) and zero coverage, behind CORE-05/07 and `C-SC6-d`. The one row that genuinely needed a probe. |
| `C-CORE-06` | `admin/Settings.tsx` | No | API covered by `tests/core/test_settings.py`; the untested part is FE wiring, which is what the human click *is*. A mock-based vitest would assert the payload again, not the wiring. |
| `C-CORE-07` | `routes/Home.tsx` | No | A link surface with no logic; its correctness *is* its appearance — human residue by definition. |
| `C-PLUM-07` | below-cost margin **red** | No | Colour. Task 10 explicitly excludes pure appearance. |
| `C-SYERP-14` | `syerp/GLAccounts.tsx` | No | Read-only render of seed data, no logic. A vitest here would create false confidence in the screen while asserting nothing about it. |
| `C-CRUMB-02/04/05` | `LeadDetail`, `OpportunityDetail`, `Quotes` | No | Backends covered by `verify_crumb.py (A)`–`(H)`; the residual risk is wiring/reachability, which a mocked render cannot reach. Counted as one register row, three checks. |

---

## Citation verification

Every cited path and every cited test/scenario name was grepped; **zero misses**. The
verification script and its output are recorded in the Task-9 report. Re-run with:

```bash
# every cited backend test name
grep -c "def test_login_success"       backend/tests/auth/test_login.py
# every cited vitest title
grep -c "flat footer shows the rolled-up cost, not the sum of the rows" \
        frontend/src/routes/plum/components/BomTree.test.tsx
# every cited verify_* scenario letter / label
grep -c "(F2)" backend/scripts/verify_gelato.py
```
