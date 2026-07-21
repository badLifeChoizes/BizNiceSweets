"""
Auth module Pydantic schemas.

Separation:
  - Input schemas (Create/Update): no from_attributes — they validate incoming JSON.
  - Response schemas (Read): from_attributes=True — serialise from ORM instances.

Schemas:
  TokenResponse   — access token response for login/refresh
  UserCreate      — admin creates a new user account
  UserRead        — user data returned to callers
  UserUpdate      — admin updates a user (all fields optional)
  RoleRead        — role data with permission codes
"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr

# ---------------------------------------------------------------------------
# Token schemas
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    """Returned by /auth/login and /auth/refresh."""

    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Admin-provisioned account creation (D-01: no public signup)."""

    email: EmailStr
    password: str
    full_name: str | None = None
    role: str | None = None  # role name to assign; defaults to "user" if omitted


class UserRead(BaseModel):
    """User data returned to API callers."""

    id: str
    email: str
    full_name: str | None = None
    is_active: bool
    roles: list[RoleRead] = []
    # Flat permission-code list for frontend nav filtering (D-04, CORE-08).
    # Populated by collect_permissions(user) in the /me endpoint.
    # Admin users include "*" (wildcard) plus all explicit codes.
    permissions: list[str] = []

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Admin-only update (all fields optional — PATCH semantics)."""

    full_name: str | None = None
    is_active: bool | None = None
    role: str | None = None  # replace the user's roles with this single role


# ---------------------------------------------------------------------------
# Role / Permission schemas
# ---------------------------------------------------------------------------


class RoleRead(BaseModel):
    """Role data with flattened permission codes."""

    id: int
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}
