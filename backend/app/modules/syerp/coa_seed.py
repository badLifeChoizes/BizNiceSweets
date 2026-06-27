"""
Standard chart-of-accounts seed.

Called from app.core.seed:run_seeds() on every application startup.
All operations are idempotent — safe to call on repeated `podman-compose up`
(T-04-02: select-before-insert pattern prevents duplicate accounts).

Seed sequence:
  1. Insert top-level accounts (parent_code = None) first; flush to get IDs.
  2. Build a code→id map from the inserted/existing top-level accounts.
  3. Insert child accounts with resolved parent_id (Pitfall 6 — parents before
     children, FK ordering).
  4. Single await db.commit() at the end (mirrors auth/seed.py pattern).

The _STANDARD_COA constant uses `parent_code` (not `parent_id`) as the raw
seed data key; the seed function resolves parent codes to DB integer IDs at
runtime so the data stays portable across environments.

Accounts: 40 entries covering 5 GAAP types (ASSET, LIABILITY, EQUITY,
REVENUE, EXPENSE), 1xxx–5xxx numbering, with manufacturing-specific accounts
(WIP, COGS sub-accounts, R&D) for the medical-device manufacturing use case.
[ASSUMED: standard US GAAP small-business CoA — see RESEARCH.md assumption A4]
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Standard Chart of Accounts data
#
# Each entry: code, name, account_type, parent_code (None = top-level).
# The seed function resolves parent_code → parent_id integer before inserting.
# Ordering: parents before children within each account-type group.
# ---------------------------------------------------------------------------

_STANDARD_COA: list[dict] = [
    # ── ASSETS (1000–1999) ─────────────────────────────────────────────────
    {"code": "1000", "name": "Assets",                      "account_type": "ASSET",     "parent_code": None},
    {"code": "1100", "name": "Current Assets",              "account_type": "ASSET",     "parent_code": "1000"},
    {"code": "1110", "name": "Cash and Cash Equivalents",   "account_type": "ASSET",     "parent_code": "1100"},
    {"code": "1120", "name": "Accounts Receivable",         "account_type": "ASSET",     "parent_code": "1100"},
    {"code": "1130", "name": "Inventory",                   "account_type": "ASSET",     "parent_code": "1100"},
    {"code": "1140", "name": "Work in Process",             "account_type": "ASSET",     "parent_code": "1100"},
    {"code": "1150", "name": "Prepaid Expenses",            "account_type": "ASSET",     "parent_code": "1100"},
    {"code": "1200", "name": "Fixed Assets",                "account_type": "ASSET",     "parent_code": "1000"},
    {"code": "1210", "name": "Equipment",                   "account_type": "ASSET",     "parent_code": "1200"},
    {"code": "1220", "name": "Accumulated Depreciation",    "account_type": "ASSET",     "parent_code": "1200"},

    # ── LIABILITIES (2000–2999) ────────────────────────────────────────────
    {"code": "2000", "name": "Liabilities",                 "account_type": "LIABILITY", "parent_code": None},
    {"code": "2100", "name": "Current Liabilities",         "account_type": "LIABILITY", "parent_code": "2000"},
    {"code": "2110", "name": "Accounts Payable",            "account_type": "LIABILITY", "parent_code": "2100"},
    {"code": "2120", "name": "Accrued Expenses",            "account_type": "LIABILITY", "parent_code": "2100"},
    {"code": "2130", "name": "Sales Tax Payable",           "account_type": "LIABILITY", "parent_code": "2100"},
    {"code": "2140", "name": "Payroll Liabilities",         "account_type": "LIABILITY", "parent_code": "2100"},
    {"code": "2200", "name": "Long-Term Liabilities",       "account_type": "LIABILITY", "parent_code": "2000"},
    {"code": "2210", "name": "Long-Term Debt",              "account_type": "LIABILITY", "parent_code": "2200"},

    # ── EQUITY (3000–3999) ─────────────────────────────────────────────────
    {"code": "3000", "name": "Equity",                      "account_type": "EQUITY",    "parent_code": None},
    {"code": "3100", "name": "Owner's Equity",              "account_type": "EQUITY",    "parent_code": "3000"},
    {"code": "3110", "name": "Capital Contributions",       "account_type": "EQUITY",    "parent_code": "3100"},
    {"code": "3120", "name": "Retained Earnings",           "account_type": "EQUITY",    "parent_code": "3100"},
    {"code": "3130", "name": "Current Year Net Income",     "account_type": "EQUITY",    "parent_code": "3100"},

    # ── REVENUE (4000–4999) ────────────────────────────────────────────────
    {"code": "4000", "name": "Revenue",                     "account_type": "REVENUE",   "parent_code": None},
    {"code": "4100", "name": "Product Sales",               "account_type": "REVENUE",   "parent_code": "4000"},
    {"code": "4110", "name": "Product Revenue",             "account_type": "REVENUE",   "parent_code": "4100"},
    {"code": "4120", "name": "Service Revenue",             "account_type": "REVENUE",   "parent_code": "4100"},
    {"code": "4200", "name": "Other Income",                "account_type": "REVENUE",   "parent_code": "4000"},
    {"code": "4210", "name": "Interest Income",             "account_type": "REVENUE",   "parent_code": "4200"},

    # ── EXPENSES (5000–5999) ───────────────────────────────────────────────
    {"code": "5000", "name": "Expenses",                    "account_type": "EXPENSE",   "parent_code": None},
    {"code": "5100", "name": "Cost of Goods Sold",          "account_type": "EXPENSE",   "parent_code": "5000"},
    {"code": "5110", "name": "Direct Materials",            "account_type": "EXPENSE",   "parent_code": "5100"},
    {"code": "5120", "name": "Direct Labor",                "account_type": "EXPENSE",   "parent_code": "5100"},
    {"code": "5130", "name": "Manufacturing Overhead",      "account_type": "EXPENSE",   "parent_code": "5100"},
    {"code": "5200", "name": "Operating Expenses",          "account_type": "EXPENSE",   "parent_code": "5000"},
    {"code": "5210", "name": "Salaries and Wages",          "account_type": "EXPENSE",   "parent_code": "5200"},
    {"code": "5220", "name": "Rent and Occupancy",          "account_type": "EXPENSE",   "parent_code": "5200"},
    {"code": "5230", "name": "Utilities",                   "account_type": "EXPENSE",   "parent_code": "5200"},
    {"code": "5240", "name": "Insurance",                   "account_type": "EXPENSE",   "parent_code": "5200"},
    {"code": "5250", "name": "Depreciation Expense",        "account_type": "EXPENSE",   "parent_code": "5200"},
    {"code": "5260", "name": "Research and Development",    "account_type": "EXPENSE",   "parent_code": "5200"},
    {"code": "5270", "name": "Marketing and Sales",         "account_type": "EXPENSE",   "parent_code": "5200"},
    {"code": "5280", "name": "General and Administrative",  "account_type": "EXPENSE",   "parent_code": "5200"},
    {"code": "5290", "name": "Professional Services",       "account_type": "EXPENSE",   "parent_code": "5200"},
]


async def seed_gl_accounts(db: "AsyncSession") -> None:
    """
    Idempotent chart-of-accounts seed.

    Inserts the _STANDARD_COA accounts into syerp_gl_account if they do not
    already exist. Safe to call on every podman-compose up (T-04-02).

    Two-pass ordering (Pitfall 6 — parents before children):
      Pass 1: insert accounts whose parent_code is None (top-level roots).
              Flush after each insert to obtain the DB-assigned integer id.
      Pass 2: insert remaining accounts, resolving parent_code → integer id
              via the code_to_id map built during Pass 1.
      Both passes use select-before-insert to skip already-present rows.

    Single await db.commit() at the end (mirrors auth/seed.py pattern).
    """
    from sqlalchemy import select

    from app.modules.syerp.models import GLAccount

    # code → integer DB id map (populated during the two passes)
    code_to_id: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Pre-populate code_to_id from rows already in the DB (re-run safety).
    # On first run this will return nothing; on subsequent runs it avoids
    # re-inserting accounts that were already seeded.
    # ------------------------------------------------------------------
    existing = await db.execute(select(GLAccount))
    for row in existing.scalars().all():
        code_to_id[row.code] = row.id

    # ------------------------------------------------------------------
    # Pass 1: top-level accounts (parent_code = None)
    # ------------------------------------------------------------------
    for entry in _STANDARD_COA:
        if entry["parent_code"] is not None:
            continue  # handled in pass 2
        if entry["code"] in code_to_id:
            continue  # already exists — idempotent skip

        account = GLAccount(
            code=entry["code"],
            name=entry["name"],
            account_type=entry["account_type"],
            parent_id=None,
            active=True,
        )
        db.add(account)
        await db.flush()  # obtain DB-assigned id before pass 2 references it
        code_to_id[entry["code"]] = account.id

    # ------------------------------------------------------------------
    # Pass 2: child accounts (parent_code is not None)
    # ------------------------------------------------------------------
    for entry in _STANDARD_COA:
        if entry["parent_code"] is None:
            continue  # already handled in pass 1
        if entry["code"] in code_to_id:
            continue  # already exists — idempotent skip

        parent_id = code_to_id.get(entry["parent_code"])
        # parent_code must resolve; the seed list is ordered parents-before-children
        # but code_to_id now includes all top-level accounts from pass 1 AND any
        # already-seeded rows loaded above, so any missing parent indicates a data
        # error in _STANDARD_COA rather than an ordering issue.
        account = GLAccount(
            code=entry["code"],
            name=entry["name"],
            account_type=entry["account_type"],
            parent_id=parent_id,
            active=True,
        )
        db.add(account)
        await db.flush()  # keep code_to_id accurate for any deeper nesting
        code_to_id[entry["code"]] = account.id

    # Single commit at the end of the function (mirrors auth/seed.py line 146)
    await db.commit()
