"""
Idempotent settings table seed — Phase 3 (CORE-06).

Seeds the `settings` table with company identity and locale defaults on every
application startup. The seed uses select-before-insert filtering on both
`key` AND `owner_id IS NULL` (global row) so that a future per-user seed
can insert rows with the same key for different owners without collision.

All operations are idempotent — safe on repeated `podman-compose up`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Default global settings (D-11: company identity + locale defaults).
# Tuple: (key, default_value, value_type, category, description)
_DEFAULT_SETTINGS: list[tuple[str, str | None, str, str, str]] = [
    (
        "company.name",
        "BizNiceSweets",
        "str",
        "company",
        "Company display name shown in the app header",
    ),
    (
        "company.logo_url",
        None,
        "str",
        "company",
        "Optional URL to company logo",
    ),
    (
        "locale.currency",
        "USD",
        "str",
        "locale",
        "Default currency code (ISO 4217)",
    ),
    (
        "locale.date_format",
        "YYYY-MM-DD",
        "str",
        "locale",
        "Default date display format",
    ),
    (
        "locale.timezone",
        "UTC",
        "str",
        "locale",
        "Default timezone (IANA tz database)",
    ),
    (
        "locale.units",
        "metric",
        "str",
        "locale",
        "Default unit system: metric or imperial",
    ),
]


async def seed_default_settings(db: AsyncSession) -> None:
    """
    Idempotent settings seed — insert global row only if key + owner_id=None row
    does not already exist.

    Filters on BOTH key AND owner_id.is_(None) so that per-user override rows
    with the same key (future D-13 extension) do not block the global seed.
    """
    from sqlalchemy import select

    from app.core.settings_model import Setting

    for key, value, value_type, category, description in _DEFAULT_SETTINGS:
        result = await db.execute(
            select(Setting).where(
                Setting.key == key,
                Setting.owner_id.is_(None),
            )
        )
        if result.scalars().first() is None:
            db.add(
                Setting(
                    key=key,
                    value=value,
                    value_type=value_type,
                    category=category,
                    description=description,
                    scope="global",
                    owner_id=None,
                )
            )

    await db.commit()
