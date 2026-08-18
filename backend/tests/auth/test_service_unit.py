"""
Service and dependency unit tests — plan 02-02 (TDD RED phase).

Covers behaviors introduced in Task 1:
  - authenticate_user timing-safe path (DUMMY_HASH on user-not-found)
  - collect_permissions flattening + admin wildcard
  - get_current_user raises 401 on bad token / missing sub / inactive user
  - require_permission grants when code matches or role is "admin"; else 403

These run without a live database using mock/stub objects.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — lightweight stand-ins for ORM User/Role/Permission
# ---------------------------------------------------------------------------


def _make_permission(code: str) -> MagicMock:
    p = MagicMock()
    p.code = code
    return p


def _make_role(name: str, perm_codes: list[str]) -> MagicMock:
    r = MagicMock()
    r.name = name
    r.permissions = [_make_permission(c) for c in perm_codes]
    return r


def _make_user(
    user_id: str = "user-1",
    is_active: bool = True,
    role_names: list[tuple[str, list[str]]] | None = None,
) -> MagicMock:
    """Create a mock User with roles and permissions."""
    u = MagicMock()
    u.id = user_id
    u.is_active = is_active
    u.roles = [_make_role(name, perms) for name, perms in (role_names or [])]
    return u


# ---------------------------------------------------------------------------
# authenticate_user — timing-safe path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authenticate_user_bad_password_returns_none() -> None:
    """Wrong password for a known user returns None (not an exception)."""
    from app.modules.auth.service import authenticate_user, hash_password

    user = _make_user()
    user.hashed_password = hash_password("correctpassword")

    db = AsyncMock()

    with patch(
        "app.modules.auth.service.get_user_by_email", new=AsyncMock(return_value=user)
    ):
        result = await authenticate_user(db, "user@example.com", "wrongpassword")

    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_unknown_email_returns_none() -> None:
    """Unknown email — verify_password called with DUMMY_HASH for timing safety."""
    from app.modules.auth.service import DUMMY_HASH, authenticate_user, verify_password

    db = AsyncMock()
    calls: list[tuple] = []
    original_verify = verify_password

    def tracking_verify(plain: str, hashed: str) -> bool:
        calls.append((plain, hashed))
        return original_verify(plain, hashed)

    with (
        patch(
            "app.modules.auth.service.get_user_by_email", new=AsyncMock(return_value=None)
        ),
        patch("app.modules.auth.service.verify_password", side_effect=tracking_verify),
    ):
        result = await authenticate_user(db, "nobody@nowhere.test", "anypassword")

    assert result is None
    # DUMMY_HASH must be the hashed value used in the constant-time comparison
    assert len(calls) == 1
    _, hashed_arg = calls[0]
    assert hashed_arg == DUMMY_HASH


@pytest.mark.asyncio
async def test_authenticate_user_correct_returns_user() -> None:
    """Correct credentials return the user object."""
    from app.modules.auth.service import authenticate_user, hash_password

    user = _make_user()
    user.hashed_password = hash_password("goodpassword")

    db = AsyncMock()

    with patch(
        "app.modules.auth.service.get_user_by_email", new=AsyncMock(return_value=user)
    ):
        result = await authenticate_user(db, "user@example.com", "goodpassword")

    assert result is user


# ---------------------------------------------------------------------------
# collect_permissions
# ---------------------------------------------------------------------------


def test_collect_permissions_flattens_role_codes() -> None:
    """collect_permissions returns a flat list of permission codes from all roles."""
    from app.modules.auth.service import collect_permissions

    user = _make_user(
        role_names=[
            ("editor", ["plum:read", "plum:write"]),
            ("viewer", ["syerp:read"]),
        ]
    )
    perms = collect_permissions(user)
    assert "plum:read" in perms
    assert "plum:write" in perms
    assert "syerp:read" in perms


def test_collect_permissions_admin_wildcard() -> None:
    """Admin role produces a wildcard '*' marker in permissions."""
    from app.modules.auth.service import collect_permissions

    user = _make_user(role_names=[("admin", ["syerp:read"])])
    perms = collect_permissions(user)
    assert "*" in perms


def test_collect_permissions_no_roles() -> None:
    """User with no roles returns an empty list."""
    from app.modules.auth.service import collect_permissions

    user = _make_user(role_names=[])
    perms = collect_permissions(user)
    assert perms == []


# ---------------------------------------------------------------------------
# get_current_user — 401 paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_raises_401_on_bad_token() -> None:
    """Invalid token raises HTTPException 401 with WWW-Authenticate header."""
    from fastapi import HTTPException

    from app.modules.auth.dependencies import get_current_user

    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="not.a.valid.token", db=db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers.get("WWW-Authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_get_current_user_raises_401_on_missing_sub() -> None:
    """Token with no 'sub' claim raises HTTPException 401."""
    import jwt as pyjwt
    from fastapi import HTTPException

    from app.core.config import settings
    from app.modules.auth.dependencies import get_current_user
    from app.modules.auth.service import ALGORITHM

    # Mint a token without a 'sub' field
    token = pyjwt.encode(
        {"perms": ["syerp:read"]},
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_raises_401_when_user_not_found() -> None:
    """Token valid but user_id not in DB returns 401."""
    from fastapi import HTTPException

    from app.modules.auth.dependencies import get_current_user
    from app.modules.auth.service import create_access_token

    token = create_access_token(subject="ghost-id", permissions=[])
    db = AsyncMock()

    with patch(
        "app.modules.auth.dependencies.get_user_by_id",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_raises_401_for_inactive_user() -> None:
    """Token valid but user.is_active=False returns 401."""
    from fastapi import HTTPException

    from app.modules.auth.dependencies import get_current_user
    from app.modules.auth.service import create_access_token

    inactive_user = _make_user(is_active=False)
    token = create_access_token(subject="inactive-id", permissions=[])
    db = AsyncMock()

    with patch(
        "app.modules.auth.dependencies.get_user_by_id",
        new=AsyncMock(return_value=inactive_user),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_returns_user_for_valid_token() -> None:
    """Valid token + active user returns the user object."""
    from app.modules.auth.dependencies import get_current_user
    from app.modules.auth.service import create_access_token

    active_user = _make_user(is_active=True)
    token = create_access_token(subject="active-id", permissions=["syerp:read"])
    db = AsyncMock()

    with patch(
        "app.modules.auth.dependencies.get_user_by_id",
        new=AsyncMock(return_value=active_user),
    ):
        result = await get_current_user(token=token, db=db)

    assert result is active_user


# ---------------------------------------------------------------------------
# require_permission — 403 / grant paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_permission_grants_when_code_matches() -> None:
    """User with matching permission code is granted (returns user)."""
    from app.modules.auth.dependencies import require_permission

    user = _make_user(role_names=[("editor", ["syerp:read", "plum:write"])])
    dep = require_permission("syerp:read")

    result = await dep(current_user=user)
    assert result is user


@pytest.mark.asyncio
async def test_require_permission_grants_for_admin_role() -> None:
    """User with 'admin' role name is granted even without explicit permission code."""
    from app.modules.auth.dependencies import require_permission

    user = _make_user(role_names=[("admin", [])])
    dep = require_permission("any:permission")

    result = await dep(current_user=user)
    assert result is user


@pytest.mark.asyncio
async def test_require_permission_raises_403_when_missing() -> None:
    """User lacking the required permission raises HTTPException 403."""
    from fastapi import HTTPException

    from app.modules.auth.dependencies import require_permission

    user = _make_user(role_names=[("viewer", ["syerp:read"])])
    dep = require_permission("plum:write")

    with pytest.raises(HTTPException) as exc_info:
        await dep(current_user=user)

    assert exc_info.value.status_code == 403
    assert "plum:write" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_permission_raises_403_for_no_roles() -> None:
    """User with no roles at all raises HTTPException 403."""
    from fastapi import HTTPException

    from app.modules.auth.dependencies import require_permission

    user = _make_user(role_names=[])
    dep = require_permission("syerp:read")

    with pytest.raises(HTTPException) as exc_info:
        await dep(current_user=user)

    assert exc_info.value.status_code == 403
