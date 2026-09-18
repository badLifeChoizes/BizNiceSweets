# ABOUTME: FLAN task-key generation — the next `<PREFIX>-<n>` key for a project,
# ABOUTME: found by casting the numeric suffix to Numeric (never Integer) after a
# ABOUTME: regex filter, so PRJ-9 → PRJ-10 and a 10-digit suffix cannot 500 the
# ABOUTME: suite permanently (D-P8-6, the PLUM-01 Phase-7 defect 7562a02).
"""FLAN task-key generation (FLAN-01.3, D-P8-6, D-V5P1-7).

A task key is `<PREFIX>-<n>`, unique within its project
(`uq_flan_task_project_key`) and unpadded: `PRJ-1`, `PRJ-9`, `PRJ-10` — **not**
`PRJ-0001` (D-V5P1-7). Unlike the platform's document series (`QUOTE-0001`,
`SO-0001`, `WO-0001`) a task key is a handle people type and say aloud; the
SRD's own verification names the literal `PRJ-9 → PRJ-10` and both prototypes
agree (`flan/app/schedule_gate-v45.html:3205`, `return pre+'-'+(max+1)`).

This is a port of `generate_quote_number` (crumb/service/quotes.py) with three
deliberate differences:

  1. **It is project-scoped.** The search is filtered by
     `Task.project_id == project_id` and uses the *project's stored*
     `key_prefix` (D-V5P1-2) rather than a literal series name. Two projects may
     each hold a `PRJ-1`; each numbers independently, and the uniqueness
     constraint is `(project_id, key)`, not `key`.
  2. **The cast target is `Numeric`, NOT `Integer`.** This is the single most
     important line in the file. `flan_task.key` is `String(20)` with no format
     constraint, so `PRJ-9999999999` is a legal key whose suffix matches the
     regex but overflows `int4`; an `Integer` cast raises "value out of range
     for type integer" and makes **every** auto-numbered create in that project
     500 *permanently*, until the offending row is deleted by hand. That is
     exactly the PLUM-01 Phase-7 defect (`7562a02`), which D-P8-6 exists to stop
     recurring. `Numeric` cannot overflow for any 20-character digit string.
  3. **The regex filter runs BEFORE the cast.** A bare cast over
     `LIKE '<PREFIX>-%'` would throw on a non-numeric key such as `PRJ-DRAFT`,
     so `^{prefix}-[0-9]+$` (Postgres `~`) narrows the rows first and the cast
     only ever sees digits. Interpolating `prefix` into that regex is safe
     because a key_prefix can only be one of two things, and both are validated
     against `KEY_PREFIX_PATTERN` (`^[A-Za-z][A-Za-z0-9]{0,9}$`, flan/schemas.py):
     a client-supplied prefix, checked by the schema, or one derived from the
     project name by `projects.py::derive_key_prefix`, which falls back to `PRJ`
     precisely so a name like "3M Widgets" cannot yield a regex-unsafe (or even
     merely non-conforming) prefix. No regex metacharacter survives that shape.

Ordering note (D-V5P1-7 consequence): a plain string sort over unpadded keys
puts `PRJ-10` *before* `PRJ-9`. Nothing order-related is exported from this
module; any list that orders by key — `tasks.py::list_tasks`, the board — must
order on the **numeric suffix**, exactly as the `ORDER BY` below does.

Uniqueness is the database's job: `uq_flan_task_project_key` is the
authoritative backstop and `create_task` retries a bounded number of times on
that specific IntegrityError. This module is a best-effort generator called
under the project row lock.

Models are imported lazily inside the function (house idiom — mirrors
service/_common.py and crumb/service/quotes.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Numeric, cast, func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _next_key(prefix: str, existing_max: int | None) -> str:
    """
    Compute the next task key from the project's current highest numeric suffix.

    Pure (no DB) so the digit-boundary guarantee is unit-testable in isolation —
    the `_next_quote_number` / `_percent` precedent. Returns `<PREFIX>-1` when
    the project holds no keys in the series yet, otherwise the given suffix + 1.

    **Unpadded** (D-V5P1-7): `_next_key("PRJ", 9)` is `"PRJ-10"`, not
    `"PRJ-0010"`. Python integers are arbitrary-precision, so a suffix that
    overflows `int4` (the reason the SQL cast below is `Numeric`) increments
    here without special handling: 9999999999 → `PRJ-10000000000`.
    """
    if existing_max is None:
        return f"{prefix}-1"
    return f"{prefix}-{existing_max + 1}"


async def generate_task_key(db: AsyncSession, project_id: str, key_prefix: str) -> str:
    """
    Generate the next task key for one project (FLAN-01.3, D-P8-6).

    Finds the current highest *numeric* suffix among that project's
    strictly-numeric `<PREFIX>-<n>` keys and delegates the increment to the pure
    `_next_key` helper, so `PRJ-9` yields `PRJ-10` rather than the lexicographic
    sibling a `MAX(key)` string aggregate would return (`PRJ-9` again — a
    duplicate key, D-P8-6).

    Three details carry the guarantee, each explained at module level:

      * the search is scoped to `project_id` and to this project's stored
        `key_prefix`, so projects number independently;
      * the `~ '^{prefix}-[0-9]+$'` filter runs **before** the cast, so a
        non-numeric key such as `PRJ-DRAFT` is excluded instead of throwing;
      * the cast target is **`Numeric`, never `Integer`** — a legal 10-digit
        suffix overflows `int4` and would 500 every subsequent create in the
        project permanently (the PLUM-01 defect `7562a02`).

    `func.substring(Task.key, len(key_prefix) + 2)` skips the prefix and its
    hyphen: Postgres `substring` is 1-indexed, so with a 3-character prefix the
    first digit of `PRJ-10` sits at position 5.

    Called under the project row lock taken by `create_task`; the DB unique
    constraint `uq_flan_task_project_key` remains the authoritative backstop.
    """
    from app.modules.flan.models import Task

    suffix_start = len(key_prefix) + 2
    result = await db.execute(
        select(Task.key)
        .where(Task.project_id == project_id)
        .where(Task.key.op("~")(rf"^{key_prefix}-[0-9]+$"))
        .order_by(cast(func.substring(Task.key, suffix_start), Numeric).desc())
        .limit(1)
    )
    max_key: str | None = result.scalar()
    existing_max = int(max_key.split("-", 1)[1]) if max_key is not None else None
    return _next_key(key_prefix, existing_max)
