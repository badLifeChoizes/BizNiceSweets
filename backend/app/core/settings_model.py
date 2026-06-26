"""
Setting ORM model — Phase 3 (App Shell & Settings, CORE-06).

Key-value settings store with surrogate PK for D-13 per-user groundwork.

Design notes:
- Surrogate int PK avoids a breaking PK migration when per-user settings arrive
  (the future extension adds rows with owner_id != None, not a PK change).
- Partial unique index `uq_settings_global` enforces uniqueness for global rows
  (owner_id IS NULL). Standard UNIQUE(key, owner_id) would NOT work because
  PostgreSQL treats NULL != NULL in unique constraint evaluation — two rows with
  key='company.name' and owner_id=NULL would both pass (RESEARCH Pitfall 5).
- `scope` and `owner_id` are groundwork only in v1; all v1 rows have scope='global'
  and owner_id=None. Per-user behavior is not shipped in Phase 3 (D-13).
- No ORM relationships in v1 — no lazy="selectin" needed.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Dotted key convention: "company.name", "locale.currency", etc.
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Type hint for deserialization: "str", "bool", "int", "json"
    value_type: Mapped[str] = mapped_column(String(20), default="str", nullable=False)
    # Logical grouping for the admin UI: "company", "locale", "feature"
    category: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    # D-13 groundwork: scope = "global" now; add "user" scope later without rewrite
    scope: Mapped[str] = mapped_column(String(20), default="global", nullable=False)
    # D-13 groundwork: owner_id = None for global; user.id for per-user override later
    # Mirrors AuditLog.actor_id nullable-string pattern
    owner_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # Partial unique index: unique (key) WHERE owner_id IS NULL.
        # Ensures only one global row per key while allowing future per-user rows
        # with the same key (owner_id IS NOT NULL). Standard UNIQUE(key, owner_id)
        # fails here because PostgreSQL treats NULL != NULL (RESEARCH Pitfall 5).
        Index(
            "uq_settings_global",
            "key",
            unique=True,
            postgresql_where=(owner_id == None),  # noqa: E711
        ),
    )
