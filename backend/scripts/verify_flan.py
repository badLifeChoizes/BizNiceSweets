# ABOUTME: Standalone live-DB verification for the FLAN phase rollup (v5.0 Phase 1).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and drives
# ABOUTME: the REAL flan service through the SAME ProjectCreate/PhaseCreate/TaskCreate/TaskUpdate
# ABOUTME: schemas the router sends — proving THE CRUX: a phase's start date, due date and %
# ABOUTME: complete are DERIVED from its tasks and never stored, including the empty-phase case
# ABOUTME: asserted inside a batch whose FIRST member is a non-empty phase (the non-vacuous form);
# ABOUTME: exits non-zero on FAIL and self-cleans so it is safe to re-run.
"""
Standalone live-DB verification script for FLAN core (v5.0 Phase 1).

WHY THIS EXISTS (FLAN-01.2 / D-V5-1, the SRD's named verification):
  A FLAN phase carries **no** `start_date`, `due_date` or `percent_complete`
  column. Those three values are derived on every read from the phase's tasks —
  earliest task start, latest task due, and the share of its tasks in status
  `Done` — and are never hand-set. The load-bearing behaviours:

    * EMPTY PHASE (FLAN-01.2, the case a happy-path fixture will not have): a
      phase with zero tasks reports no dates, `0.00`% and zero counts. SQL
      `GROUP BY` produces no row for a group with no rows, so the empty phase is
      answered by an explicit named branch in `service/rollup.py` — the one
      branch this whole crux turns on.
    * MIN/MAX, NOT FIRST/LAST (FLAN-01.2): the derived start is the EARLIEST
      task start and the derived due the LATEST task due, whatever order the
      tasks were inserted in.
    * PERCENT IS DECIMAL (D-11, no float across the wire): 0/3 → `0.00`,
      1/3 → `33.33`, 3/3 → `100.00`, quantized ROUND_HALF_UP.
    * MIN/MAX SKIP NULLS (FLAN-01.2): an undated task is still work — it raises
      `task_count` and moves the percentage but contributes nothing to the
      derived dates. A phase whose tasks ALL lack dates therefore reports no
      dates and a REAL percentage, which is emphatically not the empty-phase
      shape.
    * NOTHING IS STORED (D-V5-1, the structural half of "never hand-set"):
      `flan_phase` has no column named `start_date`, `due_date` or
      `percent_complete` to write these to.

  THE NON-VACUITY POINT (A0, amended at build — read this before editing):
    The empty-phase assertion MUST be made inside a BATCH whose FIRST member is
    a NON-empty phase. A solo `phase_rollups(db, [empty_phase_id])` is vacuous
    against the mutation it exists to catch: break the empty-phase branch so it
    falls through to a `phase_ids[0]` default and — when the batch holds only
    the empty phase — `phase_ids[0]` IS that phase, so the mutant returns the
    empty shape anyway and the assertion stays GREEN. With a dated phase first
    in the batch the mutant hands the empty phase the DATED phase's rollup and
    A0 goes RED, which is the whole point of this script. Both calls are made
    below; only the batch one carries the proof.

  THE KEEPER (the 11a/11b lesson): two prior phases certified GREEN while the
  headline feature was dead through the UI, because the verify script hand-fed
  inputs in a shape the router/UI never sends. This script therefore builds every
  fixture through the REAL service and the REAL schemas the router constructs —
  `create_project(db, ProjectCreate(...))`, `create_phase(db, project_id,
  PhaseCreate(...))`, `create_task(db, TaskCreate(...))`, `update_task(db,
  task_id, TaskUpdate(...))` — and never hand-inserts an ORM row for a headline
  assertion. The rollup is read back BOTH through `phase_rollups` directly and
  through `list_phases`, the read the router actually serves.

  None of that can be proven by the pure unit tests, and the backend live-DB
  pytest harness is broken (D-P7-4), so DB-dependent tests skip under plain
  ``pytest``. Verifiable truth must come from a STANDALONE run against LIVE
  Postgres. This script stands up its own async engine + sessionmaker from the
  ``POSTGRES_*`` environment variables — it deliberately does NOT import the
  broken test conftest fixtures — and drives the REAL flan service end-to-end.

  It imports ``app.core.models`` (the central aggregator) FIRST and on purpose:
  `flan_team_member.user_id` FKs into `users.id`, so touching any flan table
  before the auth models are registered raises `NoReferencedTableError`.

HOW TO RUN (the compose ``db`` service is not host-published):
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_flan.py
  (ad-hoc SQL: podman exec compose_db_1 psql -U app -d biznice -c '...')

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  (A) THE PHASE ROLLUP (FLAN-01.2, D-V5-1) — four phases in ONE project:
      A0  the EMPTY phase, created FIRST: zero tasks → derived_start_date None,
          derived_due_date None, percent_complete == Decimal("0.00"),
          task_count == 0 — asserted (a) on the freshly-created phase, (b) in a
          SOLO batch, and (c) — the assertion that carries the proof — in a
          BATCH whose first member is the dated, non-empty phase, and (d)
          through `list_phases`, the read the router serves, which orders the
          non-empty phase first.
      A1  DATES ARE MIN/MAX: 3 tasks with starts 2026-03-05 / 2026-03-01 /
          2026-03-09 and dues 2026-03-20 / 2026-03-11 / 2026-03-14 → derived
          start 2026-03-01 and derived due 2026-03-20 (neither the first nor the
          last inserted).
      A2  PERCENT: 0/3 → "0.00", 1/3 → "33.33", 3/3 → "100.00", flipping the
          statuses through the REAL `update_task`.
      A3  DATES SKIP NULLS: a 4th, UNDATED task joins A1's phase → the derived
          dates are UNCHANGED, task_count rises 3 → 4 and the percentage moves
          33.33 → 25.00. And a phase whose tasks ALL lack dates reports no dates
          with a REAL percentage and task_count — not the empty-phase shape.
      A4  NOTHING IS STORED: `Phase.__table__.columns` holds no `start_date`,
          `due_date` or `percent_complete`.

The script uses uniquely-suffixed throwaway projects and CLEANS UP after itself
(assignees -> tasks -> phases -> members -> project tags -> projects) in a
finally block, so it is safe to re-run against the same database.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_flan.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app — the sibling verify_*.py scripts require that env var).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the central model aggregator FIRST so Base.metadata is fully populated.
# Not optional and not cosmetic: `flan_team_member.user_id` FKs into `users.id`,
# so importing the flan models alone raises NoReferencedTableError the moment a
# mapper is configured (the Task-16 lesson; the MOUSSE Task-8 lesson before it).
import app.core.models  # noqa: F401
from app.modules.flan.models import (
    Phase,
    PhaseAssignee,
    Project,
    ProjectTag,
    Task,
    TaskAssignee,
    TeamMember,
)
from app.modules.flan.schemas import PhaseCreate, ProjectCreate, TaskCreate, TaskUpdate
from app.modules.flan.service import (
    create_phase,
    create_project,
    create_task,
    list_phases,
    phase_rollups,
    update_task,
)

# ---------------------------------------------------------------------------
# PASS/FAIL bookkeeping
# ---------------------------------------------------------------------------

_FAILURES = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    """Print PASS/FAIL for one assertion and record failures for the exit code."""
    global _FAILURES
    if condition:
        print(f"PASS: {label}")
    else:
        _FAILURES += 1
        suffix = f" — {detail}" if detail else ""
        print(f"FAIL: {label}{suffix}")


# ---------------------------------------------------------------------------
# Own async engine from POSTGRES_* env (NOT the broken conftest fixtures)
# ---------------------------------------------------------------------------


def build_dsn() -> str:
    """
    Assemble the asyncpg DSN directly from POSTGRES_* environment variables.

    Mirrors app.core.config.Settings.database_url but reads os.environ itself so
    the script is fully self-contained and never touches the test conftest.
    """
    host = os.environ.get("POSTGRES_HOST", "db")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DB", "biznice")
    user = os.environ.get("POSTGRES_USER", "app")
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        print("FAIL: POSTGRES_PASSWORD is not set in the environment.")
        sys.exit(2)
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


# ---------------------------------------------------------------------------
# Fixture builders — every one goes through the REAL service and the REAL
# schema the router sends (the 11a/11b keeper); nothing hand-inserts an ORM row.
# ---------------------------------------------------------------------------


async def _make_project(session_factory, unique: str, tag: str) -> str:
    """Create a throwaway FLAN project via the REAL create_project service."""
    async with session_factory() as session:
        project = await create_project(
            session,
            ProjectCreate(
                name=f"VERIFY-FLAN {tag} {unique}",
                key_prefix=f"VF{unique.upper()}",
                category="work",
                description=f"Throwaway project for verify_flan.py scenario {tag}.",
                currency="USD",
            ),
        )
        return project.id


async def _make_phase(session_factory, project_id: str, name: str, sort_order: int) -> str:
    """Create a phase via the REAL create_phase service; return its id."""
    async with session_factory() as session:
        phase = await create_phase(
            session,
            project_id,
            PhaseCreate(name=name, sort_order=sort_order, status="in-progress"),
        )
        return phase.id


async def _make_task(
    session_factory,
    phase_id: str,
    summary: str,
    start: date | None = None,
    due: date | None = None,
) -> str:
    """Create a task via the REAL create_task service and the REAL TaskCreate schema."""
    async with session_factory() as session:
        task = await create_task(
            session,
            TaskCreate(
                phase_id=phase_id,
                summary=summary,
                status="To Do",
                start_date=start,
                due_date=due,
            ),
        )
        return task.id


async def _set_status(session_factory, task_id: str, status: str) -> None:
    """Flip a task's status through the REAL update_task service (PATCH semantics)."""
    async with session_factory() as session:
        await update_task(session, task_id, TaskUpdate(status=status))


async def _rollups(session_factory, phase_ids: list[str]) -> dict:
    """Read a batch of phase rollups through the REAL phase_rollups service."""
    async with session_factory() as session:
        return await phase_rollups(session, phase_ids)


async def _listed_phases(session_factory, project_id: str) -> dict:
    """
    Read the project's phases through `list_phases` — the read the ROUTER serves
    (GET /flan/projects/{id}/phases) — and index them by id.

    This is the batched path a client actually gets: `list_phases` orders by
    sort_order and hands EVERY phase of the project to `phase_rollups` in one
    call, so the empty phase is answered inside a batch that also holds the
    dated one. Same crux, read through the real route's shape.
    """
    async with session_factory() as session:
        phases = await list_phases(session, project_id)
    return {phase.id: phase for phase in phases}


# ---------------------------------------------------------------------------
# (A) THE PHASE ROLLUP — the crux (FLAN-01.2, D-V5-1)
# ---------------------------------------------------------------------------


async def scenario_a(session_factory, project_ids: set[str]) -> None:  # noqa: C901
    """
    Four phases in ONE project: the empty phase, the dated phase, the percentage
    phase, and a phase whose tasks are all undated.

    The empty phase is created FIRST — before any phase that has tasks — so no
    assertion below can be passing because the empty case happened to be seeded
    into a shape some other fixture had already established.

    `sort_order` is chosen so `list_phases` returns the DATED phase first and the
    EMPTY phase second: that ordering is what makes A0 non-vacuous (see the
    module docstring), and it is the ordering a real client sees.
    """
    unique = uuid.uuid4().hex[:8]
    project_id = await _make_project(session_factory, unique, "A")
    project_ids.add(project_id)

    # --- A0 fixture: the EMPTY phase, created FIRST -------------------------
    # (a) The phase as `create_phase` itself returned it: a brand-new phase has no
    #     tasks, so the rollup attached on the way out is already the empty shape.
    async with session_factory() as session:
        fresh = await create_phase(
            session,
            project_id,
            PhaseCreate(name=f"A0 empty {unique}", sort_order=2, status="pending"),
        )
    empty_id = fresh.id
    check(
        "(A0a/FLAN-01.2) a phase returned by the REAL create_phase carries the "
        "empty rollup already attached — no dates, 0.00%, 0 tasks",
        fresh.derived_start_date is None
        and fresh.derived_due_date is None
        and fresh.percent_complete == Decimal("0.00")
        and fresh.task_count == 0,
        f"start={fresh.derived_start_date!r} due={fresh.derived_due_date!r} "
        f"pct={fresh.percent_complete!r} count={fresh.task_count!r}",
    )

    # (b) The SOLO batch. Kept because it is the shape a single-phase caller uses,
    #     but it PROVES LESS than it looks: with only the empty phase in the batch,
    #     a fall-through to `phase_ids[0]` would return that same empty phase's
    #     shape and stay green. The load-bearing assertion is (c) below.
    solo = await _rollups(session_factory, [empty_id])
    check(
        "(A0b/FLAN-01.2) solo phase_rollups([empty]) → no dates, 0.00%, 0/0 "
        "(the weak form — see A0c for the assertion that carries the proof)",
        solo[empty_id].derived_start_date is None
        and solo[empty_id].derived_due_date is None
        and solo[empty_id].percent_complete == Decimal("0.00")
        and solo[empty_id].task_count == 0
        and solo[empty_id].done_count == 0,
        f"{solo[empty_id]!r}",
    )

    # --- A1: derived dates are MIN/MAX, not first/last inserted -------------
    dated_id = await _make_phase(session_factory, project_id, f"A1 dated {unique}", 1)
    dated_tasks = [
        await _make_task(
            session_factory, dated_id, "A1 first inserted", date(2026, 3, 5), date(2026, 3, 20)
        ),
        await _make_task(
            session_factory, dated_id, "A1 earliest start", date(2026, 3, 1), date(2026, 3, 11)
        ),
        await _make_task(
            session_factory, dated_id, "A1 latest start", date(2026, 3, 9), date(2026, 3, 14)
        ),
    ]
    batch = await _rollups(session_factory, [dated_id])
    check(
        "(A1/FLAN-01.2) derived start == 2026-03-01 (the EARLIEST task start, "
        "inserted 2nd) and derived due == 2026-03-20 (the LATEST task due, "
        "inserted 1st) — MIN/MAX, not first/last inserted",
        batch[dated_id].derived_start_date == date(2026, 3, 1)
        and batch[dated_id].derived_due_date == date(2026, 3, 20)
        and batch[dated_id].task_count == 3,
        f"{batch[dated_id]!r}",
    )

    # --- A2: percentage, flipped through the REAL update_task ---------------
    percent_id = await _make_phase(session_factory, project_id, f"A2 percent {unique}", 3)
    percent_tasks = [
        await _make_task(session_factory, percent_id, f"A2 task {n}") for n in (1, 2, 3)
    ]

    batch = await _rollups(session_factory, [percent_id])
    check(
        '(A2/FLAN-01.2) 0 of 3 tasks Done → percent_complete == Decimal("0.00") '
        "(a real 0 from real counts, not the empty-phase 0)",
        batch[percent_id].percent_complete == Decimal("0.00")
        and batch[percent_id].task_count == 3
        and batch[percent_id].done_count == 0,
        f"{batch[percent_id]!r}",
    )

    await _set_status(session_factory, percent_tasks[0], "Done")
    batch = await _rollups(session_factory, [percent_id])
    check(
        '(A2/FLAN-01.2) 1 of 3 Done through the REAL update_task → "33.33" '
        "(Decimal, ROUND_HALF_UP — never a float)",
        batch[percent_id].percent_complete == Decimal("33.33")
        and batch[percent_id].done_count == 1,
        f"{batch[percent_id]!r}",
    )

    await _set_status(session_factory, percent_tasks[1], "In Progress")
    batch = await _rollups(session_factory, [percent_id])
    check(
        '(A2/FLAN-01.2) "In Progress" does NOT count as done — still "33.33" '
        "with 1 of 3 done",
        batch[percent_id].percent_complete == Decimal("33.33")
        and batch[percent_id].done_count == 1,
        f"{batch[percent_id]!r}",
    )

    for task_id in percent_tasks[1:]:
        await _set_status(session_factory, task_id, "Done")
    batch = await _rollups(session_factory, [percent_id])
    check(
        '(A2/FLAN-01.2) 3 of 3 Done → "100.00" exactly',
        batch[percent_id].percent_complete == Decimal("100.00")
        and batch[percent_id].done_count == 3,
        f"{batch[percent_id]!r}",
    )

    # --- A3: MIN/MAX skip NULLs --------------------------------------------
    # One of A1's dated tasks goes Done first, so the percentage has a value the
    # 4th task can visibly MOVE (33.33 with 3 tasks → 25.00 with 4).
    await _set_status(session_factory, dated_tasks[0], "Done")
    before = (await _rollups(session_factory, [dated_id]))[dated_id]
    await _make_task(session_factory, dated_id, "A3 undated task", None, None)
    after = (await _rollups(session_factory, [dated_id]))[dated_id]
    check(
        "(A3/FLAN-01.2) a 4th UNDATED task joins the dated phase: the derived "
        "dates are UNCHANGED (2026-03-01 → 2026-03-20) while task_count rises "
        "3 → 4 and the percentage moves 33.33 → 25.00 — MIN/MAX skip NULLs but "
        "the undated task is still counted work",
        before.percent_complete == Decimal("33.33")
        and before.task_count == 3
        and after.derived_start_date == date(2026, 3, 1)
        and after.derived_due_date == date(2026, 3, 20)
        and after.task_count == 4
        and after.percent_complete == Decimal("25.00"),
        f"before={before!r} after={after!r}",
    )

    # A phase whose tasks ALL lack dates: no dates, but a REAL percentage and a
    # REAL task_count. This is emphatically NOT the empty-phase shape, and the
    # two are easy to conflate precisely because both report no dates.
    undated_id = await _make_phase(session_factory, project_id, f"A3 undated {unique}", 4)
    undated_tasks = [
        await _make_task(session_factory, undated_id, f"A3 undated {n}") for n in (1, 2, 3)
    ]
    await _set_status(session_factory, undated_tasks[0], "Done")
    batch = await _rollups(session_factory, [undated_id])
    check(
        "(A3/FLAN-01.2) a phase whose tasks ALL lack dates reports no dates but "
        'a REAL "33.33" over 3 tasks — no-dates is not the same state as no-tasks',
        batch[undated_id].derived_start_date is None
        and batch[undated_id].derived_due_date is None
        and batch[undated_id].percent_complete == Decimal("33.33")
        and batch[undated_id].task_count == 3,
        f"{batch[undated_id]!r}",
    )

    # --- A0c: THE ASSERTION THAT CARRIES THE PROOF --------------------------
    # The empty phase inside a BATCH whose FIRST member is a NON-empty phase.
    # Break the empty-phase branch in rollup.py so it falls through to a
    # `phase_ids[0]` default and this call hands the empty phase the DATED
    # phase's rollup (2026-03-01 / 2026-03-20 / 25.00 / 4 tasks) → RED. The solo
    # form in A0b cannot see that mutation at all. Do not "simplify" this to a
    # single-id call.
    ordered = [dated_id, empty_id, percent_id, undated_id]
    batch = await _rollups(session_factory, ordered)
    empty = batch[empty_id]
    check(
        "(A0c/FLAN-01.2 CRUX) phase_rollups([dated, EMPTY, percent, undated]) — "
        "the empty phase asserted inside a batch whose FIRST member is a "
        "non-empty phase — still reports derived_start_date None, "
        'derived_due_date None, percent_complete Decimal("0.00") and 0/0 tasks, '
        "and does NOT inherit the leading phase's rollup",
        empty.derived_start_date is None
        and empty.derived_due_date is None
        and empty.percent_complete == Decimal("0.00")
        and empty.task_count == 0
        and empty.done_count == 0,
        f"empty={empty!r} leading_dated={batch[dated_id]!r}",
    )
    check(
        "(A0c/FLAN-01.2) the same batch still answers every OTHER phase with its "
        "own real aggregates — the empty branch does not flatten its neighbours",
        batch[dated_id].derived_start_date == date(2026, 3, 1)
        and batch[dated_id].task_count == 4
        and batch[percent_id].percent_complete == Decimal("100.00")
        and batch[undated_id].task_count == 3,
        f"dated={batch[dated_id]!r} percent={batch[percent_id]!r} "
        f"undated={batch[undated_id]!r}",
    )

    # --- A0d: the same crux through list_phases, the read the ROUTER serves --
    listed = await _listed_phases(session_factory, project_id)
    listed_empty = listed[empty_id]
    check(
        "(A0d/FLAN-01.2 CRUX) through list_phases — the batched read GET "
        "/flan/projects/{id}/phases actually serves, which returns the dated "
        "phase FIRST (sort_order 1) and the empty phase second — the empty "
        'phase still shows no dates, "0.00" and 0 tasks',
        listed_empty.derived_start_date is None
        and listed_empty.derived_due_date is None
        and listed_empty.percent_complete == Decimal("0.00")
        and listed_empty.task_count == 0
        and listed_empty.done_count == 0,
        f"order={[p.name for p in listed.values()]} empty="
        f"(start={listed_empty.derived_start_date!r} "
        f"due={listed_empty.derived_due_date!r} "
        f"pct={listed_empty.percent_complete!r} count={listed_empty.task_count!r})",
    )
    check(
        "(A0d/FLAN-01.2) list_phases orders the NON-empty dated phase ahead of "
        "the empty one, so the router's own read is the non-vacuous batch shape",
        list(listed).index(dated_id) < list(listed).index(empty_id),
        f"order={[p.name for p in listed.values()]}",
    )

    # --- A4: nothing is stored ---------------------------------------------
    columns = [c.name for c in Phase.__table__.columns]
    check(
        "(A4/D-V5-1) flan_phase has NO start_date, due_date or percent_complete "
        'column — "never hand-set" is structural, not a rule to remember',
        not ({"start_date", "due_date", "percent_complete"} & set(columns)),
        f"columns={columns}",
    )


# ---------------------------------------------------------------------------
# Scenario driver
# ---------------------------------------------------------------------------


async def run() -> None:
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Throwaway-row registry for the finally cleanup. Every scenario adds the
    # ids of the projects it creates; the cleanup reaches everything else
    # (phases, tasks, members, tags, assignees) through them.
    project_ids: set[str] = set()

    try:
        await scenario_a(session_factory, project_ids)
        # ---------------------------------------------------------------
        # INSERTION POINT — scenarios (B)-(F) (plan task 28) go here, each as
        # its own `await scenario_x(session_factory, project_ids)` call with a
        # matching `async def scenario_x(...)` above. Register every project a
        # scenario creates in `project_ids` and the cleanup below covers it.
        # ---------------------------------------------------------------
    finally:
        await _cleanup(session_factory, project_ids)
        await engine.dispose()


# ---------------------------------------------------------------------------
# Cleanup — delete only the throwaway rows, in FK-safe order
# ---------------------------------------------------------------------------


async def _cleanup(session_factory, project_ids: set[str]) -> None:
    """
    Delete every throwaway row in FK-safe order, keyed off the project ids alone.

    Order: task/phase assignee rows (they FK into flan_team_member, which is NOT
    an ON DELETE CASCADE edge, so they must go before the members) -> tasks ->
    phases -> team members -> project tags -> projects. Task and phase tags ride
    out on their owners' CASCADE edges.

    Nothing seeded or pre-existing is touched: only rows whose project_id is one
    this run created.
    """
    if not project_ids:
        return
    ids = list(project_ids)
    async with session_factory() as session:
        await session.execute(
            delete(TaskAssignee).where(
                TaskAssignee.task_id.in_(select(Task.id).where(Task.project_id.in_(ids)))
            )
        )
        await session.execute(
            delete(PhaseAssignee).where(
                PhaseAssignee.phase_id.in_(select(Phase.id).where(Phase.project_id.in_(ids)))
            )
        )
        await session.execute(delete(Task).where(Task.project_id.in_(ids)))
        await session.execute(delete(Phase).where(Phase.project_id.in_(ids)))
        await session.execute(delete(TeamMember).where(TeamMember.project_id.in_(ids)))
        await session.execute(delete(ProjectTag).where(ProjectTag.project_id.in_(ids)))
        await session.execute(delete(Project).where(Project.id.in_(ids)))
        await session.commit()


def main() -> int:
    asyncio.run(run())
    if _FAILURES:
        print(f"\n{_FAILURES} assertion(s) FAILED.")
        return 1
    print("\nAll assertions PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
