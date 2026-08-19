# ABOUTME: SERVICE-path port of verify_flan.py scenarios (A0)-(A4), (B), (C), (D) and (F) (NFR-5).
# ABOUTME: Drives the REAL flan service + REAL schemas on the migrated test DB — the phase rollup crux.
"""
FLAN phase-rollup crux — ported from ``backend/scripts/verify_flan.py`` scenarios
(A0)-(A4) the derived dates and % complete, (B) numeric-safe task keys, (C)
``due < start`` / ``due == start``, (D) roster removal and (F) phase-delete
cascade (NFR-5).

WHY THIS EXISTS (FLAN-01.2 / D-V5-1, the SRD's named verification):
  A FLAN phase carries **no** ``start_date``, ``due_date`` or
  ``percent_complete`` column. Those three values are derived on every read from
  the phase's tasks — earliest task start, latest task due, and the share of its
  tasks in status ``Done`` — and are never hand-set. The load-bearing
  behaviours ported here:

    * EMPTY PHASE (FLAN-01.2, the case a happy-path fixture will not have): a
      phase with zero tasks reports no dates, ``0.00``% and zero counts. SQL
      ``GROUP BY`` produces no row for a group with no rows, so the empty phase
      is answered by an explicit named branch in ``service/rollup.py`` — the one
      branch this whole crux turns on.
    * MIN/MAX, NOT FIRST/LAST (FLAN-01.2): the derived start is the EARLIEST
      task start and the derived due the LATEST task due, whatever order the
      tasks were inserted in.
    * PERCENT IS DECIMAL (D-11, no float across the wire): 0/3 → ``0.00``,
      1/3 → ``33.33``, 3/3 → ``100.00``, quantized ROUND_HALF_UP.
    * MIN/MAX SKIP NULLS (FLAN-01.2): an undated task is still work — it raises
      ``task_count`` and moves the percentage but contributes nothing to the
      derived dates. A phase whose tasks ALL lack dates therefore reports no
      dates and a REAL percentage, which is emphatically not the empty-phase
      shape.
    * NOTHING IS STORED (D-V5-1, the structural half of "never hand-set"):
      ``flan_phase`` has no column named ``start_date``, ``due_date`` or
      ``percent_complete`` to write these to.

THE NON-VACUITY POINT (A0 — read this before editing):
  The empty-phase assertion MUST be made inside a BATCH whose FIRST member is a
  NON-empty phase. A solo ``phase_rollups(db, [empty_phase_id])`` is vacuous
  against the mutation it exists to catch: break the empty-phase branch so it
  falls through to a ``phase_ids[0]`` default and — when the batch holds only
  the empty phase — ``phase_ids[0]`` IS that phase, so the mutant returns the
  empty shape anyway and the assertion stays GREEN. That was confirmed
  empirically in plan Task 27. With a dated phase FIRST in the batch the mutant
  hands the empty phase the DATED phase's rollup and the assertion goes RED,
  which is the whole point. The solo call is asserted too, but only the batched
  one carries the proof — do not "simplify" it to a single-id call.

SC2 red-on-revert: making the empty-phase branch of
  ``flan/service/rollup.py::phase_rollups`` fall through to a ``phase_ids[0]``
  default instead of ``NO_TASKS`` must turn ``test_phase_rollup_crux``'s (A0c)
  batched assertion RED — the empty phase would report the dated phase's
  2026-03-01 / 2026-03-20 / 25.00 over 4 tasks.

D-P2b-5 (hard rule, the 11a/11b keeper): every fixture below is built through
  the REAL service and the REAL schemas the router sends — ``create_project(db,
  ProjectCreate(...))``, ``create_phase(db, project_id, PhaseCreate(...))``,
  ``create_task(db, TaskCreate(...))``, ``update_task(db, id, TaskUpdate(...))``
  — and no headline assertion is fed a hand-inserted ORM row. The single
  deliberate exception is the ``PRJ-9999999999`` key in (B), which no legal
  service call can produce and which exists precisely to prove the ``Numeric``
  (not ``Integer``) cast; it is flagged at its call site.

The (E) archived-project scenario and the HTTP RBAC/audit surface stay in the
standalone scripts and ``tests/flan/test_api.py`` respectively; only the rollup
crux and its immediate neighbours are ported here. All percentages are Decimal
— never float (D-11).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select

# Import the central model aggregator FIRST so Base.metadata is fully populated.
# Not cosmetic: `flan_team_member.user_id` FKs into `users.id`, so touching a
# flan table before the auth models are registered raises NoReferencedTableError
# (the plan's Task-16 lesson). conftest already imports app.main, which pulls
# this in; the explicit import keeps the guarantee local to this module.
import app.core.models  # noqa: F401
from app.modules.flan.models import Phase, PhaseAssignee, Task, TaskAssignee, TeamMember
from app.modules.flan.schemas import (
    PhaseCreate,
    ProjectCreate,
    TaskCreate,
    TaskUpdate,
    TeamMemberCreate,
)
from app.modules.flan.service import (
    create_member,
    create_phase,
    create_project,
    create_task,
    delete_phase,
    list_members,
    list_phases,
    list_tasks,
    phase_rollups,
    remove_member,
    set_phase_assignees,
    set_task_assignees,
    update_task,
)
from app.modules.flan.service.keys import _next_key
from app.modules.flan.service.rollup import _percent

# ---------------------------------------------------------------------------
# Session fixture — the NullPool test sessionmaker from conftest.
# FLAN posts no GL and needs no chart of accounts, so this deliberately does NOT
# use `seeded_ledger_db`: the per-test `_isolate` truncate + auth reseed is the
# whole baseline these tests need.
# ---------------------------------------------------------------------------


@pytest.fixture
async def flan_db(test_sessionmaker):
    """One NullPool session for the whole test; the flan services commit internally."""
    async with test_sessionmaker() as session:
        yield session


# ---------------------------------------------------------------------------
# Fixture builders — REAL service, REAL schemas (the 11a/11b keeper)
# ---------------------------------------------------------------------------


async def _make_project(session, tag: str, key_prefix: str = "PRJ") -> str:
    """Create a FLAN project via the REAL create_project service; return its id."""
    project = await create_project(
        session,
        ProjectCreate(
            name=f"FLAN rollup {tag}",
            key_prefix=key_prefix,
            category="work",
            currency="USD",
        ),
    )
    return project.id


async def _make_phase(session, project_id: str, name: str, sort_order: int) -> str:
    """Create a phase via the REAL create_phase service; return its id."""
    phase = await create_phase(
        session,
        project_id,
        PhaseCreate(name=name, sort_order=sort_order, status="in-progress"),
    )
    return phase.id


async def _make_task(
    session,
    phase_id: str,
    summary: str,
    start: date | None = None,
    due: date | None = None,
) -> Task:
    """Create a task via the REAL create_task service and the REAL TaskCreate schema."""
    return await create_task(
        session,
        TaskCreate(
            phase_id=phase_id,
            summary=summary,
            status="To Do",
            start_date=start,
            due_date=due,
        ),
    )


async def _task_row(session, task_id: str) -> Task:
    """Re-read a task straight from the table (independent oracle, no service cache)."""
    return (
        await session.execute(select(Task).where(Task.id == task_id))
    ).scalars().one()


async def _count(session, model, *criteria) -> int:
    """COUNT(*) over one model under the given criteria — the assertions' own oracle."""
    return int(
        (
            await session.execute(select(func.count()).select_from(model).where(*criteria))
        ).scalar_one()
    )


# ---------------------------------------------------------------------------
# Pure unit tests — no DB (the `_next_quote_number` / `generate_part_number`
# precedent: the arithmetic halves of the two generators are testable alone).
# ---------------------------------------------------------------------------


def test_percent_is_a_quantized_decimal_never_a_float() -> None:
    """`_percent` returns a Decimal quantized to 0.01 — D-11, no float across the wire."""
    value = _percent(1, 3)
    assert isinstance(value, Decimal)
    assert value.as_tuple().exponent == -2


@pytest.mark.parametrize(
    ("done", "total", "expected"),
    [
        (0, 3, "0.00"),
        (1, 3, "33.33"),
        (2, 3, "66.67"),
        (3, 3, "100.00"),
        (1, 2, "50.00"),
        (1, 8, "12.50"),
    ],
)
def test_percent_rounds_half_up_to_two_places(done: int, total: int, expected: str) -> None:
    """0/3 → 0.00, 1/3 → 33.33, 2/3 → 66.67 (ROUND_HALF_UP), 3/3 → 100.00 exactly."""
    assert _percent(done, total) == Decimal(expected)
    assert str(_percent(done, total)) == expected


def test_next_key_starts_the_series_at_one() -> None:
    """No existing key in the series → `<PREFIX>-1`, unpadded (D-V5P1-7)."""
    assert _next_key("PRJ", None) == "PRJ-1"


def test_next_key_crosses_the_single_digit_boundary() -> None:
    """The SRD's own literal: PRJ-9 → PRJ-10, the NUMERIC successor (D-P8-6)."""
    assert _next_key("PRJ", 9) == "PRJ-10"


def test_next_key_is_unpadded() -> None:
    """Unpadded, unlike the platform's document series — `PRJ-10`, not `PRJ-0010`."""
    assert _next_key("PRJ", 1) == "PRJ-2"
    assert _next_key("PRJ", 99) == "PRJ-100"


def test_next_key_increments_past_the_int4_boundary() -> None:
    """
    A suffix that overflows int4 still increments.

    Python ints are arbitrary-precision, so the pure half never had the problem;
    the SQL half is what the `Numeric`-not-`Integer` cast guards (the PLUM-01
    Phase-7 defect 7562a02), and (B) below proves that live.
    """
    assert _next_key("PRJ", 9999999999) == "PRJ-10000000000"


# ---------------------------------------------------------------------------
# (A0)-(A4) THE PHASE ROLLUP — the crux (FLAN-01.2, D-V5-1)
# ---------------------------------------------------------------------------


async def test_phase_rollup_crux(flan_db) -> None:
    """
    Port of verify_flan.py scenario (A) — four phases in ONE project.

    The empty phase is created FIRST — before any phase that has tasks — so no
    assertion below can be passing because the empty case happened to be seeded
    into a shape some other fixture had already established.

      (A0a) a phase returned by the REAL `create_phase` already carries the
            empty rollup: no dates, 0.00%, 0 tasks.
      (A0b) the SOLO `phase_rollups([empty])` — the shape a single-phase caller
            uses, kept for completeness, but it PROVES LESS than it looks.
      (A0c/CRUX) the empty phase inside a BATCH whose FIRST member is the DATED,
            non-empty phase: still no dates, 0.00% and 0/0, and it does NOT
            inherit the leading phase's rollup. **This is the assertion that
            carries the proof** — see the module docstring.
      (A0d) the same crux through `list_phases`, the read the ROUTER serves,
            which orders the dated phase first (sort_order 1) and the empty one
            second — so the router's own read is the non-vacuous batch shape.
      (A1)  derived dates are MIN/MAX, not first/last inserted.
      (A2)  0/3 → 0.00, 1/3 → 33.33 ("In Progress" is not Done), 3/3 → 100.00,
            flipped through the REAL `update_task`.
      (A3)  MIN/MAX skip NULLs: a 4th UNDATED task leaves the dates alone but
            moves task_count and the percentage; and a phase whose tasks ALL
            lack dates is NOT the empty-phase shape.
      (A4)  nothing is stored: `flan_phase` has none of the three columns.

    SC2 red-on-revert: an empty-phase branch that falls through to a
    `phase_ids[0]` default turns (A0c) and (A0d) RED.
    """
    session = flan_db
    project_id = await _make_project(session, "A")

    # --- A0 fixture: the EMPTY phase, created FIRST -------------------------
    fresh = await create_phase(
        session,
        project_id,
        PhaseCreate(name="A0 empty", sort_order=2, status="pending"),
    )
    empty_id = fresh.id
    # (A0a) The rollup `create_phase` attached on the way out is already the
    # empty shape — a brand-new phase has no tasks.
    assert fresh.derived_start_date is None
    assert fresh.derived_due_date is None
    assert fresh.percent_complete == Decimal("0.00")
    assert fresh.task_count == 0
    assert fresh.done_count == 0

    # (A0b) The SOLO batch. Kept because it is the shape a single-phase caller
    # uses, but it is VACUOUS against the fall-through mutation: with only the
    # empty phase in the batch, `phase_ids[0]` IS that phase. The load-bearing
    # assertion is (A0c).
    solo = await phase_rollups(session, [empty_id])
    assert solo[empty_id].derived_start_date is None
    assert solo[empty_id].derived_due_date is None
    assert solo[empty_id].percent_complete == Decimal("0.00")
    assert solo[empty_id].task_count == 0
    assert solo[empty_id].done_count == 0

    # --- A1: derived dates are MIN/MAX, not first/last inserted -------------
    dated_id = await _make_phase(session, project_id, "A1 dated", 1)
    dated_tasks = [
        (await _make_task(session, dated_id, "A1 first inserted", date(2026, 3, 5), date(2026, 3, 20))).id,
        (await _make_task(session, dated_id, "A1 earliest start", date(2026, 3, 1), date(2026, 3, 11))).id,
        (await _make_task(session, dated_id, "A1 latest start", date(2026, 3, 9), date(2026, 3, 14))).id,
    ]
    batch = await phase_rollups(session, [dated_id])
    # Derived start is the EARLIEST task start (inserted 2nd) and derived due the
    # LATEST task due (inserted 1st) — MIN/MAX, not first/last inserted.
    assert batch[dated_id].derived_start_date == date(2026, 3, 1)
    assert batch[dated_id].derived_due_date == date(2026, 3, 20)
    assert batch[dated_id].task_count == 3

    # --- A2: percentage, flipped through the REAL update_task ---------------
    percent_id = await _make_phase(session, project_id, "A2 percent", 3)
    percent_tasks = [(await _make_task(session, percent_id, f"A2 task {n}")).id for n in (1, 2, 3)]

    batch = await phase_rollups(session, [percent_id])
    # A REAL 0 from real counts, not the empty-phase 0.
    assert batch[percent_id].percent_complete == Decimal("0.00")
    assert batch[percent_id].task_count == 3
    assert batch[percent_id].done_count == 0

    await update_task(session, percent_tasks[0], TaskUpdate(status="Done"))
    batch = await phase_rollups(session, [percent_id])
    assert batch[percent_id].percent_complete == Decimal("33.33")
    assert batch[percent_id].done_count == 1

    await update_task(session, percent_tasks[1], TaskUpdate(status="In Progress"))
    batch = await phase_rollups(session, [percent_id])
    # "In Progress" does NOT count as done — still 33.33 with 1 of 3 done.
    assert batch[percent_id].percent_complete == Decimal("33.33")
    assert batch[percent_id].done_count == 1

    for task_id in percent_tasks[1:]:
        await update_task(session, task_id, TaskUpdate(status="Done"))
    batch = await phase_rollups(session, [percent_id])
    assert batch[percent_id].percent_complete == Decimal("100.00")
    assert batch[percent_id].done_count == 3

    # --- A3: MIN/MAX skip NULLs --------------------------------------------
    # One of A1's dated tasks goes Done first, so the percentage has a value the
    # 4th task can visibly MOVE (33.33 over 3 tasks → 25.00 over 4).
    await update_task(session, dated_tasks[0], TaskUpdate(status="Done"))
    before = (await phase_rollups(session, [dated_id]))[dated_id]
    await _make_task(session, dated_id, "A3 undated task", None, None)
    after = (await phase_rollups(session, [dated_id]))[dated_id]
    assert before.percent_complete == Decimal("33.33")
    assert before.task_count == 3
    # The derived dates are UNCHANGED while task_count rises 3 → 4 and the
    # percentage moves 33.33 → 25.00: MIN/MAX skip NULLs, but the undated task
    # is still counted work.
    assert after.derived_start_date == date(2026, 3, 1)
    assert after.derived_due_date == date(2026, 3, 20)
    assert after.task_count == 4
    assert after.percent_complete == Decimal("25.00")

    # A phase whose tasks ALL lack dates: no dates, but a REAL percentage and a
    # REAL task_count. Emphatically NOT the empty-phase shape, and the two are
    # easy to conflate precisely because both report no dates.
    undated_id = await _make_phase(session, project_id, "A3 undated", 4)
    undated_tasks = [(await _make_task(session, undated_id, f"A3 undated {n}")).id for n in (1, 2, 3)]
    await update_task(session, undated_tasks[0], TaskUpdate(status="Done"))
    batch = await phase_rollups(session, [undated_id])
    assert batch[undated_id].derived_start_date is None
    assert batch[undated_id].derived_due_date is None
    assert batch[undated_id].percent_complete == Decimal("33.33")
    assert batch[undated_id].task_count == 3

    # --- A0c: THE ASSERTION THAT CARRIES THE PROOF --------------------------
    # The empty phase inside a BATCH whose FIRST member is a NON-empty phase.
    # Break the empty-phase branch in rollup.py so it falls through to a
    # `phase_ids[0]` default and this call hands the empty phase the DATED
    # phase's rollup (2026-03-01 / 2026-03-20 / 25.00 / 4 tasks) → RED. The solo
    # form in (A0b) cannot see that mutation at all. Do NOT reduce this to a
    # single-id call — that re-introduces the vacuity this phase spent its
    # headline effort removing.
    batch = await phase_rollups(session, [dated_id, empty_id, percent_id, undated_id])
    empty = batch[empty_id]
    assert empty.derived_start_date is None, f"empty inherited {batch[dated_id]!r}"
    assert empty.derived_due_date is None, f"empty inherited {batch[dated_id]!r}"
    assert empty.percent_complete == Decimal("0.00"), f"empty inherited {batch[dated_id]!r}"
    assert empty.task_count == 0, f"empty inherited {batch[dated_id]!r}"
    assert empty.done_count == 0, f"empty inherited {batch[dated_id]!r}"
    # The same batch still answers every OTHER phase with its own real
    # aggregates — the empty branch does not flatten its neighbours.
    assert batch[dated_id].derived_start_date == date(2026, 3, 1)
    assert batch[dated_id].task_count == 4
    assert batch[percent_id].percent_complete == Decimal("100.00")
    assert batch[undated_id].task_count == 3

    # --- A0d: the same crux through list_phases, the read the ROUTER serves --
    listed = {phase.id: phase for phase in await list_phases(session, project_id)}
    # list_phases orders the NON-empty dated phase (sort_order 1) ahead of the
    # empty one (sort_order 2), so the router's own read is the non-vacuous
    # batch shape.
    assert list(listed).index(dated_id) < list(listed).index(empty_id)
    listed_empty = listed[empty_id]
    assert listed_empty.derived_start_date is None
    assert listed_empty.derived_due_date is None
    assert listed_empty.percent_complete == Decimal("0.00")
    assert listed_empty.task_count == 0
    assert listed_empty.done_count == 0

    # --- A4: nothing is stored ---------------------------------------------
    # "Never hand-set" is structural, not a rule to remember: there is no column
    # for these three values to be written to.
    columns = {column.name for column in Phase.__table__.columns}
    assert not ({"start_date", "due_date", "percent_complete"} & columns), columns


# ---------------------------------------------------------------------------
# (B) NUMERIC-SAFE TASK KEYS (FLAN-01.3, D-P8-6, D-V5P1-7)
# ---------------------------------------------------------------------------


async def test_task_keys_are_numeric_safe(flan_db) -> None:
    """
    Port of verify_flan.py scenario (B) — `PRJ-9 → PRJ-10`, live.

      * nine tasks created through the REAL service reach `PRJ-9`; the tenth is
        `PRJ-10`, the NUMERIC successor, not the lexicographic sibling a
        `MAX(key)` string aggregate would return (which would be `PRJ-9` again —
        a duplicate key, D-P8-6);
      * a legal 10-digit suffix (`PRJ-9999999999`) does not permanently 500 the
        project's creates — the cast target is `Numeric`, never `Integer` (the
        PLUM-01 Phase-7 defect 7562a02);
      * no two tasks in one project share a key, and two DIFFERENT projects may
        both hold `PRJ-1` (uniqueness is `(project_id, key)`).
    """
    session = flan_db
    project_id = await _make_project(session, "B", key_prefix="PRJ")
    phase_id = await _make_phase(session, project_id, "B keys", 1)

    keys = [(await _make_task(session, phase_id, f"B task {n}")).key for n in range(1, 10)]
    # The series is unpadded and sequential up to the digit boundary.
    assert keys == [f"PRJ-{n}" for n in range(1, 10)]
    assert keys[-1] == "PRJ-9"

    tenth = await _make_task(session, phase_id, "B task 10")
    # CRUX (D-P8-6): the successor of PRJ-9 is the NUMERIC PRJ-10.
    assert tenth.key == "PRJ-10"

    # The ONE deliberate hand-inserted row in this module: `PRJ-9999999999` is a
    # legal key that no legal service call can produce (the generator would have
    # to be walked there one create at a time). It exists solely to put a suffix
    # that overflows int4 in front of the generator's cast.
    overflow = Task(
        phase_id=phase_id,
        project_id=project_id,
        key="PRJ-9999999999",
        summary="B legacy 10-digit suffix",
    )
    session.add(overflow)
    await session.commit()

    # An Integer cast would raise "value out of range for type integer" here and
    # make EVERY subsequent auto-numbered create in this project 500 permanently.
    after_overflow = await _make_task(session, phase_id, "B task after overflow")
    assert after_overflow.key == "PRJ-10000000000"

    # No two tasks in the project share a key.
    project_keys = [task.key for task in await list_tasks(session, project_id)]
    assert len(project_keys) == len(set(project_keys))

    # A SECOND project numbers independently — both may hold `PRJ-1`, because
    # uniqueness is (project_id, key), not key.
    other_project_id = await _make_project(session, "B-other", key_prefix="PRJ")
    other_phase_id = await _make_phase(session, other_project_id, "B other", 1)
    other_first = await _make_task(session, other_phase_id, "B other task 1")
    assert other_first.key == "PRJ-1"
    assert other_first.project_id == other_project_id
    assert keys[0] == "PRJ-1"


# ---------------------------------------------------------------------------
# (C) DATE VALIDATION (FLAN-01.3)
# ---------------------------------------------------------------------------


async def test_task_date_order_is_enforced_and_milestones_are_valid(flan_db) -> None:
    """
    Port of verify_flan.py scenario (C) — `due < start` is refused, `due == start`
    is a valid zero-duration milestone task.

    The refusal has two halves and BOTH are asserted, because they catch
    different shapes:

      * the schema validator on `TaskCreate` (a 422 at the API boundary) sees a
        payload carrying both dates;
      * `update_task`'s re-check over the MERGED values (an HTTP 422 from the
        service) is the only place a PATCH that moves **only** `start_date` can
        be caught — the schema has no stored row to compare against.
    """
    session = flan_db
    project_id = await _make_project(session, "C")
    phase_id = await _make_phase(session, project_id, "C dates", 1)

    # POST with due < start is refused at the schema layer (422 over the wire).
    with pytest.raises(ValidationError):
        TaskCreate(
            phase_id=phase_id,
            summary="C invalid",
            start_date=date(2026, 1, 10),
            due_date=date(2026, 1, 9),
        )

    # `due == start` constructs and creates: a zero-duration MILESTONE task.
    milestone = await _make_task(
        session, phase_id, "C milestone", date(2026, 1, 10), date(2026, 1, 10)
    )
    stored = await _task_row(session, milestone.id)
    assert stored.start_date == stored.due_date == date(2026, 1, 10)

    # The phase's derived dates follow: a milestone's start and due are both it.
    rollup = (await phase_rollups(session, [phase_id]))[phase_id]
    assert rollup.derived_start_date == rollup.derived_due_date == date(2026, 1, 10)

    # PATCH that moves ONLY start_date past the stored due_date → 422 from the
    # service's merged re-check (the schema validator cannot see this case).
    dated = await _make_task(
        session, phase_id, "C dated", date(2026, 2, 1), date(2026, 2, 10)
    )
    with pytest.raises(HTTPException) as patch_exc:
        await update_task(session, dated.id, TaskUpdate(start_date=date(2026, 2, 20)))
    assert patch_exc.value.status_code == 422

    # The refused PATCH changed nothing.
    unchanged = await _task_row(session, dated.id)
    assert unchanged.start_date == date(2026, 2, 1)
    assert unchanged.due_date == date(2026, 2, 10)

    # PATCH to `due == start` is accepted — turning a task into a milestone is legal.
    await update_task(session, dated.id, TaskUpdate(due_date=date(2026, 2, 1)))
    became_milestone = await _task_row(session, dated.id)
    assert became_milestone.start_date == became_milestone.due_date == date(2026, 2, 1)


# ---------------------------------------------------------------------------
# (D) ROSTER REMOVAL LEAVES THE TASKS INTACT (FLAN-01.4, D-V5P1-6)
# ---------------------------------------------------------------------------


async def test_roster_removal_clears_assignments_and_leaves_tasks_intact(flan_db) -> None:
    """
    Port of verify_flan.py scenario (D) — a member assigned to 2 tasks and 1
    phase is removed.

    "Removing a roster member clears their assignments but leaves the tasks
    intact" (FLAN-01.4) is meant literally, so the assertions are literal:

      * both tasks still exist with their summaries, dates AND their exact
        `updated_at` — `remove_member` must not load, dirty or re-save a task
        row (an `updated_at` that moved is the observable proof that it did);
      * zero `flan_task_assignee` / `flan_phase_assignee` rows remain for the
        removed member, and the OTHER member's assignment on the same task
        survives — the deletes are scoped by `member_id`, never by `task_id`;
      * the member row itself is KEPT with `active=False` (a soft remove,
        D-V5P1-6), so past references stay resolvable; `list_members` hides it
        by default and `include_removed=True` finds it.
    """
    session = flan_db
    project_id = await _make_project(session, "D")
    phase_id = await _make_phase(session, project_id, "D roster", 1)
    task_a_id = (
        await _make_task(session, phase_id, "D task A", date(2026, 4, 1), date(2026, 4, 5))
    ).id
    task_b_id = (
        await _make_task(session, phase_id, "D task B", date(2026, 4, 2), date(2026, 4, 6))
    ).id

    leaving_id = (
        await create_member(
            session, project_id, TeamMemberCreate(name="D Leaving Member", role="Engineer")
        )
    ).id
    staying_id = (
        await create_member(
            session, project_id, TeamMemberCreate(name="D Staying Member", role="Engineer")
        )
    ).id

    # Both members on task A, the leaver alone on task B and on the phase.
    await set_task_assignees(session, task_a_id, [leaving_id, staying_id])
    await set_task_assignees(session, task_b_id, [leaving_id])
    await set_phase_assignees(session, phase_id, [leaving_id])
    assert await _count(session, TaskAssignee, TaskAssignee.member_id == leaving_id) == 2
    assert await _count(session, PhaseAssignee, PhaseAssignee.member_id == leaving_id) == 1

    async def _task_state(task_id: str) -> tuple:
        """Summary, dates and updated_at read fresh from the table (the oracle)."""
        session.expire_all()
        task = await _task_row(session, task_id)
        return (task.summary, task.start_date, task.due_date, task.updated_at)

    before = {task_id: await _task_state(task_id) for task_id in (task_a_id, task_b_id)}

    cleared = await remove_member(session, leaving_id)
    # The count the router names in the `team_member.removed` audit detail: two
    # task assignments plus one phase assignment.
    assert cleared == 3

    # Both tasks survive untouched — summary, dates and the exact `updated_at`
    # (an updated_at that moved would prove remove_member re-saved a task row).
    after = {task_id: await _task_state(task_id) for task_id in (task_a_id, task_b_id)}
    assert after == before

    # No assignment row anywhere still names the removed member...
    assert await _count(session, TaskAssignee, TaskAssignee.member_id == leaving_id) == 0
    assert await _count(session, PhaseAssignee, PhaseAssignee.member_id == leaving_id) == 0
    # ...while the OTHER member's assignment on the shared task is untouched
    # (the deletes are scoped by member_id, never by task_id).
    assert await _count(session, TaskAssignee, TaskAssignee.member_id == staying_id) == 1
    assert await _count(session, TaskAssignee, TaskAssignee.task_id == task_a_id) == 1

    # The member row is KEPT (soft remove, D-V5P1-6) with its history intact.
    kept = (
        await session.execute(select(TeamMember).where(TeamMember.id == leaving_id))
    ).scalars().one()
    assert kept.active is False
    assert kept.name == "D Leaving Member"
    assert kept.role == "Engineer"

    # Hidden from the default roster read (and so from assignee pickers), found
    # by the explicit include_removed=True view.
    assert [m.id for m in await list_members(session, project_id)] == [staying_id]
    removed_view = await list_members(session, project_id, include_removed=True)
    assert leaving_id in {member.id for member in removed_view}


# ---------------------------------------------------------------------------
# (F) PHASE DELETE CASCADES TO ITS TASKS (FLAN-01.2)
# ---------------------------------------------------------------------------


async def test_phase_delete_cascades_to_its_tasks_only(flan_db) -> None:
    """
    Port of verify_flan.py scenario (F) — deleting a phase takes its tasks with
    it, and ONLY its tasks.

    The cascade is the DATABASE's (`flan_task.phase_id` is `ondelete="CASCADE"`),
    so the assertions are made against the table, not against the service's
    return value alone: zero `flan_task` rows remain for the deleted phase, the
    sibling phase's tasks in the SAME project are all still there, and
    `delete_phase` reports the count it removed (the number the router names in
    the `phase.deleted` audit detail).
    """
    session = flan_db
    project_id = await _make_project(session, "F")
    doomed_id = await _make_phase(session, project_id, "F doomed", 1)
    sibling_id = await _make_phase(session, project_id, "F sibling", 2)

    for n in (1, 2, 3):
        await _make_task(session, doomed_id, f"F doomed task {n}", date(2026, 5, n), date(2026, 6, n))
    sibling_tasks = [(await _make_task(session, sibling_id, f"F sibling task {n}")).id for n in (1, 2)]

    assert await _count(session, Task, Task.phase_id == doomed_id) == 3

    removed = await delete_phase(session, doomed_id)
    # The count is read BEFORE the delete, since afterwards there is nothing to count.
    assert removed == 3

    # The phase and every one of its tasks are gone.
    assert await _count(session, Phase, Phase.id == doomed_id) == 0
    assert await _count(session, Task, Task.phase_id == doomed_id) == 0

    # The sibling phase in the SAME project is untouched — the cascade is scoped
    # by phase_id, not by project_id.
    assert await _count(session, Phase, Phase.id == sibling_id) == 1
    assert sorted(task.id for task in await list_tasks(session, project_id)) == sorted(sibling_tasks)

    # And the surviving phase still reports its own rollup, not a hole.
    remaining = {phase.id: phase for phase in await list_phases(session, project_id)}
    assert set(remaining) == {sibling_id}
    assert remaining[sibling_id].task_count == 2
    assert remaining[sibling_id].percent_complete == Decimal("0.00")
