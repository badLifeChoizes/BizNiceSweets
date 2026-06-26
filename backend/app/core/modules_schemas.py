"""
Pydantic schemas for the modules API — Phase 3 (CORE-07).

ModuleRead   — serialises a Module ORM row into API response JSON.
ModuleUpdate — validates the PATCH /core/modules/{key} request body.

Notes:
- ModuleRead uses from_attributes=True so FastAPI can serialise SQLAlchemy
  Module instances directly (no intermediate dict construction).
- ModuleUpdate has a single optional field; omitting `enabled` in the PATCH
  body is a no-op (the router checks `data.enabled is not None`).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ModuleRead(BaseModel):
    """Module data returned to API callers."""

    key: str
    display_name: str
    enabled: bool
    always_on: bool
    sort_order: int

    model_config = {"from_attributes": True}


class ModuleUpdate(BaseModel):
    """PATCH body for toggling a module's enabled state.

    All fields optional — omit to leave unchanged.
    """

    enabled: Optional[bool] = None
