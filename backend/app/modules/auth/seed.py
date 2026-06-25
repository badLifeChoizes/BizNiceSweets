"""
First-admin and role/permission seed.

Called from app.core.seed:run_seeds() on every application startup.
All operations are idempotent — safe to call on repeated `podman-compose up`
(D-02, D-09).

Seed sequence:
  1. Upsert permission rows by code (users:manage, syerp:read, syerp:write,
     plum:read, plum:write) — check existence before insert.
  2. Upsert 'admin' and 'user' roles by name.
  3. Assign ALL permissions to 'admin'; assign the four business read/write
     permissions to 'user' (but NOT users:manage).
  4. Create the admin User only if no row with bns_admin_email exists; hash
     the password via hash_password; attach the 'admin' role.
  5. Write an AuditLog row action='seed.admin_created' ONLY when the admin is
     actually created (not on subsequent no-op runs).

Sources:
  02-RESEARCH.md Pattern 7
  02-CONTEXT.md D-02, D-09
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# Permission codes seeded by this module
_PERMISSIONS: list[tuple[str, str]] = [
    ("users:manage", "Create, edit, and deactivate user accounts"),
    ("syerp:read", "Read access to SYERP (ERP/financials/inventory)"),
    ("syerp:write", "Write access to SYERP"),
    ("plum:read", "Read access to PLUM (Product Lifecycle Management)"),
    ("plum:write", "Write access to PLUM"),
]

# Permissions granted to the standard 'user' role (all EXCEPT users:manage)
_USER_ROLE_PERMS: set[str] = {"syerp:read", "syerp:write", "plum:read", "plum:write"}


async def seed_admin_user(db: "AsyncSession") -> None:
    """
    Idempotent first-admin + role/permission bootstrap.

    This function is safe to call on every application startup.  When the
    admin user, roles, and permissions already exist the function returns
    without making any changes (no duplicate rows, no errors).

    Implements D-02 (first admin from env) and D-09 (roles/permissions as
    data rows, not hardcoded enums; admin seeded on every startup idempotently).
    """
    from sqlalchemy import select

    from app.core.config import settings
    from app.modules.auth.models import AuditLog, Permission, Role, User
    from app.modules.auth.service import hash_password

    # ------------------------------------------------------------------
    # 1. Upsert permissions by code
    # ------------------------------------------------------------------
    permission_map: dict[str, Permission] = {}
    for code, description in _PERMISSIONS:
        result = await db.execute(select(Permission).where(Permission.code == code))
        perm = result.scalars().first()
        if perm is None:
            perm = Permission(code=code, description=description)
            db.add(perm)
            await db.flush()  # assign id before we reference it in relationships
        permission_map[code] = perm

    # ------------------------------------------------------------------
    # 2. Upsert 'admin' role
    # ------------------------------------------------------------------
    result = await db.execute(select(Role).where(Role.name == "admin"))
    admin_role = result.scalars().first()
    if admin_role is None:
        admin_role = Role(name="admin", description="Full administrative access (wildcard)")
        db.add(admin_role)
        await db.flush()

    # ------------------------------------------------------------------
    # 3. Upsert 'user' role
    # ------------------------------------------------------------------
    result = await db.execute(select(Role).where(Role.name == "user"))
    user_role = result.scalars().first()
    if user_role is None:
        user_role = Role(name="user", description="Standard business user access")
        db.add(user_role)
        await db.flush()

    # ------------------------------------------------------------------
    # 4. Assign permissions to roles (idempotent via set-difference)
    # ------------------------------------------------------------------
    # Admin role gets ALL permissions (wildcard — wildcard logic in service
    # is triggered by role.name == "admin"; we still assign all codes
    # so that the permission list on the admin role is complete and auditable).
    admin_existing_codes = {p.code for p in await admin_role.awaitable_attrs.permissions}
    for code, perm in permission_map.items():
        if code not in admin_existing_codes:
            admin_role.permissions.append(perm)

    # User role gets the four business permissions only (NOT users:manage)
    user_existing_codes = {p.code for p in await user_role.awaitable_attrs.permissions}
    for code in _USER_ROLE_PERMS:
        if code not in user_existing_codes:
            user_role.permissions.append(permission_map[code])

    await db.flush()

    # ------------------------------------------------------------------
    # 5. Create admin User if not already present
    # ------------------------------------------------------------------
    admin_email = settings.bns_admin_email
    result = await db.execute(select(User).where(User.email == admin_email))
    admin_user = result.scalars().first()

    if admin_user is None:
        # Hash the plaintext password from settings; never store plaintext (D-12)
        hashed = hash_password(settings.bns_admin_password.get_secret_value())
        admin_user = User(
            email=admin_email,
            hashed_password=hashed,
            full_name="System Administrator",
            is_active=True,
        )
        admin_user.roles.append(admin_role)
        db.add(admin_user)
        await db.flush()

        # ------------------------------------------------------------------
        # 6. Write audit log ONLY on actual creation (not on no-op reruns)
        # ------------------------------------------------------------------
        audit = AuditLog(
            actor_id=None,  # system action — no human actor
            action="seed.admin_created",
            target_type="user",
            target_id=str(admin_user.id),
            detail=f"First admin user seeded from environment: {admin_email}",
        )
        db.add(audit)

    await db.commit()
