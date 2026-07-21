"""SYERP service — double-entry journal posting, reversal, balances, and account register."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.modules.syerp.models import (
        GLAccount,
        JournalEntry,
        JournalLine,
    )
    from app.modules.syerp.schemas import (
        AccountRegisterRead,
        JournalEntryRead,
    )

from app.modules.syerp.service._common import _COST_QUANTUM

# ---------------------------------------------------------------------------
# Journal-entry balance helpers (Phase 9a — GL posting engine, SYERP-12)
# ---------------------------------------------------------------------------
#
# Double-entry invariant (D-P9a): a journal entry posts only when its debits
# equal its credits. These helpers are PURE (no DB, no float, no FastAPI) so the
# balance core is unit-testable in isolation; the service layer raises HTTP 422
# on top of `_je_is_balanced`. All money is Decimal quantized to scale 6 to match
# the Numeric(18,6) amount columns exactly (D-11) — a float sum could drift a
# cent off a "balanced" entry and silently corrupt the ledger.
#
# Lines are duck-typed: each may be a mapping ({"debit": ..., "credit": ...}) or
# any object exposing `.debit`/`.credit`. Exactly one side is set per line; the
# other is None (or 0). Amounts are quantized to `_COST_QUANTUM` before summing.


def _je_side(line: object, side: str) -> Decimal:
    """
    Read one side (``"debit"`` or ``"credit"``) off a journal line.

    Accepts both a mapping (``line["debit"]``) and an attribute-bearing object
    (``line.debit``). A missing / ``None`` value means "not this side" and reads
    as ``Decimal("0")``. The raw value is coerced through ``str`` before
    ``Decimal`` so an accidental float can never seed float drift into the sum.
    """
    if isinstance(line, Mapping):
        value = line.get(side)
    else:
        value = getattr(line, side, None)
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP)


def _je_totals(lines: Iterable[object]) -> tuple[Decimal, Decimal]:
    """
    Sum (Σdebits, Σcredits) across journal lines, quantized to scale 6 (D-11).

    PURE (no DB, no float). Each line contributes its debit to the first total
    and its credit to the second; an unset side contributes zero.
    """
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for line in lines:
        total_debit += _je_side(line, "debit")
        total_credit += _je_side(line, "credit")
    return (
        total_debit.quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP),
        total_credit.quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP),
    )


def _je_is_balanced(lines: Iterable[object]) -> bool:
    """
    Return whether a journal entry is a valid, balanced double-entry (D-P9a).

    Balanced means ALL of:
      * at least two lines (a single-sided entry cannot balance),
      * every line sets EXACTLY ONE of debit/credit (the other None/absent),
      * every set amount is >= 0 (no negative sides — a negative debit is a
        credit and must be expressed as one), and
      * Σdebits == Σcredits (quantized to scale 6).

    PURE (no DB, no float, no FastAPI). The service layer maps a ``False`` here
    to HTTP 422; this helper only decides truth.
    """
    line_list = list(lines)
    if len(line_list) < 2:
        return False
    for line in line_list:
        debit = _je_side(line, "debit")
        credit = _je_side(line, "credit")
        if debit < 0 or credit < 0:
            return False
        # Exactly one side must be non-zero (XOR): never both, never neither.
        if (debit != 0) == (credit != 0):
            return False
    total_debit, total_credit = _je_totals(line_list)
    return total_debit == total_credit


def _reverse_lines(lines: Iterable[object]) -> list[dict]:
    """
    Reverse a set of journal lines by swapping debit <-> credit (D-P9a).

    Returns new line dicts (``{"debit": ..., "credit": ...}``) — the source lines
    are never mutated. A reversal of a balanced entry is itself balanced (the two
    column sums merely trade places), which is the property the audit-safe void /
    correction path relies on. Amounts are quantized to scale 6 (D-11).
    """
    reversed_lines: list[dict] = []
    for line in lines:
        reversed_lines.append(
            {
                "debit": _je_side(line, "credit"),
                "credit": _je_side(line, "debit"),
            }
        )
    return reversed_lines


# ---------------------------------------------------------------------------
# GL posting engine — journal entries, reversals, register (Phase 9a, SYERP-12)
# ---------------------------------------------------------------------------
#
# Double-entry postings (D-P9a): an entry posts only when it is balanced
# (Σdebit == Σcredit, >= 2 lines, exactly one non-negative side per line). The
# pure _je_is_balanced helper decides truth; the service maps a False to HTTP
# 422. Entries and their lines are APPEND-ONLY (mirrors InventoryTxn) — never
# edited or deleted. A correction is a reversing entry (reverse_journal_entry)
# that swaps every debit/credit and links back via reversal_of_id, leaving the
# original untouched (immutability).
#
# Balances are DERIVED, never stored (D-P8-4): an account's balance is the SUM
# of its lines' debits minus credits (derive_account_balance / the register's
# running balance), mirroring the on-hand derivation (service.py post_receipt).
# All money is Decimal (D-11). The models declare NO ORM relationships (async
# MissingGreenlet avoidance), so child lines are loaded with explicit ordered
# SELECTs, exactly like the PurchaseOrder line loaders above.


def _je_account_id(line: object) -> int:
    """Read `account_id` off a journal line (mapping or attribute-bearing object)."""
    if isinstance(line, Mapping):
        return line.get("account_id")
    return getattr(line, "account_id", None)


async def _require_gl_account(db: AsyncSession, account_id: int) -> GLAccount:
    """
    Load a GL account by id, raising HTTP 404 if it does not exist.

    Called for every posting line before any write so an unknown account fails
    the whole entry (no partial posting) with a clean 404 (mirrors get_item).
    """
    from app.modules.syerp.models import GLAccount

    result = await db.execute(select(GLAccount).where(GLAccount.id == account_id))
    account = result.scalars().first()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GL account {account_id} not found.",
        )
    return account


async def _get_journal_entry_row(db: AsyncSession, entry_id: str) -> JournalEntry:
    """Load a JournalEntry ORM row by id, raising HTTP 404 if missing."""
    from app.modules.syerp.models import JournalEntry

    result = await db.execute(select(JournalEntry).where(JournalEntry.id == entry_id))
    entry = result.scalars().first()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Journal entry {entry_id} not found.",
        )
    return entry


async def _load_journal_lines(db: AsyncSession, entry_id: str) -> list[JournalLine]:
    """Return an entry's lines ordered by line_no (no ORM relationship — Pitfall 2)."""
    from app.modules.syerp.models import JournalLine

    result = await db.execute(
        select(JournalLine)
        .where(JournalLine.entry_id == entry_id)
        .order_by(JournalLine.line_no)
    )
    return list(result.scalars().all())


def _je_to_read(
    entry: JournalEntry, lines: Iterable[JournalLine]
) -> JournalEntryRead:
    """Assemble a JournalEntryRead from a JournalEntry ORM row and its lines."""
    from app.modules.syerp.schemas import JournalEntryRead, JournalLineRead

    return JournalEntryRead(
        id=entry.id,
        entry_date=entry.entry_date,
        memo=entry.memo,
        source_type=entry.source_type,
        source_id=entry.source_id,
        reversal_of_id=entry.reversal_of_id,
        actor_id=entry.actor_id,
        created_at=entry.created_at,
        lines=[JournalLineRead.model_validate(line) for line in lines],
    )


async def post_journal_entry(
    db: AsyncSession,
    *,
    entry_date: date,
    memo: str | None,
    lines: Iterable[object],
    actor_id: str,
    source_type: str | None = None,
    source_id: str | None = None,
    reversal_of_id: str | None = None,
    commit: bool = True,
) -> JournalEntryRead:
    """
    Post a balanced double-entry journal entry (Phase 9a, SYERP-12 AC1).

    Validates the payload with the PURE _je_is_balanced helper (>= 2 lines,
    exactly one non-negative side per line, Σdebit == Σcredit at scale 6 — D-11)
    and rejects an unbalanced / single-line / bad-line entry with HTTP 422. Every
    line's `account_id` is resolved against syerp_gl_account BEFORE any write; an
    unknown account fails the whole entry with 404 (no partial posting). Lines are
    persisted in input order with `line_no` starting at 1; the unset side of each
    line is stored NULL (exactly one column is non-null per line).

    `commit` (default True) follows the post_receipt flush-vs-commit pattern: a
    standalone posting owns its commit (True); the receipt auto-post path (Task 8)
    passes commit=False so the entry + lines share the receipt's single atomic
    transaction — flushed (so the PK/timestamp exist) but committed by the caller.

    `source_type` / `source_id` are the soft polymorphic link back to the
    originating document; `reversal_of_id` is set by reverse_journal_entry. The
    entry and its lines are APPEND-ONLY thereafter (D-P9a) — corrections are
    reversing entries, never edits. Returns the posted entry as a JournalEntryRead
    with its lines nested.
    """
    from app.modules.syerp.models import JournalEntry, JournalLine

    line_list = list(lines)

    # Balance guard (D-P9a): the pure helper decides truth, the service maps to 422.
    if not _je_is_balanced(line_list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Journal entry is not a balanced double-entry: it needs at least "
                "two lines, each setting exactly one non-negative debit or credit, "
                "with total debits equal to total credits."
            ),
        )

    # Resolve every account (404 on unknown) BEFORE any write — no partial posting.
    for line in line_list:
        await _require_gl_account(db, _je_account_id(line))

    entry = JournalEntry(
        entry_date=entry_date,
        memo=memo,
        source_type=source_type,
        source_id=source_id,
        reversal_of_id=reversal_of_id,
        actor_id=actor_id,
    )
    db.add(entry)
    await db.flush()  # materialize entry.id for the child lines' FK.

    for line_no, line in enumerate(line_list, start=1):
        debit = _je_side(line, "debit")
        credit = _je_side(line, "credit")
        db.add(
            JournalLine(
                entry_id=entry.id,
                account_id=_je_account_id(line),
                line_no=line_no,
                # Exactly one side is non-zero (enforced above); store the other NULL.
                debit=debit if debit != 0 else None,
                credit=credit if credit != 0 else None,
            )
        )

    # commit=True: standalone posting owns the commit. commit=False: the caller
    # (receipt auto-post) owns one atomic commit; flush so rows/PKs exist for the
    # read-back below without ending the transaction (post_receipt pattern).
    if commit:
        await db.commit()
    else:
        await db.flush()

    entry_lines = await _load_journal_lines(db, entry.id)
    return _je_to_read(entry, entry_lines)


async def reverse_journal_entry(
    db: AsyncSession,
    entry_id: str,
    actor_id: str,
    memo: str | None = None,
) -> JournalEntryRead:
    """
    Reverse an existing journal entry by posting its mirror image (AC2, D-P9a).

    Loads the original (404 if missing) and posts a NEW entry whose lines swap
    every debit/credit (via the pure _je_side amount swap that _reverse_lines
    performs), preserving each line's account, dated today, and linked back with
    `reversal_of_id = entry_id`. The reversal of a balanced entry is itself
    balanced, so it re-uses post_journal_entry (same 422 / 404 guards).

    The original entry is NEVER edited or deleted — immutability is the audit
    guarantee (a correction is a reversing entry, not a mutation). `memo` overrides
    the reversing entry's memo; when omitted a default derived from the original id
    is used. Returns the new reversing entry as a JournalEntryRead.

    Double-reversal is REFUSED (HTTP 409, Phase 9a verify M2): a posted entry may
    be reversed at most once, and a reversal is not itself reversible. Reversing
    the same entry twice would apply its opposite swing twice, silently diverging
    the DERIVED GL control-account balance from the physical inventory / moving-
    average valuation it mirrors (e.g. a receipt's 1130/2150 legs would net to a
    phantom −qty×cost while stock is still on hand). A correction beyond one
    reversal must re-post a fresh entry, never reverse again.
    """
    from app.modules.syerp.models import JournalEntry

    original = await _get_journal_entry_row(db, entry_id)  # 404 if the original is missing.

    # Guard A: a reversal is not itself reversible.
    if original.reversal_of_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Journal entry {entry_id} is itself a reversal "
                f"(of {original.reversal_of_id}) and cannot be reversed again."
            ),
        )
    # Guard B: an entry may be reversed at most once.
    existing_reversal = (
        await db.execute(
            select(JournalEntry.id).where(JournalEntry.reversal_of_id == entry_id)
        )
    ).scalars().first()
    if existing_reversal is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Journal entry {entry_id} has already been reversed by "
                f"{existing_reversal}."
            ),
        )

    original_lines = await _load_journal_lines(db, entry_id)

    # _reverse_lines swaps debit<->credit (pure amount swap, no account_id); zip the
    # swapped amounts back onto each original line's account to rebuild the legs.
    swapped = _reverse_lines(original_lines)
    reversed_lines = [
        {"account_id": line.account_id, **amounts}
        for line, amounts in zip(original_lines, swapped)
    ]

    return await post_journal_entry(
        db,
        entry_date=date.today(),
        memo=memo or f"Reversal of journal entry {entry_id}",
        lines=reversed_lines,
        actor_id=actor_id,
        reversal_of_id=entry_id,
        commit=True,
    )


async def list_journal_entries(
    db: AsyncSession,
    source_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[JournalEntryRead]:
    """
    Return journal entries (newest-first), optionally filtered (AC1 query side).

    Filters (all optional): `source_type` restricts to auto-posted entries of a
    given kind (e.g. inventory receipts); `date_from` / `date_to` bound the
    entry_date range (inclusive). Ordered by entry_date DESC then created_at DESC
    for a stable tie-break. Lines are fetched in ONE query over all returned entry
    ids and grouped in memory (no per-entry N+1), mirroring list_pos.
    """
    from app.modules.syerp.models import JournalEntry, JournalLine

    stmt = select(JournalEntry)
    if source_type is not None:
        stmt = stmt.where(JournalEntry.source_type == source_type)
    if date_from is not None:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    stmt = stmt.order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())

    result = await db.execute(stmt)
    entries = list(result.scalars().all())
    if not entries:
        return []

    entry_ids = [entry.id for entry in entries]
    lines_result = await db.execute(
        select(JournalLine)
        .where(JournalLine.entry_id.in_(entry_ids))
        .order_by(JournalLine.line_no)
    )
    lines_by_entry: dict[str, list[JournalLine]] = {eid: [] for eid in entry_ids}
    for line in lines_result.scalars().all():
        lines_by_entry[line.entry_id].append(line)

    return [_je_to_read(entry, lines_by_entry[entry.id]) for entry in entries]


async def get_journal_entry(db: AsyncSession, entry_id: str) -> JournalEntryRead:
    """
    Load a journal entry (header + nested lines) by id (404 if missing).
    """
    entry = await _get_journal_entry_row(db, entry_id)
    lines = await _load_journal_lines(db, entry_id)
    return _je_to_read(entry, lines)


async def latest_journal_entry_id_for_source(
    db: AsyncSession, source_type: str, source_id: str
) -> str | None:
    """
    Return the id of the MOST RECENT journal entry auto-posted for a source
    document, or None if none was posted (Phase 9a verify M5).

    The receipt path posts one JE per receipt, all source-linked to the same PO
    line (source_id == line.id); partial receipts therefore accumulate several.
    The audit row for the receipt just processed needs the entry this request
    posted — the newest by created_at. Returns None when the source posted no JE
    at all (a zero-cost receipt skips the GL post), so the caller omits the
    gl.journal_posted audit row rather than record a phantom, untraceable one.
    """
    from app.modules.syerp.models import JournalEntry

    result = await db.execute(
        select(JournalEntry.id)
        .where(
            JournalEntry.source_type == source_type,
            JournalEntry.source_id == source_id,
        )
        .order_by(JournalEntry.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def derive_account_balance(db: AsyncSession, account_id: int) -> Decimal:
    """
    Derive a GL account's balance as Σdebit − Σcredit (D-P8-4 — never stored).

    A single aggregate scalar over all of the account's lines (no date filter),
    mirroring the on-hand derivation pattern (func.sum ... scalar() or 0). Each
    side is COALESCEd to zero INDEPENDENTLY: an account posted on only one side
    (e.g. a control account that is only ever credited) has NULL for the empty
    side, and `Σdebit − NULL` would be NULL in SQL — coalescing each sum first
    keeps the balance correct (D-P8-4). An account with no postings coalesces to
    0 − 0 == 0. Exact fixed-point (never float — D-11).
    """
    from app.modules.syerp.models import JournalLine

    result = await db.execute(
        select(
            func.coalesce(func.sum(JournalLine.debit), 0)
            - func.coalesce(func.sum(JournalLine.credit), 0)
        ).where(JournalLine.account_id == account_id)
    )
    return result.scalar() or Decimal("0")


async def get_account_register(
    db: AsyncSession,
    account_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
) -> AccountRegisterRead:
    """
    Build an account register for one GL account over a date range (AC1).

    404s if the account is unknown. `opening_balance` is the derived Σdebit −
    Σcredit of every posting BEFORE `date_from` (D-P8-4 — nothing is stored); the
    ordered `rows` are that account's postings within [date_from, date_to]
    (inclusive), each carrying a Python-computed running balance
    (opening + Σ(debit − credit) up to and including that row); `closing_balance`
    is the final running balance. When a bound is None it is simply not applied
    (open-ended period). All arithmetic is Decimal — exact, never float (D-11).
    """
    from app.modules.syerp.models import JournalEntry, JournalLine

    account = await _require_gl_account(db, account_id)  # 404 if unknown.

    # opening_balance = derived Σdebit − Σcredit of postings strictly BEFORE the
    # window (D-P8-4). NULL (no prior postings) coalesces to zero.
    if date_from is not None:
        opening_stmt = (
            select(
                func.coalesce(func.sum(JournalLine.debit), 0)
                - func.coalesce(func.sum(JournalLine.credit), 0)
            )
            .select_from(JournalLine)
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
            .where(
                JournalLine.account_id == account_id,
                JournalEntry.entry_date < date_from,
            )
        )
        opening_balance: Decimal = (await db.execute(opening_stmt)).scalar() or Decimal("0")
    else:
        opening_balance = Decimal("0")

    rows_stmt = (
        select(
            JournalEntry.entry_date,
            JournalEntry.id,
            JournalEntry.memo,
            JournalLine.debit,
            JournalLine.credit,
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(JournalLine.account_id == account_id)
        .order_by(
            JournalEntry.entry_date,
            JournalEntry.created_at,
            JournalLine.line_no,
        )
    )
    if date_from is not None:
        rows_stmt = rows_stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        rows_stmt = rows_stmt.where(JournalEntry.entry_date <= date_to)

    from app.modules.syerp.schemas import AccountRegisterRead, AccountRegisterRow

    result = await db.execute(rows_stmt)
    running_balance = opening_balance
    rows: list[AccountRegisterRow] = []
    for entry_date_, entry_id_, memo_, debit_, credit_ in result:
        running_balance = running_balance + (debit_ or Decimal("0")) - (credit_ or Decimal("0"))
        rows.append(
            AccountRegisterRow(
                entry_date=entry_date_,
                entry_id=entry_id_,
                memo=memo_,
                debit=debit_,
                credit=credit_,
                running_balance=running_balance,
            )
        )

    return AccountRegisterRead(
        account_id=account.id,
        account_code=account.code,
        account_name=account.name,
        opening_balance=opening_balance,
        closing_balance=running_balance,
        rows=rows,
    )
