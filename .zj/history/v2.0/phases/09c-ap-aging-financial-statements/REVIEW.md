# Review: Phase 09c — AP aging + financial statements (SYERP), 81c2256..226d1b8
Date: 2026-07-12

Scope: `git diff 81c2256..226d1b8 -- backend/ frontend/`. Reviewed service report
functions, migration 0011, router endpoints, schemas, and the bill-date wiring;
cross-read `post_bill`, `record_payment`, the bill FSM, and the COA seed.

## Summary
No blockers, no majors. The SC2 tie-out is structurally sound: 2110 is written only by
`post_bill` (credit at `bill.bill_date`) and `record_payment` (debit at `payment_date`),
the aging subledger ages on those same two dates, the bill FSM is draft→posted→paid with
no reversal/void path, and every derived sum coalesces each side independently. Findings
below are latent/cosmetic.

## Findings

### 1. [minor] Balance-sheet computed 3130 line double-counts if account 3130 ever carries a posting
- **Where:** `backend/app/modules/syerp/service.py:3735-3812` (`balance_sheet`)
- **Failure:** The main query filters `account_type in (ASSET,LIABILITY,EQUITY)` and
  inner-joins `JournalLine`, so it includes 3130 the moment 3130 has any journal line.
  The function then *unconditionally* appends a second, computed 3130 "Current Year Net
  Income" row and adds `net_income` into `total_equity`. Scenario: a user posts a manual
  JE to 3130 (nothing forbids posting to that EQUITY leaf via `post_journal_entry`); the
  balance sheet then renders two rows both labelled `3130`. The accounting identity still
  holds (`in_balance` cannot be driven false — it is a mathematical consequence of the
  ledger balancing plus `net_income = R − E`), so this is presentation duplication, not a
  balance break, and there is no code path today that posts to 3130 (opening balances use
  a separate equity account). Latent.
- **Fix:** Exclude 3130 from the main query (`GLAccount.code != "3130"`), or skip the
  computed line when ledger 3130 is non-empty — so exactly one 3130 row is ever emitted.

### 2. [minor] Computed "Current Year Net Income" is all-time R−E, not fiscal-year-bounded
- **Where:** `backend/app/modules/syerp/service.py:3776-3801`
- **Failure:** `net_income` sums REVENUE/EXPENSE over `entry_date <= as_of` from
  beginning-of-time with no lower fiscal-year bound. With no closing entries this is
  correct for the tie-out today (retained earnings is empty, so all-time net income is the
  only figure that balances), but once the ledger spans more than one fiscal year the
  line labelled "Current Year Net Income" will overstate the current year by all prior
  years' cumulative P&L. Balance still ties; the label is wrong.
- **Fix:** When fiscal-year closing lands, bound this to the current fiscal year and move
  prior-year P&L to retained earnings; until then, document that 3130 == cumulative.

## Questions

- **Pre-dated (backdated) payment tie-out** — `record_payment` does not validate
  `payment_date >= bill_date`, and `create_bill` accepts any `bill_date`. For a bill dated
  2026-07-10 paid on 2026-07-01, an `ap_aging_report(as_of=2026-07-05)` excludes the bill
  (`bill_date > as_of`) while the payment's 2110 debit (`entry_date=2026-07-01`) is inside
  the control window → `control_balance` negative, `grand_total` 0, `in_balance` False.
  This appears to be a *correct* reflection of a genuinely anomalous ledger state (AP
  carries a debit balance because cash left before the invoice was booked), not a report
  bug. Confirm the product intends to surface it as out-of-balance rather than reject the
  data-entry order at write time. (Build's own `## Noticed` flagged this; I concur it is
  low severity.)
