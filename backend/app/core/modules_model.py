"""
Module ORM model — Phase 3 (App Shell & Settings, CORE-07).

Represents the DB-backed runtime enable/disable state of each suite.
Distinct from Compose profiles (deploy-time presence) vs DB flag (runtime on/off).

Design notes:
- Natural string PK (`key`) matching MODULE_NAME in each module's __init__.py.
- `always_on=True` on SYERP (and any future platform-bundled module); the PATCH
  endpoint rejects enabled=False for always-on modules (D-08).
- No ORM relationships in v1 — no lazy="selectin" needed.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class Module(Base):
    __tablename__ = "modules"

    # Natural key matching MODULE_NAME in each module's __init__.py
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # False = currently disabled (admin toggled off); always_on=True cannot go False
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # True = platform-bundled; PATCH to enabled=False is rejected (D-08 SYERP guard)
    always_on: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Sidebar display order; lower = higher in list
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
