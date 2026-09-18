# ABOUTME: The D-V5P1-2 key_prefix invariant under CONCURRENCY (verify-1 finding 1) plus the
# ABOUTME: derived-prefix shape guarantee (finding 2). Proves create_task reads the prefix THROUGH
# ABOUTME: its row lock rather than off the identity map, that update_project holds that same lock
# ABOUTME: across its has-tasks check, and that a derived prefix always matches KEY_PREFIX_PATTERN.
"""FLAN key_prefix locking + derivation crux.

WHY THIS EXISTS (the two verify-1 findings this module pins):

  **(A1) The project-row lock has to actually serialize.** D-V5P1-2 says a
  project's ``key_prefix`` is editable only until its first task exists, so that
  no project ever advertises ``CRIS`` while holding a ``PRJ-1``. That state is
  unrepairable through the API — once the task exists, ``update_project`` 422s
  every subsequent prefix change forever — so the invariant is only worth
  anything if it survives two concurrent requests. It was breaking in two
  independent ways, and each has its own test here:

    * ``create_task`` locked the row and then read the prefix off an instance
      ``require_writable_project`` had already put in the session's identity map
      via ``db.get``. SQLAlchemy returns that mapped instance from the
      ``FOR UPDATE`` select **without repopulating it**, so the value read was
      the pre-lock snapshot — the lock serialized nothing it then used. Pinned
      by ``test_create_task_reads_the_prefix_through_the_lock``.
    * ``update_project`` never took the lock at all (a plain ``db.get`` into
      ``_project_has_tasks``), so ``create_task``'s ``FOR UPDATE`` had nothing
      to block against. Pinned by
      ``test_update_project_holds_the_row_lock_across_the_has_tasks_check``,
      which asks an INDEPENDENT session for the same row ``FOR UPDATE NOWAIT``
      at the moment of the has-tasks read: 55P03 means the lock is held, success
      means it is not.

    ``test_prefix_change_and_first_task_create_serialize`` then drives the real
    interleaving end to end — the create is spawned from inside the PATCH's
    has-tasks check, must BLOCK until the PATCH commits, and the end state must
    be a project and a task that agree on the prefix.

  **(A2) A derived prefix must honour the shape a client-supplied one does.**
  ``keys.py`` interpolates ``key_prefix`` into ``^{prefix}-[0-9]+$``; its safety
  argument rests on every prefix matching ``KEY_PREFIX_PATTERN``. ``isalnum()``
  and ``upper()`` are Unicode-aware and the ``[:4]`` slice runs BEFORE the
  uppercasing, so "Café Simulator" derived the non-conforming ``CAFÉ`` and
  "ﬃﬃﬃﬃ" (U+FB03, alnum) derived the 12-character ``FFIFFIFFIFFI`` — an
  overflow of ``key_prefix VARCHAR(10)`` and an unhandled 500 on create.

MUTATION PROOF (SC2 red-on-revert — each fix has exactly one test that catches
its removal):
  * drop ``populate_existing`` from ``create_task``'s ``with_for_update()``
    select → ``test_create_task_reads_the_prefix_through_the_lock`` goes RED
    (``PRJ-1`` instead of ``CRIS-1``);
  * drop the ``with_for_update()`` select from ``update_project`` → the NOWAIT
    probe acquires the row and
    ``test_update_project_holds_the_row_lock_across_the_has_tasks_check`` goes
    RED, and ``test_prefix_change_and_first_task_create_serialize`` goes RED
    with the documented corruption (project ``CRIS``, task ``PRJ-1``);
  * revert ``derive_key_prefix``'s ``re.fullmatch`` → ``CAFÉ`` fails the pattern
    assertion and the ligature name 500s the create with 22001.

D-P2b-5: every fixture is built through the REAL service and the REAL schemas
(``create_project`` / ``create_phase`` / ``create_task`` / ``update_project``);
nothing here is a hand-inserted ORM row. Concurrency is expressed with
INDEPENDENT sessions off the conftest NullPool sessionmaker, which opens a real
connection per checkout — two sessions are two Postgres backends, which is what
makes ``FOR UPDATE`` observable at all.
"""
from __future__ import annotations

import asyncio
import re

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (flan_team_member.user_id FKs into users.id — the Task-16 lesson).
import app.core.models  # noqa: F401
from app.modules.flan.models import Project
from app.modules.flan.schemas import (
    KEY_PREFIX_PATTERN,
    PhaseCreate,
    ProjectCreate,
    ProjectUpdate,
    TaskCreate,
)
from app.modules.flan.service import (
    create_phase,
    create_project,
    create_task,
    derive_key_prefix,
    update_project,
)
from app.modules.flan.service import projects as projects_service
from app.modules.flan.service._common import get_project_or_404

#: Postgres SQLSTATE for "could not obtain lock" — what FOR UPDATE NOWAIT raises
#: when another transaction already holds the row lock (55P03).
LOCK_NOT_AVAILABLE = "55P03"

#: How long a blocked call is given to (not) finish before the test concludes it
#: really is blocked. Generous enough not to flake on a loaded box, short enough
#: that a broken lock fails the suite in seconds rather than hanging it.
BLOCKED_TIMEOUT_SECONDS = 2.0


# ---------------------------------------------------------------------------
# Fixture builders — REAL service, REAL schemas (D-P2b-5)
# ---------------------------------------------------------------------------


async def _make_project(session, tag: str, key_prefix: str = "PRJ") -> Project:
    """
    Create a FLAN project via the REAL create_project service; return the row.

    The INSTANCE is returned, not just its id, and callers below deliberately
    keep it alive: the Session identity map holds objects WEAKLY, so a project
    nobody references is garbage-collected out of the map and the next `db.get`
    silently re-loads it from the database. A test that let that happen would be
    vacuous against the identity-map staleness it exists to catch — it would
    pass with or without `populate_existing` (confirmed empirically while
    mutation-proving this module).
    """
    return await create_project(
        session,
        ProjectCreate(
            name=f"FLAN prefix lock {tag}",
            key_prefix=key_prefix,
            category="work",
            currency="USD",
        ),
    )


async def _make_phase(session, project_id: str, name: str = "Build") -> str:
    """Create a phase via the REAL create_phase service; return its id."""
    phase = await create_phase(
        session,
        project_id,
        PhaseCreate(name=name, sort_order=1, status="in-progress"),
    )
    return phase.id


async def _stored_prefix(session, project_id: str) -> str:
    """Read key_prefix straight from the table (independent oracle, no ORM cache)."""
    return (
        await session.execute(
            select(Project.key_prefix).where(Project.id == project_id)
        )
    ).scalar_one()


async def _row_lock_is_held(sessionmaker, project_id: str) -> bool:
    """
    Ask an INDEPENDENT session for the project row ``FOR UPDATE NOWAIT``.

    Returns True when Postgres refuses with 55P03 (somebody else holds the row
    lock) and False when the lock is granted (nobody does). NOWAIT is what makes
    this a probe rather than a hang; anything other than 55P03 is re-raised, so
    a typo'd table name cannot masquerade as "the lock is held".
    """
    async with sessionmaker() as probe:
        try:
            await probe.execute(
                text("SELECT 1 FROM flan_project WHERE id = :id FOR UPDATE NOWAIT"),
                {"id": project_id},
            )
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) != LOCK_NOT_AVAILABLE:
                raise
            return True
        finally:
            await probe.rollback()
    return False


# ---------------------------------------------------------------------------
# (A1a) create_task must read the prefix THROUGH the lock
# ---------------------------------------------------------------------------


async def test_create_task_reads_the_prefix_through_the_lock(test_sessionmaker):
    """
    The prefix create_task issues a key under is the POST-lock value, not the
    identity-map snapshot ``require_writable_project``'s ``db.get`` left behind.

    Two independent sessions: session 1 holds the project it loaded (with
    ``expire_on_commit=False`` the instance keeps its attributes), session 2
    commits a prefix change from a different connection, and session 1 then
    creates a task. The key must carry ``CRIS``. Without ``populate_existing``
    on the ``FOR UPDATE`` select, session 1 re-reads its own stale ``PRJ`` and
    issues ``PRJ-1`` — a task whose prefix disagrees with the project that owns
    it, which is the exact state D-V5P1-2 forbids.
    """
    async with test_sessionmaker() as session_one, test_sessionmaker() as session_two:
        # `project` is held for the whole test ON PURPOSE (see _make_project):
        # it is the identity-mapped, pre-lock snapshot create_task must not
        # trust, and dropping the reference would collect it and make this test
        # pass against the very mutation it is here to catch.
        project = await _make_project(session_one, "A1a")
        project_id = project.id
        phase_id = await _make_phase(session_one, project_id)

        # Session 2 (a different connection) commits the prefix change.
        await update_project(session_two, project_id, ProjectUpdate(key_prefix="CRIS"))
        assert await _stored_prefix(session_two, project_id) == "CRIS"

        # Precondition, asserted rather than assumed: session 1 still carries
        # the OLD value on its mapped instance. If this ever reads "CRIS" the
        # test has stopped exercising the staleness and must be repaired, not
        # trusted.
        assert project.key_prefix == "PRJ"

        task = await create_task(
            session_one,
            TaskCreate(phase_id=phase_id, summary="Issued after the prefix moved"),
        )

    assert task.key == "CRIS-1", (
        "create_task issued its key under the pre-lock identity-map snapshot "
        f"({task.key!r}) instead of the committed prefix CRIS — the FOR UPDATE "
        "select needs populate_existing"
    )


# ---------------------------------------------------------------------------
# (A1b) update_project must HOLD the row lock across the has-tasks check
# ---------------------------------------------------------------------------


async def test_update_project_holds_the_row_lock_across_the_has_tasks_check(
    test_sessionmaker, monkeypatch
):
    """
    A prefix PATCH locks the project row BEFORE reading whether it has tasks,
    and still holds that lock when the read happens.

    The probe runs from an independent session at the one instant that matters —
    inside ``_project_has_tasks`` — and asks for the same row ``FOR UPDATE
    NOWAIT``. Granted means ``create_task``'s ``FOR UPDATE`` has nothing to
    block on and the whole D-V5P1-2 invariant is decoration; refused with 55P03
    means the two writers genuinely contend on one row.
    """
    observed: dict[str, bool] = {}
    real_has_tasks = projects_service._project_has_tasks

    async def probing_has_tasks(db, project_id: str) -> bool:
        observed["locked"] = await _row_lock_is_held(test_sessionmaker, project_id)
        return await real_has_tasks(db, project_id)

    monkeypatch.setattr(projects_service, "_project_has_tasks", probing_has_tasks)

    async with test_sessionmaker() as session:
        project_id = (await _make_project(session, "A1b")).id
        await update_project(session, project_id, ProjectUpdate(key_prefix="CRIS"))

        assert observed["locked"] is True, (
            "another session took FOR UPDATE on the project row while "
            "update_project was deciding whether the prefix may change — the "
            "PATCH is not holding the row lock create_task contends for"
        )
        assert await _stored_prefix(session, project_id) == "CRIS"


# ---------------------------------------------------------------------------
# (A1) The interleaving itself — PATCH prefix vs. first task create
# ---------------------------------------------------------------------------


async def test_prefix_change_and_first_task_create_serialize(test_sessionmaker, monkeypatch):
    """
    The reviewer's interleaving, driven deterministically: a first-task create
    that starts while a prefix PATCH is mid-flight must WAIT for that PATCH and
    then number under the new prefix.

    ``create_task`` is spawned from inside the PATCH's has-tasks check — so it
    has already loaded the project at the OLD prefix — and must not complete
    while the PATCH holds the row. When both are done, the project's stored
    prefix and its only task's key must agree. Unfixed, the create sails through
    and commits ``PRJ-1`` into a project that goes on to advertise ``CRIS``,
    a mismatch no endpoint can repair.
    """
    async with test_sessionmaker() as setup_session:
        project_id = (await _make_project(setup_session, "A1-race")).id
        phase_id = await _make_phase(setup_session, project_id)

    creator_session = test_sessionmaker()
    # The creating session loads the project BEFORE the PATCH commits and keeps
    # it (the identity map is weak — see _make_project), so this test carries
    # both halves of the finding: the create must block on the row lock AND, once
    # through, must read the prefix the lock serialized rather than this snapshot.
    creator_snapshot = await get_project_or_404(creator_session, project_id)
    assert creator_snapshot.key_prefix == "PRJ"
    create_call: asyncio.Task = None  # type: ignore[assignment]
    real_has_tasks = projects_service._project_has_tasks

    async def racing_has_tasks(db, project_id: str) -> bool:
        nonlocal create_call
        result = await real_has_tasks(db, project_id)
        create_call = asyncio.create_task(
            create_task(
                creator_session,
                TaskCreate(phase_id=phase_id, summary="Raced against the prefix PATCH"),
            )
        )
        # shield, not a bare wait_for: a timeout must not CANCEL the create
        # mid-statement — it has to survive and finish once the lock is free.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                asyncio.shield(create_call), timeout=BLOCKED_TIMEOUT_SECONDS
            )
        return result

    monkeypatch.setattr(projects_service, "_project_has_tasks", racing_has_tasks)

    try:
        async with test_sessionmaker() as patch_session:
            await update_project(patch_session, project_id, ProjectUpdate(key_prefix="CRIS"))
        task = await asyncio.wait_for(create_call, timeout=30)
    finally:
        await creator_session.close()

    async with test_sessionmaker() as check_session:
        stored = await _stored_prefix(check_session, project_id)

    assert stored == "CRIS"
    assert task.key == "CRIS-1", (
        f"task {task.key!r} was issued under the pre-PATCH prefix inside a "
        f"project that now advertises {stored!r} — the prefix edit and the "
        "first task create did not serialize on the project row"
    )


# ---------------------------------------------------------------------------
# (A2) A derived prefix always honours KEY_PREFIX_PATTERN
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Crisis Simulator", "CRIS"),  # the happy path stays intact
        ("R&D 2026", "RD20"),
        ("3M Widgets", "PRJ"),  # leading digit — the pre-existing fallback
        ("!!!", "PRJ"),  # no alphanumerics at all
        ("Café Simulator", "PRJ"),  # é is alnum but not [A-Za-z0-9]
        ("ﬃﬃﬃﬃ", "PRJ"),  # U+FB03 uppercases to FFI — 12 chars into VARCHAR(10)
    ],
)
def test_derive_key_prefix_always_matches_the_pattern(name: str, expected: str):
    """
    Every derived prefix matches KEY_PREFIX_PATTERN — the shape ``keys.py``
    interpolates into ``^{prefix}-[0-9]+$`` and whose safety argument rests on
    "a derived prefix must honour the same shape a client-supplied one does".

    Pure, no DB. The last two rows are the finding: ``CAFÉ`` conformed to no
    pattern, and ``FFIFFIFFIFFI`` is four characters of name turned into twelve.
    """
    derived = derive_key_prefix(name)
    assert derived == expected
    assert re.fullmatch(KEY_PREFIX_PATTERN, derived), (
        f"derive_key_prefix({name!r}) produced {derived!r}, which does not match "
        f"KEY_PREFIX_PATTERN {KEY_PREFIX_PATTERN}"
    )


async def test_ligature_name_creates_instead_of_overflowing_the_column(test_sessionmaker):
    """
    ``POST /flan/projects {"name":"ﬃﬃﬃﬃ"}`` creates — it does not 500.

    Unfixed, the derivation hands ``FFIFFIFFIFFI`` (12 chars) to
    ``flan_project.key_prefix VARCHAR(10)`` and Postgres raises 22001
    string_data_right_truncation, which nothing in the create path catches. The
    project must land with the ``PRJ`` fallback and be usable — so a task is
    created against it, proving the stored prefix drives real key generation.
    """
    async with test_sessionmaker() as session:
        project = await create_project(session, ProjectCreate(name="ﬃﬃﬃﬃ"))
        assert project.key_prefix == "PRJ"
        assert await _stored_prefix(session, project.id) == "PRJ"

        phase_id = await _make_phase(session, project.id)
        task = await create_task(
            session, TaskCreate(phase_id=phase_id, summary="Usable project")
        )
        assert task.key == "PRJ-1"
