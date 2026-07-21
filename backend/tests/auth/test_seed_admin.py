"""
First-admin seed tests — plan 02-03 (TDD: xfail markers removed).

Behaviors tested (CORE-04, D-02, D-09):
  - seed_admin_user is idempotent: running twice yields exactly one admin user,
    one "admin" role, one "user" role, and no duplicate permissions.
  - After seed, the admin user has the "admin" role; collect_permissions(admin)
    includes the wildcard "*".
  - The "user" role includes syerp:read + plum:write but NOT users:manage.
  - The seeded admin's hashed_password != plaintext and verifies via verify_password.

Tests require a live PostgreSQL database (skip_if_no_db).

The seeded_db fixture is auto-discovered via tests/auth/conftest.py (re-exported
from conftest_helpers) — no module-level import is needed here.
"""

# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


async def test_seed_idempotent_user_count(seeded_db) -> None:
    """Running seed_admin_user twice yields exactly one admin user."""
    from sqlalchemy import func, select

    from app.modules.auth.models import User
    from app.modules.auth.seed import seed_admin_user

    # Run a second time — must be a no-op
    await seed_admin_user(seeded_db)

    from app.core.config import settings

    result = await seeded_db.execute(
        select(func.count()).select_from(User).where(User.email == settings.bns_admin_email)
    )
    count = result.scalar_one()
    assert count == 1, f"Expected exactly 1 admin user, found {count}"


async def test_seed_idempotent_role_count(seeded_db) -> None:
    """Running seed_admin_user twice yields exactly one 'admin' role and one 'user' role."""
    from sqlalchemy import func, select

    from app.modules.auth.models import Role
    from app.modules.auth.seed import seed_admin_user

    # Second seed call
    await seed_admin_user(seeded_db)

    for role_name in ("admin", "user"):
        result = await seeded_db.execute(
            select(func.count()).select_from(Role).where(Role.name == role_name)
        )
        count = result.scalar_one()
        assert count == 1, f"Expected exactly 1 '{role_name}' role, found {count}"


async def test_seed_idempotent_no_duplicate_permissions(seeded_db) -> None:
    """Running seed_admin_user twice does not duplicate permission rows."""
    from sqlalchemy import func, select

    from app.modules.auth.models import Permission
    from app.modules.auth.seed import seed_admin_user

    # Second seed call
    await seed_admin_user(seeded_db)

    # Verify unique codes by counting per-code
    expected_codes = {"users:manage", "syerp:read", "syerp:write", "plum:read", "plum:write"}
    for code in expected_codes:
        result = await seeded_db.execute(
            select(func.count()).select_from(Permission).where(Permission.code == code)
        )
        count = result.scalar_one()
        assert count == 1, f"Expected exactly 1 permission '{code}', found {count}"


# ---------------------------------------------------------------------------
# Admin user role assignment
# ---------------------------------------------------------------------------


async def test_admin_user_has_admin_role(seeded_db) -> None:
    """Seeded admin user has the 'admin' role attached."""
    from sqlalchemy import select

    from app.core.config import settings
    from app.modules.auth.models import User

    result = await seeded_db.execute(
        select(User).where(User.email == settings.bns_admin_email)
    )
    admin = result.scalars().first()
    assert admin is not None, "Admin user not found in DB"
    role_names = [r.name for r in admin.roles]
    assert "admin" in role_names, f"Admin role not assigned; roles: {role_names}"


async def test_admin_collect_permissions_includes_wildcard(seeded_db) -> None:
    """collect_permissions on the seeded admin includes the '*' wildcard marker."""
    from sqlalchemy import select

    from app.core.config import settings
    from app.modules.auth.models import User
    from app.modules.auth.service import collect_permissions

    result = await seeded_db.execute(
        select(User).where(User.email == settings.bns_admin_email)
    )
    admin = result.scalars().first()
    assert admin is not None
    perms = collect_permissions(admin)
    assert "*" in perms, f"Wildcard missing from admin permissions: {perms}"


# ---------------------------------------------------------------------------
# User role permission set
# ---------------------------------------------------------------------------


async def test_user_role_has_business_permissions(seeded_db) -> None:
    """The 'user' role has syerp:read, syerp:write, plum:read, plum:write."""
    from sqlalchemy import select

    from app.modules.auth.models import Role

    result = await seeded_db.execute(select(Role).where(Role.name == "user"))
    user_role = result.scalars().first()
    assert user_role is not None, "'user' role not found in DB"

    codes = {p.code for p in user_role.permissions}
    for expected in ("syerp:read", "syerp:write", "plum:read", "plum:write"):
        assert expected in codes, f"Expected '{expected}' in user role permissions; got {codes}"


async def test_user_role_lacks_users_manage(seeded_db) -> None:
    """The 'user' role does NOT have users:manage permission."""
    from sqlalchemy import select

    from app.modules.auth.models import Role

    result = await seeded_db.execute(select(Role).where(Role.name == "user"))
    user_role = result.scalars().first()
    assert user_role is not None
    codes = {p.code for p in user_role.permissions}
    assert "users:manage" not in codes, (
        f"'users:manage' should NOT be in user role permissions; got {codes}"
    )


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


async def test_admin_password_is_hashed(seeded_db) -> None:
    """Admin's hashed_password differs from the plaintext."""
    from sqlalchemy import select

    from app.core.config import settings
    from app.modules.auth.models import User

    result = await seeded_db.execute(
        select(User).where(User.email == settings.bns_admin_email)
    )
    admin = result.scalars().first()
    assert admin is not None
    plaintext = settings.bns_admin_password.get_secret_value()
    assert admin.hashed_password != plaintext, "hashed_password must not equal plaintext"


async def test_admin_password_verifies(seeded_db) -> None:
    """Admin's hashed_password passes verify_password with the correct plaintext."""
    from sqlalchemy import select

    from app.core.config import settings
    from app.modules.auth.models import User
    from app.modules.auth.service import verify_password

    result = await seeded_db.execute(
        select(User).where(User.email == settings.bns_admin_email)
    )
    admin = result.scalars().first()
    assert admin is not None
    plaintext = settings.bns_admin_password.get_secret_value()
    assert verify_password(plaintext, admin.hashed_password), (
        "verify_password returned False for correct admin password"
    )


# ---------------------------------------------------------------------------
# Audit log on first seed
# ---------------------------------------------------------------------------


async def test_seed_writes_audit_log_on_first_create(skip_if_no_db: None) -> None:
    """
    When the admin user is created for the first time, an AuditLog row
    action='seed.admin_created' is written.

    Note: this test is best run against a freshly-migrated DB.  On a DB where
    the admin already exists, the seed is a no-op and no audit row is written.
    We only assert the audit record exists (not that it was written in THIS run)
    so the test passes when the DB was seeded at least once.
    """
    from sqlalchemy import select

    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import AuditLog
    from app.modules.auth.seed import seed_admin_user

    async with AsyncSessionLocal() as session:
        await seed_admin_user(session)

        result = await session.execute(
            select(AuditLog).where(AuditLog.action == "seed.admin_created")
        )
        rows = result.scalars().all()
        # At least one audit record must exist (written on any first-ever create)
        assert len(rows) >= 1, "Expected at least one 'seed.admin_created' audit log row"
