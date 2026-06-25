"""
Auth module router.

Endpoints:
  POST /auth/login    — OAuth2 password flow; issues JWT + httpOnly refresh cookie
  POST /auth/refresh  — rotates refresh token; issues new access token
  POST /auth/logout   — revokes current user's refresh tokens; clears cookie
  GET  /auth/me       — current user info

Endpoints added in plan 02-03:
  POST   /auth/users       — admin: create user
  GET    /auth/users       — admin: list users
  GET    /auth/users/{id}  — admin: get user
  PATCH  /auth/users/{id}  — admin: update/deactivate user
  GET    /auth/roles       — admin: list roles

mount_all() in registry.py adds /api/v1 prefix — do NOT include it here.
Full paths are therefore /api/v1/auth/login, /api/v1/auth/refresh, etc.

Sources:
  RESEARCH.md Pattern 4 (httpOnly cookie), Verified Pattern: FastAPI Set Cookie
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.auth.schemas import TokenResponse, UserCreate, UserRead, UserUpdate
from app.modules.auth.service import (
    authenticate_user,
    collect_permissions,
    create_access_token,
    create_user,
    list_users,
    new_refresh_token,
    rotate_refresh_token,
    store_refresh_token,
    update_user,
    write_audit,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    """
    Set the httpOnly refresh-token cookie with the correct security attributes.

    - httponly=True: JS cannot read it (XSS protection, T-02-07).
    - secure=not settings.debug: HTTPS-only in production; HTTP allowed in dev.
    - samesite="lax": adequate CSRF protection for a same-origin SPA (T-02-08).
    - path="/api/v1/auth/refresh": scope cookie to the refresh endpoint only
      so it is not sent with every API call (reduces exposure surface).
    """
    response.set_cookie(
        key="refresh_token",
        value=raw_token,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/v1/auth/refresh",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear the refresh-token cookie on logout."""
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth/refresh",
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    OAuth2 password flow — POST with form fields `username` (email) and `password`.

    On success:
      - Returns { access_token, token_type: "bearer" } in the response body.
      - Sets an httpOnly refresh-token cookie scoped to /api/v1/auth/refresh.

    On failure:
      - 401 "Incorrect email or password" (no distinguishing between bad email/bad pass).
    """
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        # D-14: write audit log for failed login (actor_id=None — no user resolved)
        await write_audit(
            db,
            actor_id=None,
            action="auth.login_failed",
            target_type="session",
            target_id=None,
            detail=f"Failed login attempt for email: {form_data.username}",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(str(user.id), collect_permissions(user))
    raw_refresh, hashed_refresh = new_refresh_token()
    family = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )

    await store_refresh_token(
        db,
        user_id=str(user.id),
        token_hash=hashed_refresh,
        family=family,
        expires_at=expires_at,
    )
    _set_refresh_cookie(response, raw_refresh)

    # D-14: write audit log for successful login
    await write_audit(
        db,
        actor_id=str(user.id),
        action="auth.login_success",
        target_type="session",
        target_id=str(user.id),
        detail=f"Successful login for email: {user.email}",
    )

    return TokenResponse(access_token=access_token, token_type="bearer")


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Rotate the refresh token.

    Reads the refresh_token cookie (sent automatically by the browser when the
    path matches). Returns a new access token and sets a new refresh cookie.
    On reuse detection the entire token family is revoked → 401.
    """
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_raw, user = await rotate_refresh_token(db, raw_token)
    access_token = create_access_token(str(user.id), collect_permissions(user))

    _set_refresh_cookie(response, new_raw)
    return TokenResponse(access_token=access_token, token_type="bearer")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Revoke the current refresh token (if present) and clear the cookie.

    Requires a valid access token in the Authorization header so that logout
    is authenticated — prevents unauthenticated cookie-clearing.

    Also revokes the specific refresh token that is presented in the cookie,
    ensuring the device's session is terminated even if the access token
    would still be valid for its remaining TTL.
    """
    from app.modules.auth.models import RefreshToken
    import hashlib

    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        sha = hashlib.sha256(raw_token.encode()).hexdigest()
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == sha,
            RefreshToken.user_id == str(current_user.id),
        )
        result = await db.execute(stmt)
        token_row = result.scalars().first()
        if token_row:
            token_row.revoked = True
            await db.commit()

    _clear_refresh_cookie(response)
    return {"detail": "Logged out"}


# ---------------------------------------------------------------------------
# Me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserRead)
async def me(current_user=Depends(get_current_user)) -> UserRead:
    """Return the authenticated user's profile and roles."""
    return current_user


# ---------------------------------------------------------------------------
# Admin: User CRUD (gated by users:manage permission — D-10, T-02-14)
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserRead])
async def list_users_endpoint(
    acting_admin=Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
) -> list[UserRead]:
    """
    List all user accounts.

    Gated by require_permission("users:manage") — only admins can list users.
    Returns a list of UserRead objects (roles included via selectin load).
    """
    users = await list_users(db)
    return users


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
    data: UserCreate,
    acting_admin=Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """
    Admin-provisioned account creation (D-01: no public signup).

    Creates a new user, hashes the password, optionally attaches a named role.
    Writes an AuditLog row action='user.created' (D-14, T-02-16).
    Gated by require_permission("users:manage") → 403 for non-admins (T-02-14).
    """
    user = await create_user(
        db,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        role_name=data.role,
    )
    await write_audit(
        db,
        actor_id=str(acting_admin.id),
        action="user.created",
        target_type="user",
        target_id=str(user.id),
        detail=f"Admin created user: {user.email}",
    )
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user_endpoint(
    user_id: str,
    data: UserUpdate,
    acting_admin=Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """
    Update a user account (PATCH semantics — all fields optional).

    Supports: change full_name, assign/replace role, set is_active.
    When is_active is set to False:
      - Revokes all live RefreshToken rows for the user (D-05, T-02-15).
      - Writes AuditLog action='user.deactivated'.
    Otherwise writes AuditLog action='user.updated'.
    Gated by require_permission("users:manage") → 403 (T-02-14).
    """
    was_active_before = True
    # Check current state to determine audit action
    from app.modules.auth.models import User as UserModel
    from sqlalchemy import select as sa_select
    pre_result = await db.execute(sa_select(UserModel).where(UserModel.id == user_id))
    pre_user = pre_result.scalars().first()
    if pre_user:
        was_active_before = pre_user.is_active

    user = await update_user(
        db,
        user_id=user_id,
        full_name=data.full_name,
        is_active=data.is_active,
        role_name=data.role,
    )

    # Choose the right audit action
    if data.is_active is False and was_active_before:
        audit_action = "user.deactivated"
    else:
        audit_action = "user.updated"

    await write_audit(
        db,
        actor_id=str(acting_admin.id),
        action=audit_action,
        target_type="user",
        target_id=str(user.id),
        detail=f"Admin updated user: {user.email}",
    )
    return user


# ---------------------------------------------------------------------------
# RBAC probe endpoint — test/diagnostic only (D-10 / CORE-05 verification)
# ---------------------------------------------------------------------------


@router.get("/_rbac_probe")
async def rbac_probe(
    current_user=Depends(require_permission("syerp:read")),
) -> dict:
    """
    Diagnostic probe endpoint gated by require_permission("syerp:read").

    Used by test_rbac.py to verify the require_permission dependency correctly
    returns 200 for users with syerp:read and 403 for those without.

    No SYERP module exists yet (Phase 4) — this provides a real gated endpoint
    for RBAC testing without depending on Phase 4 routes.  Marked clearly as a
    diagnostic probe; may be removed once SYERP endpoints exist.

    Production guard (CR-02): this diagnostic route is only reachable when
    settings.debug is true (dev/test). In production it returns 404 so it is
    not part of the live attack surface.
    """
    if not settings.debug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"probe": "ok", "permission": "syerp:read"}
