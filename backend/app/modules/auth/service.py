"""
Auth service helpers.

Provides:
  - hash_password / verify_password (Argon2id via pwdlib — T-02-03)
  - create_access_token / decode_access_token (PyJWT HS256 — T-02-02)
  - new_refresh_token — returns (raw, sha256_hex) pair (T-02-04)
  - DUMMY_HASH — constant-time comparison when user not found (timing-attack prevention)

Sources:
  FastAPI official docs https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
  PyJWT docs https://pyjwt.readthedocs.io/en/stable/
  RESEARCH.md Pattern 2
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError  # noqa: F401 — re-exported for callers
from pwdlib import PasswordHash

from app.core.config import settings

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
