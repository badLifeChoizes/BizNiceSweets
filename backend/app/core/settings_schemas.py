"""
Pydantic schemas for the settings API — Phase 3 (CORE-06).

SettingRead   — serialises a Setting ORM row into API response JSON.
SettingUpdate — validates the PATCH /core/settings/{key} request body.

Notes:
- SettingRead uses from_attributes=True so FastAPI can serialise SQLAlchemy
  Setting instances directly.
- SettingUpdate has a single optional field; the PATCH handler uses
  model_dump(exclude_unset=True) so omitted fields are never overwritten
  with None (RESEARCH Pitfall 8).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SettingRead(BaseModel):
    """Setting data returned to API callers."""

    key: str
    value: Optional[str] = None
    value_type: str
    category: str
    scope: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    """PATCH body for updating a global setting's value.

    All fields optional — omit to leave unchanged (exclude_unset semantics).
    Set value to None explicitly to clear a setting's value.
    """

    value: Optional[str] = None
