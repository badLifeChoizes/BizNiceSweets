# ABOUTME: Standing guard for the pytest harness's own central invariant — the DB-availability probe.
# ABOUTME: Fails LOUD (not skips) if the SC1 DSN fix regresses, so DB-backed tests can never silently skip again.
"""
Harness self-check (NFR-5, Phase 2a fix loop).

The whole point of Phase 2a was that ~100 DB-backed tests were *silently
skipping* while CI stayed green (the four D-P7-4 root causes). Nothing else in
the suite re-catches a regression of that: `pytest` exits 0 identically whether
the DB-backed tests run or skip. If the SC1 DSN probe (`_check_db_available`)
broke again, `db_available()` would flip to False and the graceful-skip path
would quietly disappear the DB tests — CI green, coverage gone.

This module pins the invariant directly: the probe MUST report a reachable
database, and it MUST do so via the repaired libpq-keyword-argument path (not
the old SQLAlchemy `+psycopg2` URL that raised `invalid dsn`). A break here is a
hard failure, not a skip — exactly the loud signal the phase exists to provide.
"""
from __future__ import annotations

from tests.conftest import _check_db_available, db_available


def test_db_probe_connects() -> None:
    """The DB-availability probe connects — regressing the DSN fix fails loud here."""
    assert _check_db_available() is True, (
        "The pytest DB-availability probe could not connect. If this regresses, "
        "DB-backed tests silently skip while CI stays green (the D-P7-4 defect "
        "Phase 2a repaired). Check tests.conftest._check_db_available uses libpq "
        "keyword args, and that a live Postgres is reachable."
    )


def test_db_available_flag_true() -> None:
    """The session-cached availability flag is True, so no test takes the skip path."""
    assert db_available() is True
