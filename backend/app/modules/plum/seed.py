"""
PLUM module seed.

Seeds:
  1. Classification tag starter vocabulary (D-12):
     Purchased(1), Manufactured(2), Assembly(3), Finished Good(4), Tool(5), Raw Material(6)
  2. Default settings (D-04, D-12):
     plum.revision_scheme = "asme"
     plum.tag_vocabulary_editable = "true"

All operations are idempotent — safe on every podman-compose up (T-05-02).
Uses select-before-insert to prevent duplicate rows across repeated startups.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Starter tag vocabulary (D-12)
# (name, sort_order) — name is the idempotency key
# ---------------------------------------------------------------------------

_CLASSIFICATION_TAGS = [
    ("Purchased", 1),
    ("Manufactured", 2),
    ("Assembly", 3),
    ("Finished Good", 4),
    ("Tool", 5),
    ("Raw Material", 6),
]

# ---------------------------------------------------------------------------
# Default PLUM settings (D-04, D-12)
# plum.revision_scheme: "asme" | "semver" (default asme per ASME Y14.35)
# plum.tag_vocabulary_editable: "true" | "false"
# ---------------------------------------------------------------------------

_PLUM_SETTINGS = [
    ("plum.revision_scheme", "asme"),
    ("plum.tag_vocabulary_editable", "true"),
]


async def seed_plum_data(db: AsyncSession) -> None:
    """
    Seed PLUM classification tags and default settings.

    Idempotent: checks for existing rows before inserting (select-before-insert
    pattern — mirrors auth/seed.py and syerp/coa_seed.py).

    Called from app.core.seed.run_seeds() after seed_gl_accounts.
    """
    from sqlalchemy import select

    from app.core.settings_model import Setting
    from app.modules.plum.models import PlumClassificationTag

    # 1. Seed classification tag starter vocabulary (D-12)
    for name, sort_order in _CLASSIFICATION_TAGS:
        result = await db.execute(
            select(PlumClassificationTag).where(PlumClassificationTag.name == name)
        )
        if result.scalars().first() is None:
            db.add(PlumClassificationTag(name=name, sort_order=sort_order, active=True))

    # 2. Seed default PLUM settings (D-04, D-12)
    for key, value in _PLUM_SETTINGS:
        result = await db.execute(select(Setting).where(Setting.key == key))
        if result.scalars().first() is None:
            db.add(Setting(key=key, value=value, value_type="str"))

    await db.commit()
