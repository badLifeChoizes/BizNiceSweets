# UAT — v1.0 milestone (PLUM)

> **Superseded for execution by [`.zj/QA.md`](QA.md)** (D-P5-11; previously by
> `.zj/UAT-v4.0.md` per D-P5-6, itself now history). Retained as **history** — its defect
> record (G1, G2, D1, D2, D3) is cited throughout. The **10 of 12** checks still open here
> were carried into v4.0's PLUM block and from there into `.zj/QA.md` under **PLUM-01..10**;
> do not run this file.

Per **D-P7-5**, human click-through UAT is a milestone-close activity, run once at
`/zj:milestone` against the Vite dev server (**http://localhost:5173**, D-P7-1) with the
Podman stack up (`podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`;
API container `compose_api_1`, `alembic current` == `0008 (head)`). Log in as admin.

## Fixtures actually present in the dev DB (re-confirmed 2026-07-09)

> The previously-listed fixtures (`ITEST-ASM-01`, `P100000`, Released `P00001`/`P00002`/`P99999`)
> **no longer exist** — the dev volume was recreated. There are currently **no Released parts at
> all**. Checks 1 and 8 already passed on 2026-07-04 and are not re-run, so no Released fixture
> is needed.

The milestone audit left two purpose-built structures. All revisions are **Draft, label `A`**.

**Cost / shared-sub-assembly tree — use `P100004`:**

```
P100004  ──3×──►  P100003  ──2×──►  P100002  ──4×──►  P100001  (material cost 2.50)
   └─────5×────────────────────────►  P100002          ← shared sub-assembly
```
Rolled up: `P100002` = 4 × 2.50 = **10.00**; `P100003` = 2 × 10 = **20.00**;
`P100004` = (3 × 20) + (5 × 10) = **110.00**. `P100004` sale price = **50.00** → margin **−60.00**
(**−54.55 %**), i.e. below cost. Flat BOM of `P100004`: `P100002` must appear **once**, total qty
**11** (5 direct + 3×2 nested).

**Where-used chain — use `P100007`:** `P100005 ──2×──► P100006 ──3×──► P100007`
(a second identical chain exists: `P100008 → P100009 → P100010`).

**Vendors for AVL:** `P-0003 AUDIT AVL Vendor`, `P-0001 AUDIT Vendor Acme`, `V-VER-1 Verifier Vendor`.

**Next auto part number:** highest is `P100010`, so check 12 must yield **`P100011`**.
*Run check 12 last* — every part you create shifts this number.

> **First-round blockers (2026-07-09 milestone audit) — cleared:**
> - Check 3: Where-Used labelled *every* parent "Direct parent" (gap **G1**, fixed `63ea954`).
> - Check 7 Excel: export 500'd, API image lacked `openpyxl` (gap **G2**, image rebuilt).
>
> **Second-round defects the human UAT found on 2026-07-11 — fixed, re-run the affected checks:**
> - **Check 2** — the flat "Total BOM Cost" footer showed **280** (summed sub-assemblies, triple-counting
>   material). Now shows the assembly's rolled-up cost. **Expect 110.00** (gap **D1**).
> - **Checks 4/9/10/11** — "Add Vendor" returned **500** when the vendor was already linked (an unhandled
>   duplicate-key crash; soft-deleted links also blocked re-adding). Now: re-adding an active link gives a
>   clean "already linked" message; re-adding a removed one reactivates it (gap **D2**, proven live).
> - **Check 7 import** — the file picker was dead: no drag-drop handler, and "Choose File" didn't open a
>   dialog. Both now work (gap **D3**).
>
> **Rebuild the image if you recreate the stack** (keeps G2 fixed):
> `podman-compose -f compose/compose.yml -f compose/compose.dev.yml build api`. The backend D1/D2 fixes
> are already live via the dev bind-mount + `--reload`; the frontend D1/D3 fixes are live via Vite HMR.
>
> If a check still fails, that is new information worth stopping for.

## Checklist

| # | Flow (req) | Status | Notes |
|---|---|---|---|
| 1 | BOM card — Add Part on a Draft revision → child in tree; expand/collapse (PLUM-04) | ✅ pass | Verified 2026-07-04 on ITEST-ASM-01; Add Part shows only when current revision is Draft |
| 8 | Released revision — BOM + cost read-only; frozen "Released at" cost (PLUM-03/06) | ✅ pass | Verified 2026-07-04; Add Part correctly hidden on Released parts |
| 2 | BOM flat view — shared sub-assembly = ONE row, summed Total Qty + Total BOM Cost footer (PLUM-05) | ⬜ todo | |
| 3 | Where-Used card — parents labeled "Direct parent" / "Indirect via {part}" (PLUM-06) | ⬜ todo | **G1 fixed `63ea954`** — was guaranteed to fail. Needs a 3-level BOM (A→B→C); open C, expect B "Direct parent" **above** A "Indirect via B" |
| 4 | AVL card — Add Vendor → pick SYERP vendor → link persists after refresh; Preferred badge (PLUM-07) | ⬜ todo | Phase-7 fix landed & code-verified |
| 5 | Cost & Margin — manual / roll-up / vendor-price sources (PLUM-08) | ⬜ todo | vendor-price source now reachable (PLUM-07 fixed) |
| 6 | Sale Price → Margin + Margin %; below-cost shows red (PLUM-09) | ⬜ todo | |
| 7 | Import/Export — JSON+Excel export; re-import → 0 errors → Confirm "No records deleted"; >10 MB rejected (PLUM-10) | ⬜ todo | **G2 fixed** — image rebuilt, `openpyxl 3.1.5` present; Excel export verified 200 + valid `.xlsx`. JSON round-trip and 10 MB guard already proven via API |
| 9 | AVL add completes with NO 500 / error toast (SC1) | ⬜ todo | proves `SyerpPartner`→`Partner` fix (`5c33ed8`) |
| 10 | Import w/ vendor reference previews + commits with NO 500 (SC1) | ⬜ todo | same fix; commit path passed a manual per-test run |
| 11 | After Confirm Import, Parts List updates without manual refresh (SC3) | ⬜ todo | proves cache-invalidation fix (`37b5f97`) |
| 12 | New Part with no part_number → fresh unique `P#####`, no duplicate-key error (SC2) | ⬜ todo | proves numeric part# fix (`1b8bfa1`); code-verified live (P100000→P100001) |

## What the machine already proved (2026-07-09 milestone audit)

The API-layer behaviour behind every check below is proven — see `.zj/MILESTONE-v1.0-AUDIT.md`
(66 live-DB assertions, 0 failures; 3-level BOM, flat dedup, exact Decimal roll-up `110.000000`,
margin 40 / −60, AVL persistence, JSON round-trip, 11 MB → 413). What remains is **the part a
machine cannot see**:

| Check | Residue only a human can confirm |
|---|---|
| 2 | shared sub-assembly is **one row**; the Total-BOM-Cost **footer** renders |
| 3 | the two labels read correctly and sort direct-above-indirect |
| 4 | the **Preferred badge** is visibly present |
| 6 | below-cost margin is actually **red** |
| 9, 10 | **no error toast appears** (absence is unobservable via API) |
| 11 | the Parts List visibly updates **without a manual refresh** (mechanism pinned by vitest) |
| 12 | essentially closable by machine — proven live (`P100000` → `P100001`) |

## Runbook — the 10 remaining checks, in order

Run them in this order: read-only checks first, mutating checks last (imports and part creation
change the fixtures the earlier checks rely on).

### 0. Bring the stack up

```bash
cd /home/zack/Projects/BizNiceSweets
podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d
podman exec compose_api_1 sh -c 'cd /app && alembic current'   # must print: 0008 (head)
```
If you recreated the `api` container from scratch, **rebuild it first** or G2 (Excel 500) returns:
`podman-compose -f compose/compose.yml -f compose/compose.dev.yml build api`

Open **http://localhost:5173** (Vite dev server, per D-P7-1 — *not* :8000, which serves a stale
bundle). Log in as the admin from `.env` (`BNS_ADMIN_EMAIL` / `BNS_ADMIN_PASSWORD`).

---

### Check 2 — Flat BOM: shared sub-assembly is ONE row (PLUM-05) ← *D1 fixed*
Parts → `P100004` → **BOM** card → switch to **Flat** view.
- ✅ `P100002` appears on **exactly one row**, Total Qty **11** (not two rows of 5 and 6).
- ✅ The **Total BOM Cost footer** shows **110.0000** — *not 280* (that was the D1 double-count).
- ✅ `P100001` shows total qty 44; `P100003` shows 3.

### Check 3 — Where-used labels (PLUM-06) ← *the G1 fix*
Parts → `P100007` → **Where-Used** card.
- ✅ `P100006` labelled **“Direct parent”**.
- ✅ `P100005` labelled **“Indirect via P100006”**.
- ✅ The direct parent sorts **above** the indirect one.
- ❌ If *both* say “Direct parent”, the G1 fix regressed — stop and report.

### Check 5 — Cost & Margin sources (PLUM-08)
Still on `P100004` → **Cost & Margin** card.
- ✅ Effective Cost **110.00**, source shown as **roll-up** (no manual cost is set).
- ✅ Now open `P100001`: source is **manual** (material cost 2.50).
- ✅ After check 4 links a vendor with a price, that part's source becomes **vendor-price**.

### Check 6 — Below-cost margin renders RED (PLUM-09)
On `P100004` (sale 50.00, cost 110.00):
- ✅ Margin shows **−60.00** and Margin % **−54.55 %**.
- ✅ Both are styled **red**. *(This is the one a machine cannot see — look at the colour.)*
- ✅ Raise Sale Price above 110 → the red styling clears.

### Check 4 + Check 9 — AVL add (PLUM-07, SC1) ← *D2 fixed*
Parts → a Draft part → **AVL** card → **Add Vendor**. Use a part **without** an existing link to
that vendor for the happy path — e.g. `P100005` (P100001/P100003 already carry audit links).
- ✅ The vendor search lists only real vendors (`AUDIT AVL Vendor`, `Verifier Vendor`).
- ✅ Save → **no 500, no error toast** *(check 9 — you are confirming an* absence *)*.
- ✅ Reload the page: the link **persists**.
- ✅ Mark it Preferred → a **Preferred badge** is visibly rendered.
- ✅ *D2 spot-check:* add the **same** vendor again → a clean **"already linked"** message,
  **not** a 500 / generic "Please try again".

### Check 7 — Import / Export round-trip (PLUM-10) ← *G2 + D3 fixed*
PLUM → **Import / Export**.
- ✅ **Export JSON** downloads.
- ✅ **Export Excel** downloads a real `.xlsx` and **does not 500** *(this was G2)*.
- ✅ *D3:* **Choose File** opens a file dialog, **and** dragging a file onto the dashed box selects it
  (the box highlights on drag-over). Both were dead before.
- ✅ Re-import the JSON → preview shows **0 errors** → **Confirm** → message says
  **“No records deleted”** (import is upsert-never-delete, D-14).
- ✅ A file >10 MB is **rejected** (10 MB guard).

### Check 10 — Import with a vendor reference (SC1)
Export JSON *after* check 4 (so it contains an AVL vendor reference), then re-import it.
- ✅ Preview renders and **Confirm** completes with **no 500 and no error toast**.
  *(This is the path the `SyerpPartner` → `Partner` alias fix repaired.)*

### Check 11 — Parts List refreshes without manual refresh (SC3)
Immediately after the Confirm in check 10, **do not press F5**.
- ✅ Navigate to the Parts List — it already reflects the import.
- ✅ Better: keep the Parts List visible in a second tab and watch it update on Confirm.
  *(Mechanism is pinned by `ImportExport.test.tsx`; you are confirming it's visibly wired.)*

### Check 12 — Auto part number (SC2) — **run this LAST**
Parts → **Create Part**, leave **Part Number blank**, fill only the description → Save.
- ✅ A fresh unique number is assigned. Expected **`P100011`** *(if you created no other parts;
  otherwise it is highest + 1)*.
- ✅ **No duplicate-key 500.**
- ✅ Create a second one → `P100012`. The counter does not stall or repeat.

---

### Recording the result
Tick the Status column above. If everything passes, the milestone tag is unblocked:
```bash
git tag -a v1.0 -m "Foundation + PLUM"
```
Per **D-M1-1** that tree also contains Phase 8 (v2.0) work — expected, recorded, not accidental.

## If a check fails
Bisect against the atomic Phase-7 commits (`git log --oneline`) — each fix is one commit — or
across the milestone's phase history. Record the failing flow + observations here and open a
gap-closure task rather than blocking the milestone on unrelated flows.
