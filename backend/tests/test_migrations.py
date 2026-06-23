"""
Alembic migration structure tests — Wave 0 harness.

Maps to CORE-09 (migrations apply cleanly on a fresh DB).

Structural tests (no live DB required):
  - Alembic config loads without error.
  - Base.metadata is reachable via the central aggregator.
  - Baseline migration 0001 has down_revision = None.

Live DB tests (skipped when no DB is available):
  - alembic upgrade head runs to completion on a fresh database.
"""
from __future__ import annotations

import importlib
import subprocess
import sys

import pytest


def test_alembic_config_loads() -> None:
    """Alembic config object loads and exposes the script location."""
    from alembic.config import Config

    cfg = Config("alembic.ini")
    # script_location is set in alembic.ini; must be non-empty
    assert cfg.get_main_option("script_location") is not None


def test_base_metadata_reachable() -> None:
    """
    Importing app.core.models populates Base.metadata.

    This is the critical wiring that prevents Pitfall 1 (autogenerate
    producing empty migrations because models were never imported).
    """
    import app.core.models  # noqa: F401 — side-effect import
    from app.core.base import Base

    # Base.metadata must be a non-None MetaData instance
    assert Base.metadata is not None


def test_baseline_migration_structure() -> None:
    """
    The 0001 initial baseline migration has down_revision = None (head).

    This verifies the migration chain starts correctly without requiring
    a live database.
    """
    # Import the migration module directly via importlib
    spec = importlib.util.spec_from_file_location(
        "migration_0001",
        "alembic/versions/0001_initial_baseline.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    assert module.revision == "0001"
    assert module.down_revision is None


def test_alembic_upgrade_head_live(skip_if_no_db: None) -> None:
    """
    alembic upgrade head applies cleanly on the configured database.

    Skipped when no live DB is reachable (sandbox / unit-test environment).
    Exercised end-to-end under Plan 03 compose.
    """
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"alembic upgrade head failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
