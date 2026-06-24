"""
Auth service helpers.

Provides:
  - hash_password / verify_password (Argon2id via pwdlib — T-02-03)
  - create_access_token / decode_access_token (PyJWT HS256 — T-02-02)
  - new_refresh_token — returns (raw, sha256_hex) pair (T-02-04)
  - DUMMY_HASH — constant-time comparison when user not found (timing-attack prevention)
  - get_user_by_email / get_user_by_id — DB lookups with selectin role/permission load
  - authenticate_user — timing-safe credential check
  - collect_permissions — flatten role permissions; admin wildcard
  - store_refresh_token — insert a new refresh token row
  - rotate_refresh_token — rotate with reuse detection (revoke family on replay)

Sources:
  FastAPI official docs https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
  PyJWT docs https://pyjwt.readthedocs.io/en/stable/
  RESEARCH.md Pattern 2 + Code Examples
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import jwt
from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError  # noqa: F401 — re-exported for callers
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

if TYPE_CHECKING:
    from app.modules.auth.models import User

# HS256 with a module-level constant — algorithm list is enforced at decode time
ALGORITHM = "HS256"

# Module-level PasswordHash.recommended() selects Argon2id with OWASP-safe defaults.
# Instantiated once to avoid re-building the hasher on every call.
_password_hash = PasswordHash.recommended()

# Constant-time dummy hash used when the user is not found during login.
# Calling verify_password against this hash prevents timing-based user enumeration.
DUMMY_HASH: str = _password_hash.hash("dummypassword-constant-time-sentinel")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash plain-text password with Argon2id. Never call with an already-hashed value."""
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plain-text password against an Argon2id hash. Timing-safe."""
    return _password_hash.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_access_token(subject: str, permissions: list[str]) -> str:
    """
    Create a signed HS256 access token.

    Payload: { sub, exp, perms }.
    Secret is read via get_secret_value() — never logged or repr'd (T-02-01).
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "exp": expire,
        "perms": permissions,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a HS256 access token.

    Raises jwt.InvalidTokenError (or subclass) if the token is invalid, expired,
    or signed with a different secret.

    CRITICAL: algorithms is always passed as a list to prevent algorithm-confusion
    attacks (T-02-02; CVE-2024-33663 class).
    """
    return jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[ALGORITHM],  # list — never a string
    )


# ---------------------------------------------------------------------------
# Refresh token helpers
# ---------------------------------------------------------------------------


def new_refresh_token() -> tuple[str, str]:
    """
    Generate a new opaque refresh token.

    Returns (raw_token, sha256_hex).
    Store sha256_hex in the database; send raw_token to the client.
    DB compromise exposes only the hash, not the raw token (T-02-04).
    """
    raw = secrets.token_urlsafe(32)  # 32 bytes → 43 URL-safe characters
    sha256_hex = hashlib.sha256(raw.encode()).hexdigest()
    return raw, sha256_hex


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def get_user_by_email(db: AsyncSession, email: str) -> "User | None":
    """
    Load a User by email.  Roles + permissions are loaded via selectin (lazy="selectin"
    on the relationship) so no extra await is needed.
    """
    from app.modules.auth.models import User

    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()


async def get_user_by_id(db: AsyncSession, user_id: str) -> "User | None":
    """Load a User by primary-key UUID string. Roles selectin-loaded automatically."""
    from app.modules.auth.models import User

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> "User | None":
    """
    Timing-safe credential verification.

    If the email does not exist, still calls verify_password against DUMMY_HASH
    so the response time is identical regardless of whether the account exists
    (prevents user-enumeration via timing, T-02-06).

    Returns the User on success; None on failure.
    """
    user = await get_user_by_email(db, email)
    if user is None:
        verify_password(password, DUMMY_HASH)  # constant-time; result discarded
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def collect_permissions(user: "User") -> list[str]:
    """
    Flatten a user's role permissions into a list of code strings.

    If any role has name "admin", a wildcard marker "*" is included so
    that require_permission() can grant access without per-code iteration.
    """
    codes: list[str] = []
    for role in user.roles:
        if role.name == "admin":
            codes.append("*")
        for perm in role.permissions:
            codes.append(perm.code)
    return codes


# ---------------------------------------------------------------------------
# Refresh token persistence + rotation
# ---------------------------------------------------------------------------


async def store_refresh_token(
    db: AsyncSession,
    user_id: str,
    token_hash: str,
    family: str,
    expires_at: datetime,
) -> None:
    """Insert a new RefreshToken row. Commit is included."""
    from app.modules.auth.models import RefreshToken

    rt = RefreshToken(
        token_hash=token_hash,
        user_id=user_id,
        expires_at=expires_at,
        revoked=False,
        family=family,
    )
    db.add(rt)
    await db.commit()


async def rotate_refresh_token(
    db: AsyncSession, raw_token: str
) -> tuple[str, "User"]:
    """
    Rotate a refresh token:
      1. Look up the token row by SHA-256 hash.
      2. If not found → 401 (invalid token).
      3. If expired → 401.
      4. If already revoked → reuse detected: revoke entire family, raise 401.
      5. Otherwise: revoke the old row, insert a new token in the same family,
         return (new_raw_token, user).

    Implements D-07 refresh-token rotation + reuse detection (T-02-09).
    """
    from app.modules.auth.models import RefreshToken

    sha = hashlib.sha256(raw_token.encode()).hexdigest()

    stmt = select(RefreshToken).where(RefreshToken.token_hash == sha)
    result = await db.execute(stmt)
    token_row: RefreshToken | None = result.scalars().first()

    if token_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    now = datetime.now(timezone.utc)
    expires = token_row.expires_at
    # Ensure both datetimes are timezone-aware for comparison
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if expires < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    if token_row.revoked:
        # Reuse detected — revoke the entire family (T-02-09)
        family_stmt = select(RefreshToken).where(
            RefreshToken.family == token_row.family
        )
        family_result = await db.execute(family_stmt)
        for row in family_result.scalars().all():
            row.revoked = True
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected — all sessions revoked",
        )

    # Valid — revoke the old token
    token_row.revoked = True

    # Load the user (selectin handles roles, but we need the User row itself)
    user = await get_user_by_id(db, token_row.user_id)
    if user is None or not user.is_active:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Issue a new token in the same family
    new_raw, new_hash = new_refresh_token()
    new_expires = now + timedelta(days=settings.refresh_token_expire_days)
    new_rt = RefreshToken(
        token_hash=new_hash,
        user_id=user.id,
        expires_at=new_expires,
        revoked=False,
        family=token_row.family,
    )
    db.add(new_rt)
    await db.commit()

    return new_raw, user
