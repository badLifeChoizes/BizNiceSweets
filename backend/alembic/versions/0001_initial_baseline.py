"""Initial baseline

Revision ID: 0001
Revises:
Create Date: 2026-06-23 00:00:00.000000+00:00

Phase 1 baseline: migration framework wired up with an empty baseline.
Substantive tables arrive with their owning modules in later phases
(Phase 4 — SYERP Core Hub, Phase 5 — PLUM Parts & Revisions, etc.).

Per Claude's Discretion (01-CONTEXT.md): a minimal/empty baseline is
acceptable for Phase 1.
"""
from collections.abc import Sequence
from typing import Union

# revision identifiers, used by Alembic
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 1: empty baseline — tables created in Phase 4+ by module migrations
    pass


def downgrade() -> None:
    pass
