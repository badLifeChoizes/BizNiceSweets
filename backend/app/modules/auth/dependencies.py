"""
Auth FastAPI dependencies.

Provides the reusable security gates every later module's routers use:

  oauth2_scheme — OAuth2PasswordBearer tokenUrl pointing at /api/v1/auth/login

  get_current_user(token, db) — decodes the Bearer JWT, loads the user, checks
    is_active. Raises 401 (WWW-Authenticate: Bearer) on any failure.

  has_permission(user, permission_code) — the grant RULE itself, as a plain
    non-raising predicate. An "admin" role grants everything (wildcard); any
    other role must have an explicit permission.code == permission_code.

  require_permission(permission_code) — factory returning a FastAPI dependency
    that calls get_current_user and then applies has_permission, raising 403
    when it answers False.

require_permission is the gate; has_permission is for the case a gate cannot
express — a route that is open to everyone but whose RESPONSE or PAYLOAD carries
a field only some callers may see (FLAN's `flan:rates`, flan/router.py). Both
read the same predicate on purpose: two copies of "does this user hold X" drift,
and the copy that drifts is the one that stops refusing.

Usage:
    # Gate a route on a specific permission
    @router.get("/vendors", dependencies=[Depends(require_permission("syerp:read"))])

    # Use the current user in a route handler
    @router.get("/me")
    async def me(current_user=Depends(get_current_user)):
        ...

    # Branch on a permission without refusing the request
    if not has_permission(current_user, "flan:rates"):
        payload.pop("hourly_rate")

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
# has_permission — the grant rule, as a predicate
# ---------------------------------------------------------------------------


def has_permission(user, permission_code: str) -> bool:
    """
    Answer whether `user` holds `permission_code`, without raising.

    The rule, in one place:
      - Any role named "admin" grants everything (wildcard; T-02-11).
      - Otherwise some role.permissions[].code must equal permission_code.

    This is the SAME rule require_permission enforces — that factory calls this
    function rather than repeating the loop, so a change to how a grant is
    decided cannot apply to the gate and not to the field-level checks (or the
    reverse). Roles and their permissions are selectin-loaded by get_user_by_id,
    so no IO happens here.

    Use it where a 403 would be the wrong answer: the caller may have the route,
    but not every field on it (FLAN's `flan:rates` gates `hourly_rate` inside
    responses that flan:read otherwise opens).
    """
    for role in user.roles:
        if role.name == "admin":
            return True
        for perm in role.permissions:
            if perm.code == permission_code:
                return True
    return False


# ---------------------------------------------------------------------------
# require_permission
# ---------------------------------------------------------------------------


def require_permission(permission_code: str):
    """
    Dependency factory for permission-based RBAC gating.

    Returns an async dependency that:
      - Calls get_current_user (inheriting its 401 behaviour).
      - Returns the user when has_permission(user, permission_code) is True
        (admin role is the wildcard; any other role needs the explicit code).
      - Raises HTTP 403 otherwise.

    Usage:
        @router.get("/protected", dependencies=[Depends(require_permission("syerp:read"))])
        # or as a route parameter:
        @router.get("/protected")
        async def view(user=Depends(require_permission("syerp:read"))):
            ...
    """

    async def _check(current_user=Depends(get_current_user)):
        if has_permission(current_user, permission_code):
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission_code} required",
        )

    return _check
