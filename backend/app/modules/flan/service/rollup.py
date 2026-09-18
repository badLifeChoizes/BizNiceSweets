# ABOUTME: The FLAN phase rollup — a phase's start date, due date and % complete
# ABOUTME: derived from its tasks on every read (D-V5-1, FLAN-01.2), in ONE
# ABOUTME: grouped query for a whole batch of phases. Nothing here is ever
# ABOUTME: written to a column: flan_phase has no such columns to write to.
"""Phase-derived dates and % complete (FLAN-01.2, D-V5-1).

**This is the property FLAN-01.2 exists to guarantee.** A phase's start date,
due date and % complete are *derived from its tasks* — earliest task start,
latest task due, and the share of its tasks in status ``Done`` — and are never
hand-set. `flan_phase` carries no `start_date`, `due_date` or `percent_complete`
column (see flan/models.py::Phase), so "never hand-set" is structural rather
than a rule someone has to remember, and **nothing in this module ever writes
these values to any column**. They are computed per read, here.

One public function, `phase_rollups`, answers a whole batch of phases with ONE
grouped query. Callers (list_phases) must batch: a query per phase is an N+1
defect, and the phase list is the hottest read in the suite.

Two behaviours are deliberate and easy to misread:

  * **A phase with no tasks is absent from the grouped result set.** SQL
    `GROUP BY` produces no row for a group with no rows, so an id the caller
    asked about that never comes back from the query *is* the empty-phase case:
    no dates, `0.00`, zero counts. It is filled in by an explicit named branch
    below rather than by a `dict.get(..., default)`, so the empty-phase case is
    a decision the code states, not a shape that happens to fall out. There is
    consequently no division by zero to guard — the zero branch never reaches
    `_percent`.
  * **SQL `MIN`/`MAX` skip NULLs.** A task with no `start_date` contributes
    nothing to the phase's derived start; a phase whose tasks *all* lack dates
    reports no dates at all while still reporting a real percentage from its
    real task counts. **This is intended**: undated tasks are still work, they
    are just not scheduled work, so they move the percentage and leave the
    dates alone.

`percent_complete` is a `Decimal` quantized to `0.01` — never a float (house
rule D-11, no float across the wire). `PhaseRead` (flan/schemas.py) formats it
to a 2dp string on the way out; this layer hands it the Decimal.

`PhaseRollup` is a plain frozen dataclass, not a Pydantic model: it is an
internal service type consumed by the phase service, and the wire type is
`PhaseRead`.

Models are imported lazily inside the function (house idiom — mirrors
service/_common.py and crumb/service/quotes.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class PhaseRollup:
    """
    The three derived phase values plus the counts they were derived from.

    Frozen because it is a computed read-model: there is no column behind any of
    these fields, so mutating one would mean nothing. `derived_*` names the
    fields as derived at every point of use, matching `PhaseRead`'s wire names.

    task_count / done_count are carried alongside the percentage so a caller (or
    a reviewer of a surprising percentage) can see the numerator and denominator
    without a second query.
    """

    derived_start_date: date | None
    derived_due_date: date | None
    percent_complete: Decimal
    task_count: int
    done_count: int


#: The rollup of a phase with **no tasks** (FLAN-01.2: "a phase with no tasks
#: reports no dates and 0%"). This is the case a happy-path fixture will not
#: have, so it is named here rather than being spelled inline: no dates, an
#: explicit `0.00` (not a bare `0`, and not a float), and zero counts. Safe to
#: share as a module constant because PhaseRollup is frozen.
NO_TASKS = PhaseRollup(
    derived_start_date=None,
    derived_due_date=None,
    percent_complete=Decimal("0.00"),
    task_count=0,
    done_count=0,
)


def _percent(done: int, total: int) -> Decimal:
    """
    Compute a phase's % complete as a Decimal quantized to 0.01.

    Pure (no DB) so the arithmetic is unit-testable in isolation — the
    `_next_quote_number` precedent (crumb/service/quotes.py).

    `total` is never 0 here: a phase with no tasks never reaches this function,
    it is answered by the NO_TASKS constant above, so there is no division to
    guard. Decimal division and ROUND_HALF_UP quantization (never float
    arithmetic, D-11) give 1/3 → 33.33, 2/3 → 66.67, 3/3 → 100.00.
    """
    return (Decimal(done) / Decimal(total) * 100).quantize(Decimal("0.01"), ROUND_HALF_UP)


async def phase_rollups(
    db: AsyncSession, phase_ids: Sequence[str]
) -> dict[str, PhaseRollup]:
    """
    Derive dates and % complete for a batch of phases (FLAN-01.2, D-V5-1).

    **Every requested phase id is a key in the returned dict**, so a caller can
    index it without a fallback. Ids the grouped query returns get their real
    aggregates; ids it does not return have no tasks at all and get NO_TASKS
    (dates None, `0.00`, zero counts) from the explicit branch below.

    ONE grouped query for the whole batch — `MIN(start_date)`, `MAX(due_date)`,
    `COUNT(*)` and `COUNT(*) FILTER (WHERE status = 'Done')` grouped by
    `phase_id`. Callers listing a project's phases must pass every phase id in
    one call; a call per phase is an N+1.

    Note that SQL `MIN`/`MAX` **skip NULLs**: undated tasks are counted in
    task_count and move the percentage, but contribute nothing to the derived
    dates, so a phase whose tasks all lack dates reports no dates and a real
    percentage. That is intended, not an edge case to fix.

    Writes nothing. There is no column to write these to (Phase has none).
    """
    from app.modules.flan.models import Task

    requested = list(dict.fromkeys(phase_ids))
    if not requested:
        return {}

    result = await db.execute(
        select(
            Task.phase_id,
            func.min(Task.start_date),
            func.max(Task.due_date),
            func.count(),
            func.count().filter(Task.status == "Done"),
        )
        .where(Task.phase_id.in_(requested))
        .group_by(Task.phase_id)
    )

    rollups: dict[str, PhaseRollup] = {}
    for phase_id, min_start, max_due, total, done in result.all():
        rollups[phase_id] = PhaseRollup(
            derived_start_date=min_start,
            derived_due_date=max_due,
            percent_complete=_percent(done, total),
            task_count=total,
            done_count=done,
        )

    # The empty-phase case, stated explicitly: a phase with no tasks produces no
    # GROUP BY row, so any requested id missing from the result set has zero
    # tasks and reports no dates and 0.00% (FLAN-01.2). Deliberately a named
    # branch rather than a `dict.get(id, ...)` at the call site — this is the
    # decision the crux turns on, and it should be visible and breakable here.
    for phase_id in requested:
        if phase_id not in rollups:
            rollups[phase_id] = NO_TASKS

    return rollups
