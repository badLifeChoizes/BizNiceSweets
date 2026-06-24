"""
Auth FastAPI dependencies.

Provides the reusable security gates every later module's routers use:

  oauth2_scheme — OAuth2PasswordBearer tokenUrl pointing at /api/v1/auth/login

  get_current_user(token, db) — decodes the Bearer JWT, loads the user, checks
    is_active. Raises 401 (WWW-Authenticate: Bearer) on any failure.

  require_permission(permission_code) — factory returning a FastAPI dependency
    that calls get_current_user and then checks the user's roles. An "admin"
    role grants everything (wildcard). Any other role must have an explicit
    permission.code == permission_code, else 403.

Usage:
    # Gate a route on a specific permission
    @router.get("/vendors", dependencies=[Depends(require_permission("syerp:read"))])

    # Use the current user in a route handler
    @router.get("/me")
    async def me(current_user=Depends(get_current_user)):
        ...

Sources:
  RESEARCH.md Pattern 3
  FastAPI security docs https://fastapi.tiangolo.com/tutorial/security/
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.service import decode_access_token, get_user_by_id

# ---------------------------------------------------------------------------
# OAuth2 scheme
# ---------------------------------------------------------------------------

# tokenUrl must be the full path that the browser/client will POST credentials to.
# registry.py mounts all module routers under /api/v1 — the login endpoint will
# therefore be at /api/v1/auth/login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
):
    """
    Decode the Bearer JWT and return the active User.

    Raises HTTP 401 with WWW-Authenticate: Bearer on:
      - invalid / expired token
      - missing 'sub' claim
      - user not found in DB
      - user.is_active == False

    The DB query checks is_active on every request — this is the correct
    tradeoff for a self-hosted single-server deployment (Pitfall 8 in RESEARCH.md).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


# ---------------------------------------------------------------------------
# require_permission
# ---------------------------------------------------------------------------


def require_permission(permission_code: str):
    """
    Dependency factory for permission-based RBAC gating.

    Returns an async dependency that:
      - Calls get_current_user (inheriting its 401 behaviour).
      - Grants access if any role.name == "admin" (wildcard; T-02-11).
      - Grants access if any role.permissions[].code == permission_code.
      - Raises HTTP 403 otherwise.

    Usage:
        @router.get("/protected", dependencies=[Depends(require_permission("syerp:read"))])
        # or as a route parameter:
        @router.get("/protected")
        async def view(user=Depends(require_permission("syerp:read"))):
            ...
    """

    async def _check(current_user=Depends(get_current_user)):
        for role in current_user.roles:
            if role.name == "admin":
                return current_user
            for perm in role.permissions:
                if perm.code == permission_code:
                    return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission_code} required",
        )

    return _check
