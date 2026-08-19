# ABOUTME: Standalone live-DB verification for the FLAN phase rollup (v5.0 Phase 1).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and drives
# ABOUTME: the REAL flan service through the SAME ProjectCreate/PhaseCreate/TaskCreate/TaskUpdate
# ABOUTME: schemas the router sends — proving THE CRUX: a phase's start date, due date and %
# ABOUTME: complete are DERIVED from its tasks and never stored, including the empty-phase case
# ABOUTME: asserted inside a batch whose FIRST member is a non-empty phase (the non-vacuous form);
# ABOUTME: and the rest of FLAN core's load-bearing rules — numeric-safe task keys, date order,
# ABOUTME: roster removal, the archived-project write freeze and the phase-delete cascade (B)-(F);
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

SCENARIOS (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
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

  (B) NUMERIC-SAFE TASK KEYS (FLAN-01.3, D-P8-6, D-V5P1-7) — three projects,
      all with the SAME `PRJ` prefix:
      B1  a project driven up to `PRJ-9` issues `PRJ-10` next — the NUMERIC
          successor the SRD names, unpadded.
      B2  the CONTRAST: a plain `MAX(key)` STRING aggregate over the same rows
          answers `PRJ-9`, whose successor the project already holds, i.e. the
          naive generator would re-issue a live key; `list_tasks` orders on the
          numeric suffix for the same reason.
      B3  two tasks in one project can never share a key
          (`uq_flan_task_project_key`, asked directly).
      B4  THE DIGIT BOUNDARY: with the legal 10-digit key `PRJ-9999999999` in
          place, the next create still succeeds (`PRJ-10000000000`) because the
          cast target is `Numeric` and never `Integer` — the PLUM-01 Phase-7
          defect `7562a02`, which made every create in a project 500 forever.
      B5  two DIFFERENT projects may both hold a `PRJ-1`.
  (C) DATE VALIDATION (FLAN-01.3) — `due < start` is refused at create (by the
      schema the router builds the payload with, which is the 422 FastAPI
      renders) AND on a PATCH that moves only `start_date` (by the service's
      merged-value check, 422 on `exc.status_code`), while the stored row is
      left untouched; `due == start` is a valid zero-duration milestone on both
      paths.
  (D) ROSTER REMOVAL (FLAN-01.4, D-V5P1-6) — a member on 2 tasks and 1 phase is
      removed: the 3 assignment rows go, the tasks come through BYTE-IDENTICAL
      (`updated_at` included — "leaves the tasks intact" is literal), the phase
      survives, a SECOND member's row on the shared task survives (the deletes
      are scoped by member_id, never by task_id) and the roster row itself is
      kept with `active` cleared. Then, separately, deactivating the linked
      platform user (`users.is_active`) changes neither the roster row nor its
      remaining assignments.
  (E) AN ARCHIVED PROJECT REJECTS WRITES (FLAN-01.1) — 422 from `create_phase`,
      `create_task`, `update_task`, `create_member`, `set_task_assignees` and
      `update_project` alike, while a READ still returns the whole project:
      tags, the phase WITH its derived rollup, the task with its dates and
      assignee, and the roster. `active` is the only thing that changed.
  (F) PHASE DELETE CASCADES (FLAN-01.2) — a phase with 3 tasks is deleted:
      `count(*) FROM flan_task WHERE phase_id = :id` falls 3 -> 0, the three task
      rows are gone rather than orphaned, and a SIBLING phase's tasks in the SAME
      project are untouched.

TWO HAND-WRITES, both marked at the line and both in (B): forcing the 10-digit
key (B4) and aiming a duplicate key at the unique constraint (B3). Neither state
can be reached by any legal service call — that is precisely why they are worth
verifying — and every headline assertion elsewhere in this file goes through the
REAL service and the REAL schema.

The script uses uniquely-suffixed throwaway projects and CLEANS UP after itself
(assignees -> tasks -> phases -> members -> project tags -> projects) in a
finally block, so it is safe to re-run against the same database. Scenario (D)
also mints ONE throwaway platform user — the only row this file creates that the
project-keyed cleanup cannot reach — and deletes it in its own `finally`, by
email pattern so a killed run is swept by the next one.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
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
from app.modules.auth.models import User
from app.modules.auth.service import create_user, update_user
from app.modules.flan.models import (
    Phase,
    PhaseAssignee,
    Project,
    ProjectTag,
    Task,
    TaskAssignee,
    TeamMember,
)
from app.modules.flan.schemas import (
    PhaseCreate,
    ProjectCreate,
    ProjectUpdate,
    TaskCreate,
    TaskUpdate,
    TeamMemberCreate,
)
from app.modules.flan.service import (
    archive_project,
    create_member,
    create_phase,
    create_project,
    create_task,
    delete_phase,
    get_project,
    get_task,
    list_members,
    list_phases,
    list_tasks,
    phase_rollups,
    remove_member,
    set_phase_assignees,
    set_task_assignees,
    update_project,
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


async def _make_project(
    session_factory, unique: str, tag: str, key_prefix: str | None = None
) -> str:
    """
    Create a throwaway FLAN project via the REAL create_project service.

    `key_prefix` defaults to a per-run unique one so nothing collides; scenario
    (B) passes an explicit "PRJ" instead, because the SRD names the literal
    `PRJ-9 → PRJ-10` case and because three projects sharing one prefix is how
    B5 shows a key is unique per PROJECT rather than globally.
    """
    async with session_factory() as session:
        project = await create_project(
            session,
            ProjectCreate(
                name=f"VERIFY-FLAN {tag} {unique}",
                key_prefix=key_prefix or f"VF{unique.upper()}",
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


async def _make_task_row(
    session_factory,
    phase_id: str,
    summary: str,
    start: date | None = None,
    due: date | None = None,
) -> Task:
    """
    Create a task via the REAL create_task service and hand back the WHOLE row.

    Scenario (B) needs the server-generated `key` off the instance the service
    returned — reading it back with a second query would be asserting on the
    database rather than on what the service handed the router. `_make_task`
    below is this function with `.id` taken off the end.
    """
    async with session_factory() as session:
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


async def _make_task(
    session_factory,
    phase_id: str,
    summary: str,
    start: date | None = None,
    due: date | None = None,
) -> str:
    """Create a task via the REAL create_task service and the REAL TaskCreate schema."""
    task = await _make_task_row(session_factory, phase_id, summary, start, due)
    return task.id


async def _set_status(session_factory, task_id: str, status: str) -> None:
    """Flip a task's status through the REAL update_task service (PATCH semantics)."""
    async with session_factory() as session:
        await update_task(session, task_id, TaskUpdate(status=status))


async def _patch_task(session_factory, task_id: str, patch: TaskUpdate) -> Task:
    """Apply an arbitrary PATCH through the REAL update_task and return the row."""
    async with session_factory() as session:
        return await update_task(session, task_id, patch)


async def _read_task(session_factory, task_id: str) -> Task:
    """Read one task back through the REAL get_task — the read the router serves."""
    async with session_factory() as session:
        return await get_task(session, task_id)


async def _make_member(
    session_factory, project_id: str, name: str, user_id: str | None = None
) -> TeamMember:
    """Add a roster member via the REAL create_member service; return the row."""
    async with session_factory() as session:
        return await create_member(
            session,
            project_id,
            TeamMemberCreate(name=name, role="Engineer", color="#336699", user_id=user_id),
        )


async def _assign_task(session_factory, task_id: str, member_ids: list[str]) -> list[str]:
    """Set a task's assignee list through the REAL set_task_assignees service."""
    async with session_factory() as session:
        return await set_task_assignees(session, task_id, member_ids)


async def _assign_phase(session_factory, phase_id: str, member_ids: list[str]) -> list[str]:
    """Set a phase's assignee list through the REAL set_phase_assignees service."""
    async with session_factory() as session:
        return await set_phase_assignees(session, phase_id, member_ids)


async def _refusal_status(session_factory, call) -> int | None:
    """
    Run one service call that is EXPECTED to be refused and return the
    `HTTPException.status_code` it raised — `None` if it was not refused at all.

    Returning the status is the point: scenarios (C) and (E) assert on
    `exc.status_code`, never on the message text, so a 404 or a 409 arriving
    where a 422 was promised is a FAIL rather than a green "well, it raised".
    `call` takes the session, so each attempt gets its own — a refused call
    leaves nothing to commit.
    """
    async with session_factory() as session:
        try:
            await call(session)
        except HTTPException as exc:
            return exc.status_code
        return None

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
# (B) NUMERIC-SAFE TASK KEYS (FLAN-01.3, D-P8-6, D-V5P1-7)
# ---------------------------------------------------------------------------


async def _project_task_keys(session_factory, project_id: str) -> list[str]:
    """One project's task keys, in the order `list_tasks` — the REAL read — returns them."""
    async with session_factory() as session:
        tasks = await list_tasks(session, project_id)
    return [task.key for task in tasks]


async def _naive_max_key(session_factory, project_id: str) -> str | None:
    """
    The key a naive `MAX(key)` STRING aggregate would pick over the same rows.

    This is the generator FLAN deliberately does NOT use, computed here purely
    for contrast (the Task-13 form): keys are unpadded (D-V5P1-7), so `MAX(key)`
    is a LEXICOGRAPHIC maximum and still answers `PRJ-9` once `PRJ-10` exists —
    whose successor is a key the project already holds. Nothing in the suite
    calls this; it exists so the passing assertion below has something to be
    better than.
    """
    async with session_factory() as session:
        result = await session.execute(
            select(func.max(Task.key)).where(Task.project_id == project_id)
        )
        return result.scalar()


async def _force_duplicate_key(session_factory, task_id: str, key: str) -> str | None:
    """
    Aim a duplicate key at the database by hand and return its complaint —
    `None` means the write was ACCEPTED, which is the failure.

    A hand-write on purpose, and one of only two in this file (see the module
    docstring). The service layer cannot produce a duplicate key — that is the
    property being verified — so the only way to ask whether
    `uq_flan_task_project_key` is really enforced is to aim a write straight at
    it. Rolled back either way: nothing here persists.
    """
    async with session_factory() as session:
        try:
            await session.execute(update(Task).where(Task.id == task_id).values(key=key))
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            return str(getattr(exc, "orig", exc))
        await session.rollback()
        return None


async def scenario_b(session_factory, project_ids: set[str]) -> None:
    """
    Task keys are numbered NUMERICALLY, they are unique per PROJECT, and the
    numeric cast cannot overflow.

    THREE projects, all created with the SAME `PRJ` prefix — which is itself part
    of the point (B5): a key is unique within its project
    (`uq_flan_task_project_key`), not globally, so two projects may each hold a
    `PRJ-1` at the same moment.

    B4 contains the file's second and last hand-write, marked at the line: a
    legal 10-digit suffix is a key no service call can issue, and it is exactly
    the shape that made `PRJ-...` numbering 500 permanently in PLUM-01
    (`7562a02`) when the cast target was `Integer`.
    """
    unique = uuid.uuid4().hex[:8]
    project_id = await _make_project(session_factory, unique, "B", key_prefix="PRJ")
    project_ids.add(project_id)
    phase_id = await _make_phase(session_factory, project_id, f"B keys {unique}", 1)

    # --- B1: PRJ-9 -> PRJ-10, the SRD's own named case ----------------------
    keys = [
        (await _make_task_row(session_factory, phase_id, f"B task {n}")).key
        for n in range(1, 10)
    ]
    check(
        "(B1/FLAN-01.3) nine tasks created through the REAL create_task are keyed "
        "PRJ-1 … PRJ-9 — unpadded (D-V5P1-7), never PRJ-0001",
        keys == [f"PRJ-{n}" for n in range(1, 10)],
        f"keys={keys}",
    )

    tenth = await _make_task_row(session_factory, phase_id, "B tenth task")
    check(
        "(B1/FLAN-01.3) the task created after PRJ-9 is PRJ-10 — the NUMERIC "
        "successor, which is the verification the SRD names literally",
        tenth.key == "PRJ-10",
        f"key={tenth.key!r}",
    )

    # --- B2: the naive MAX(key) contrast, and the ordering consequence ------
    naive = await _naive_max_key(session_factory, project_id)
    eleventh = await _make_task_row(session_factory, phase_id, "B eleventh task")
    check(
        "(B2/D-P8-6) with PRJ-1 … PRJ-10 in the project a plain MAX(key) STRING "
        "aggregate answers 'PRJ-9', whose successor PRJ-10 the project ALREADY "
        "holds — i.e. the naive generator would re-issue a live key. The real one "
        "answers PRJ-11",
        naive == "PRJ-9" and tenth.key == "PRJ-10" and eleventh.key == "PRJ-11",
        f"naive_max={naive!r} real_next={eleventh.key!r}",
    )

    ordered = await _project_task_keys(session_factory, project_id)
    check(
        "(B2/D-V5P1-7) list_tasks orders on the NUMERIC suffix — PRJ-1 … PRJ-11, "
        "not the lexicographic PRJ-1, PRJ-10, PRJ-11, PRJ-2 a string sort gives",
        ordered == [f"PRJ-{n}" for n in range(1, 12)],
        f"order={ordered}",
    )

    # --- B3: two tasks in one project can NEVER share a key -----------------
    complaint = await _force_duplicate_key(session_factory, eleventh.id, "PRJ-1")
    check(
        "(B3/FLAN-01.3) the database REFUSES a second PRJ-1 in the same project — "
        "uq_flan_task_project_key is the authoritative backstop behind the "
        "generator, and the eleven issued keys are all distinct",
        complaint is not None
        and "uq_flan_task_project_key" in complaint
        and len(set(ordered)) == len(ordered) == 11,
        f"complaint={complaint!r} keys={ordered}",
    )

    # --- B4: the digit boundary — Numeric, NEVER Integer (7562a02) ----------
    big_project_id = await _make_project(
        session_factory, unique, "B-bigkey", key_prefix="PRJ"
    )
    project_ids.add(big_project_id)
    big_phase_id = await _make_phase(session_factory, big_project_id, f"B big {unique}", 1)
    seed = await _make_task_row(session_factory, big_phase_id, "B 10-digit seed")

    # THE HAND-WRITE, marked as the module docstring promises: `flan_task.key` is
    # String(20) with no format constraint, so PRJ-9999999999 is a LEGAL key —
    # but no legal service call can produce one, so a direct write is the only
    # way to put the project in that state. Everything after this line goes back
    # through the REAL service.
    async with session_factory() as session:
        await session.execute(
            update(Task).where(Task.id == seed.id).values(key="PRJ-9999999999")
        )
        await session.commit()

    try:
        produced = (
            await _make_task_row(session_factory, big_phase_id, "B after 10 digits")
        ).key
    except Exception as exc:  # an Integer cast raises here — report it as a FAIL
        produced = f"{type(exc).__name__}: {exc}"
    check(
        "(B4/D-P8-6) a project holding the legal 10-digit key PRJ-9999999999 — a "
        "suffix that OVERFLOWS int4 — still creates its next task, keyed "
        "PRJ-10000000000: the cast target is Numeric, NEVER Integer, so one such "
        "key cannot 500 every create in the project permanently (PLUM-01 7562a02)",
        produced == "PRJ-10000000000",
        f"produced={produced!r}",
    )

    # --- B5: two DIFFERENT projects may both hold PRJ-1 ---------------------
    twin_project_id = await _make_project(
        session_factory, unique, "B-twin", key_prefix="PRJ"
    )
    project_ids.add(twin_project_id)
    twin_phase_id = await _make_phase(
        session_factory, twin_project_id, f"B twin {unique}", 1
    )
    twin = await _make_task_row(session_factory, twin_phase_id, "B twin first task")
    async with session_factory() as session:
        result = await session.execute(
            select(func.count())
            .select_from(Task)
            .where(
                Task.project_id.in_([project_id, twin_project_id]),
                Task.key == "PRJ-1",
            )
        )
        twin_rows = int(result.scalar_one())
    check(
        "(B5/FLAN-01.3) a SECOND project with the same prefix numbers from PRJ-1 "
        "independently — both projects hold a live PRJ-1 at once, because the key "
        "is unique per PROJECT and not globally",
        twin.key == "PRJ-1" and twin_rows == 2,
        f"twin_key={twin.key!r} rows_keyed_PRJ-1={twin_rows}",
    )


# ---------------------------------------------------------------------------
# (C) DATE VALIDATION — due < start (FLAN-01.3)
# ---------------------------------------------------------------------------


async def scenario_c(session_factory, project_ids: set[str]) -> None:
    """
    `due < start` is refused at CREATE and on the PATCH that moves only ONE of
    the two dates; `due == start` is a valid zero-duration milestone.

    The two refusals come from two different layers on purpose. At create the
    payload carries both dates, so `schemas.py::_check_date_order` sees the pair
    and pydantic refuses it — which is precisely what FastAPI renders as HTTP 422
    for a request body, so the failure is asserted here in the shape it really
    has (a `ValidationError`) rather than dressed up as an `HTTPException`. On a
    PATCH that moves only `start_date` the schema has no `due_date` to compare
    against and passes by construction; the refusal there is the SERVICE's
    merged-value check, it carries a real status, and it IS asserted on
    `exc.status_code`.
    """
    unique = uuid.uuid4().hex[:8]
    project_id = await _make_project(session_factory, unique, "C")
    project_ids.add(project_id)
    phase_id = await _make_phase(session_factory, project_id, f"C dates {unique}", 1)

    # --- C1: due < start is refused at CREATE, and nothing lands ------------
    refusal: ValidationError | None = None
    try:
        TaskCreate(
            phase_id=phase_id,
            summary="C backwards task",
            start_date=date(2026, 5, 10),
            due_date=date(2026, 5, 9),
        )
    except ValidationError as exc:
        refusal = exc
    async with session_factory() as session:
        result = await session.execute(
            select(func.count()).select_from(Task).where(Task.project_id == project_id)
        )
        landed = int(result.scalar_one())
    check(
        "(C1/FLAN-01.3) a create carrying due 2026-05-09 before start 2026-05-10 is "
        "REFUSED by the very schema the router builds the payload with (the 422 "
        "FastAPI renders for a request body), and no task row lands",
        refusal is not None and "must not precede" in str(refusal) and landed == 0,
        f"refusal={refusal!r} rows_in_project={landed}",
    )

    # --- C2: the PATCH that moves ONLY start_date ---------------------------
    task = await _make_task_row(
        session_factory, phase_id, "C moving task", date(2026, 5, 1), date(2026, 5, 5)
    )
    status_code = await _refusal_status(
        session_factory,
        lambda s: update_task(s, task.id, TaskUpdate(start_date=date(2026, 5, 9))),
    )
    unchanged = await _read_task(session_factory, task.id)
    check(
        "(C2/FLAN-01.3) a PATCH that moves ONLY start_date (to 2026-05-09, past the "
        "stored due 2026-05-05) is refused with 422 by the SERVICE's MERGED-value "
        "check — the schema passes it by construction, having no due_date in the "
        "payload to compare it against — and the stored row is left untouched",
        status_code == 422
        and unchanged.start_date == date(2026, 5, 1)
        and unchanged.due_date == date(2026, 5, 5),
        f"status={status_code!r} start={unchanged.start_date!r} "
        f"due={unchanged.due_date!r}",
    )

    legal = await _patch_task(
        session_factory, task.id, TaskUpdate(start_date=date(2026, 5, 3))
    )
    check(
        "(C2/FLAN-01.3) the SAME one-date PATCH shape with a legal value is ACCEPTED "
        "(start → 2026-05-03, due still 2026-05-05) — the merged check refuses the "
        "bad order, not the shape",
        legal.start_date == date(2026, 5, 3) and legal.due_date == date(2026, 5, 5),
        f"start={legal.start_date!r} due={legal.due_date!r}",
    )

    # --- C3: due == start is a valid zero-duration milestone ----------------
    milestone = await _make_task_row(
        session_factory, phase_id, "C milestone", date(2026, 6, 1), date(2026, 6, 1)
    )
    read_back = await _read_task(session_factory, milestone.id)
    check(
        "(C3/FLAN-01.3) due == start SUCCEEDS at create and reads back through the "
        "REAL get_task as a zero-duration milestone: start_date == due_date == "
        "2026-06-01",
        read_back.start_date == date(2026, 6, 1)
        and read_back.due_date == date(2026, 6, 1),
        f"start={read_back.start_date!r} due={read_back.due_date!r}",
    )

    squashed = await _patch_task(
        session_factory, task.id, TaskUpdate(due_date=date(2026, 5, 3))
    )
    check(
        "(C3/FLAN-01.3) and a PATCH that pulls due back to EQUAL start (2026-05-03) "
        "is accepted too — the merged check refuses only due < start",
        squashed.start_date == date(2026, 5, 3)
        and squashed.due_date == date(2026, 5, 3),
        f"start={squashed.start_date!r} due={squashed.due_date!r}",
    )


# ---------------------------------------------------------------------------
# (D) ROSTER REMOVAL — clears assignments, leaves the work alone (FLAN-01.4)
# ---------------------------------------------------------------------------


async def _make_user(session_factory, unique: str) -> str:
    """
    Create a throwaway platform user through the REAL auth create_user service.

    (D)'s second half needs a member whose `user_id` link points at a real row,
    because the claim under test is about what deactivating THAT user does to
    the roster. The address carries the `verify-flan-roster-` marker that
    `_drop_verify_users` sweeps on.
    """
    async with session_factory() as session:
        user = await create_user(
            session,
            email=f"verify-flan-roster-{unique}@example.test",
            password="verify-flan-roster-pw",
            full_name="VERIFY FLAN roster link",
        )
        return user.id


async def _drop_verify_users(session_factory) -> None:
    """
    Delete this file's throwaway platform users — matched by EMAIL PATTERN, not
    by id, so a run killed mid-scenario is swept by the next one and the script
    stays re-runnable.

    `flan_team_member.user_id` is ON DELETE SET NULL (models.py), so this can run
    before or after the roster rows go and never takes project history with it.
    Users are the one throwaway row this file creates that the project-keyed
    `_cleanup` cannot reach, which is why scenario (D) calls this in its own
    `finally` rather than leaving it to the driver.
    """
    async with session_factory() as session:
        await session.execute(
            delete(User).where(User.email.like("verify-flan-roster-%@example.test"))
        )
        await session.commit()


async def _task_snapshot(session_factory, task_ids: list[str]) -> dict[str, tuple]:
    """
    Snapshot each task's summary, status, dates AND `updated_at`, read through
    the REAL get_task.

    `updated_at` is the load-bearing member of that tuple (the Task-15 form):
    "removing a member leaves the tasks intact" is a claim that no task row was
    loaded, dirtied or re-saved, and only a byte-identical timestamp can show it.
    "The row still exists" is a strictly weaker statement.
    """
    snapshot: dict[str, tuple] = {}
    async with session_factory() as session:
        for task_id in task_ids:
            task = await get_task(session, task_id)
            snapshot[task_id] = (
                task.summary,
                task.status,
                task.start_date,
                task.due_date,
                task.updated_at,
            )
    return snapshot


async def _assignment_counts(session_factory, member_id: str) -> tuple[int, int]:
    """One member's `(task assignment rows, phase assignment rows)`."""
    async with session_factory() as session:
        tasks = await session.execute(
            select(func.count())
            .select_from(TaskAssignee)
            .where(TaskAssignee.member_id == member_id)
        )
        phases = await session.execute(
            select(func.count())
            .select_from(PhaseAssignee)
            .where(PhaseAssignee.member_id == member_id)
        )
        return int(tasks.scalar_one()), int(phases.scalar_one())


async def _member_snapshot(session_factory, member_id: str) -> tuple:
    """Every field of a roster row, for a byte-identity comparison."""
    async with session_factory() as session:
        member = await session.get(TeamMember, member_id)
        if member is None:
            return ()
        return (
            member.name,
            member.role,
            member.email,
            member.color,
            member.hourly_rate,
            member.user_id,
            member.active,
            member.created_at,
        )


async def scenario_d(session_factory, project_ids: set[str]) -> None:
    """
    Removing a roster member clears THAT member's assignments and touches nothing
    else; deactivating a linked platform user touches nothing at all.

    Two members are rostered because the interesting half of D-V5P1-6 is what
    does NOT happen: the assignment deletes are scoped by `member_id`, never by
    `task_id`, so the second member's row on the SHARED task has to survive. One
    member alone cannot see that mistake.

    The platform-user column is `users.is_active` (auth/models.py) and the
    deactivation goes through the REAL auth `update_user`, which is the path the
    admin UI uses.
    """
    unique = uuid.uuid4().hex[:8]
    project_id = await _make_project(session_factory, unique, "D")
    project_ids.add(project_id)
    phase_id = await _make_phase(session_factory, project_id, f"D roster {unique}", 1)
    task_one = await _make_task_row(
        session_factory, phase_id, "D shared task", date(2026, 8, 3), date(2026, 8, 7)
    )
    task_two = await _make_task_row(
        session_factory, phase_id, "D solo task", date(2026, 8, 4), None
    )

    user_id = await _make_user(session_factory, unique)
    try:
        leaver = await _make_member(session_factory, project_id, f"D leaver {unique}")
        stayer = await _make_member(
            session_factory, project_id, f"D stayer {unique}", user_id=user_id
        )

        await _assign_task(session_factory, task_one.id, [leaver.id, stayer.id])
        await _assign_task(session_factory, task_two.id, [leaver.id])
        await _assign_phase(session_factory, phase_id, [leaver.id, stayer.id])

        before = await _task_snapshot(session_factory, [task_one.id, task_two.id])
        leaver_before = await _assignment_counts(session_factory, leaver.id)

        async with session_factory() as session:
            cleared = await remove_member(session, leaver.id)

        after = await _task_snapshot(session_factory, [task_one.id, task_two.id])
        leaver_after = await _assignment_counts(session_factory, leaver.id)
        stayer_after = await _assignment_counts(session_factory, stayer.id)
        async with session_factory() as session:
            phase_alive = await session.get(Phase, phase_id) is not None
        leaver_row = await _member_snapshot(session_factory, leaver.id)

        check(
            "(D1/FLAN-01.4) a member assigned to 2 tasks and 1 phase is removed "
            "through the REAL remove_member: it reports 3 assignments cleared and "
            "the member is left with none",
            leaver_before == (2, 1) and cleared == 3 and leaver_after == (0, 0),
            f"before={leaver_before} cleared={cleared} after={leaver_after}",
        )
        check(
            "(D1/FLAN-01.4 LITERAL) both tasks come through byte-identical — summary, "
            "status, start_date, due_date AND updated_at unchanged, so no task row "
            "was loaded, dirtied or re-saved — and the phase still exists",
            after == before and phase_alive,
            f"before={before} after={after} phase_alive={phase_alive}",
        )
        check(
            "(D1/D-V5P1-6) the deletes are scoped by member_id and never by task_id: "
            "the OTHER member keeps her row on the SHARED task and on the phase",
            stayer_after == (1, 1),
            f"stayer={stayer_after}",
        )
        check(
            "(D1/D-V5P1-6) and the removal is SOFT — the roster row survives with its "
            "name, role, colour and user link intact and only `active` cleared",
            leaver_row[:4] == (f"D leaver {unique}", "Engineer", None, "#336699")
            and leaver_row[6] is False,
            f"leaver_row={leaver_row!r}",
        )

        # --- D2: deactivating the LINKED platform user changes nothing ------
        stayer_before = await _member_snapshot(session_factory, stayer.id)
        stayer_counts_before = await _assignment_counts(session_factory, stayer.id)
        async with session_factory() as session:
            user = await update_user(session, user_id, is_active=False)
            deactivated = user.is_active
        stayer_snapshot_after = await _member_snapshot(session_factory, stayer.id)
        stayer_counts_after = await _assignment_counts(session_factory, stayer.id)
        check(
            "(D2/FLAN-01.4) deactivating the LINKED platform user (users.is_active → "
            "False, through the REAL auth update_user) leaves the roster untouched: "
            "name, role, email, colour, rate, user link, active flag and created_at "
            "all identical, and the member keeps her 1 task + 1 phase assignment",
            deactivated is False
            and stayer_snapshot_after == stayer_before
            and stayer_counts_after == stayer_counts_before == (1, 1),
            f"is_active={deactivated!r} before={stayer_before!r} "
            f"after={stayer_snapshot_after!r} counts={stayer_counts_after}",
        )
    finally:
        await _drop_verify_users(session_factory)


# ---------------------------------------------------------------------------
# (E) AN ARCHIVED PROJECT REJECTS WRITES — and stays readable (FLAN-01.1)
# ---------------------------------------------------------------------------


async def _project_state(session_factory, project_id: str) -> dict:
    """
    Everything a READ of one project returns, through the REAL read services:
    the project row and its tags, its phases WITH their derived rollups, its
    tasks with dates and assignees, and its roster.

    `active` is deliberately NOT in here. Archiving flips exactly that flag and
    nothing else, so it is asserted on its own and this dict can be compared for
    equality across the archive.
    """
    async with session_factory() as session:
        project = await get_project(session, project_id)
        phases = await list_phases(session, project_id)
        tasks = await list_tasks(session, project_id)
        members = await list_members(session, project_id)
        return {
            "project": (
                project.name,
                project.key_prefix,
                project.category,
                tuple(project.tags),
            ),
            "phases": [
                (
                    phase.id,
                    phase.name,
                    phase.derived_start_date,
                    phase.derived_due_date,
                    phase.percent_complete,
                    phase.task_count,
                )
                for phase in phases
            ],
            "tasks": [
                (
                    task.id,
                    task.key,
                    task.summary,
                    task.start_date,
                    task.due_date,
                    tuple(task.assignee_ids),
                )
                for task in tasks
            ],
            "members": [(member.id, member.name, member.active) for member in members],
        }


async def scenario_e(session_factory, project_ids: set[str]) -> None:
    """
    Archiving a project freezes EVERY write inside it (422) and changes nothing
    a reader can see.

    The fixtures are built with the very calls that are refused afterwards —
    `create_phase`, `create_task`, `create_member`, `set_task_assignees` all
    succeed against the live project a few lines above — so the 422s below cannot
    be a service that was broken all along.
    """
    unique = uuid.uuid4().hex[:8]
    project_id = await _make_project(session_factory, unique, "E")
    project_ids.add(project_id)
    phase_id = await _make_phase(session_factory, project_id, f"E frozen {unique}", 1)
    task = await _make_task_row(
        session_factory, phase_id, "E task", date(2026, 9, 1), date(2026, 9, 4)
    )
    member = await _make_member(session_factory, project_id, f"E member {unique}")
    await _assign_task(session_factory, task.id, [member.id])

    before = await _project_state(session_factory, project_id)
    check(
        "(E/FLAN-01.1) the project is REAL before it is archived: one phase whose "
        "rollup derives 2026-09-01 → 2026-09-04 from its one task, one task with an "
        "assignee, one roster member — all built through the same services archiving "
        "is about to refuse",
        len(before["phases"]) == 1
        and before["phases"][0][2] == date(2026, 9, 1)
        and before["phases"][0][3] == date(2026, 9, 4)
        and len(before["tasks"]) == 1
        and before["tasks"][0][5] == (member.id,)
        and len(before["members"]) == 1,
        f"state={before}",
    )

    async with session_factory() as session:
        archived = await archive_project(session, project_id)

    refusals = {
        "create_phase": await _refusal_status(
            session_factory,
            lambda s: create_phase(s, project_id, PhaseCreate(name="E late phase")),
        ),
        "create_task": await _refusal_status(
            session_factory,
            lambda s: create_task(s, TaskCreate(phase_id=phase_id, summary="E late task")),
        ),
        "update_task": await _refusal_status(
            session_factory,
            lambda s: update_task(s, task.id, TaskUpdate(status="Done")),
        ),
        "create_member": await _refusal_status(
            session_factory,
            lambda s: create_member(
                s, project_id, TeamMemberCreate(name="E late member")
            ),
        ),
        "set_task_assignees": await _refusal_status(
            session_factory, lambda s: set_task_assignees(s, task.id, [])
        ),
        "update_project": await _refusal_status(
            session_factory,
            lambda s: update_project(s, project_id, ProjectUpdate(name="E renamed")),
        ),
    }
    check(
        "(E/FLAN-01.1) an ARCHIVED project refuses EVERY write inside it with 422 — "
        "create_phase, create_task, update_task, create_member, set_task_assignees "
        "and update_project alike, not merely writes to the project row",
        set(refusals.values()) == {422},
        f"refusals={refusals}",
    )

    after = await _project_state(session_factory, project_id)
    check(
        "(E/FLAN-01.1) archiving is a SOFT delete: a READ of the same project still "
        "returns ALL of it — name, key_prefix, category, tags, the phase with its "
        "derived rollup, the task with its dates and assignee, and the roster — with "
        "`active` the only thing that changed",
        after == before and archived.active is False,
        f"active={archived.active!r} before={before} after={after}",
    )


# ---------------------------------------------------------------------------
# (F) DELETING A PHASE CASCADES TO ITS TASKS — and only its own (FLAN-01.2)
# ---------------------------------------------------------------------------


async def _phase_task_count(session_factory, phase_id: str) -> int:
    """`SELECT count(*) FROM flan_task WHERE phase_id = :id` — the plan's own probe."""
    async with session_factory() as session:
        result = await session.execute(
            select(func.count()).select_from(Task).where(Task.phase_id == phase_id)
        )
        return int(result.scalar_one())


async def scenario_f(session_factory, project_ids: set[str]) -> None:
    """
    Deleting a phase takes its tasks with it — in the DATABASE, via
    `flan_task.phase_id ON DELETE CASCADE` — and takes nothing else.

    A SIBLING phase with its own tasks lives in the same project throughout: a
    cascade scoped to the project instead of the phase would empty it too, and
    with only one phase in the fixture that mistake would pass unseen.
    """
    unique = uuid.uuid4().hex[:8]
    project_id = await _make_project(session_factory, unique, "F")
    project_ids.add(project_id)
    doomed_id = await _make_phase(session_factory, project_id, f"F doomed {unique}", 1)
    sibling_id = await _make_phase(session_factory, project_id, f"F sibling {unique}", 2)

    doomed_tasks = [
        (await _make_task_row(session_factory, doomed_id, f"F doomed task {n}")).id
        for n in (1, 2, 3)
    ]
    sibling_tasks = [
        (await _make_task_row(session_factory, sibling_id, f"F sibling task {n}")).id
        for n in (1, 2)
    ]

    doomed_before = await _phase_task_count(session_factory, doomed_id)
    sibling_before = await _task_snapshot(session_factory, sibling_tasks)

    async with session_factory() as session:
        reported = await delete_phase(session, doomed_id)

    doomed_after = await _phase_task_count(session_factory, doomed_id)
    sibling_after_count = await _phase_task_count(session_factory, sibling_id)
    sibling_after = await _task_snapshot(session_factory, sibling_tasks)
    async with session_factory() as session:
        orphans = await session.execute(
            select(func.count()).select_from(Task).where(Task.id.in_(doomed_tasks))
        )
        surviving_rows = int(orphans.scalar_one())
        doomed_gone = await session.get(Phase, doomed_id) is None
        sibling_alive = await session.get(Phase, sibling_id) is not None
    remaining_phases = await _listed_phases(session_factory, project_id)

    check(
        "(F/FLAN-01.2) a phase holding 3 tasks is deleted through the REAL "
        "delete_phase, which reports the 3 that went with it: count(*) FROM "
        "flan_task WHERE phase_id = <deleted> falls 3 → 0",
        doomed_before == 3 and reported == 3 and doomed_after == 0,
        f"before={doomed_before} reported={reported} after={doomed_after}",
    )
    check(
        "(F/FLAN-01.2) and the three task ROWS are gone, not orphaned onto a dangling "
        "phase_id — the cascade is the database's (ON DELETE CASCADE), so it cannot "
        "be half-applied by a service that forgot a table",
        surviving_rows == 0 and doomed_gone,
        f"surviving_rows={surviving_rows} phase_gone={doomed_gone}",
    )
    check(
        "(F/FLAN-01.2) the SIBLING phase's 2 tasks in the SAME project are untouched "
        "— same rows, same summaries, same dates, same updated_at — so the cascade is "
        "scoped by phase_id and not by project",
        sibling_after == sibling_before and sibling_after_count == 2,
        f"before={sibling_before} after={sibling_after} count={sibling_after_count}",
    )
    check(
        "(F/FLAN-01.2) the project itself and the sibling phase survive: list_phases "
        "now returns exactly the sibling, with its own real rollup",
        sibling_alive
        and list(remaining_phases) == [sibling_id]
        and remaining_phases[sibling_id].task_count == 2,
        f"phases={[p.name for p in remaining_phases.values()]}",
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
        # Each scenario is independent and registers every project it creates
        # in `project_ids`; the cleanup below reaches all their phases, tasks,
        # members, tags and assignee rows through those ids alone. A new
        # scenario is one `async def scenario_x(session_factory, project_ids)`
        # above and one call here.
        await scenario_b(session_factory, project_ids)
        await scenario_c(session_factory, project_ids)
        await scenario_d(session_factory, project_ids)
        await scenario_e(session_factory, project_ids)
        await scenario_f(session_factory, project_ids)
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
