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
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import TokenResponse, UserRead
from app.modules.auth.service import (
    authenticate_user,
    collect_permissions,
    create_access_token,
    new_refresh_token,
    rotate_refresh_token,
    store_refresh_token,
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
