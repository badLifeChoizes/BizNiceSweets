"""
Auth module ORM models.

Tables: users, roles, permissions, user_roles (M2M), role_permissions (M2M),
        refresh_tokens, audit_log.

All models inherit from app.core.base.Base so that Base.metadata is fully
populated when the central aggregator (app.core.models) is imported by
Alembic's env.py.

lazy="selectin" on collection relationships is MANDATORY for async SQLAlchemy
to avoid the MissingGreenlet error when roles/permissions are accessed outside
an active session context (RESEARCH.md Pitfall 1).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base

# ---------------------------------------------------------------------------
# Association tables (no mapped class — join table only)
# ---------------------------------------------------------------------------

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ---------------------------------------------------------------------------
# Entity tables
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # lazy="selectin" — loads roles in a single additional SELECT before the
    # session closes; prevents MissingGreenlet in async context (Pitfall 1).
    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles, back_populates="users", lazy="selectin"
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")
    # lazy="selectin" — same async-safe pattern as User.roles.
    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions, back_populates="roles", lazy="selectin"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Format: "module:action" — e.g. "syerp:read", "users:manage", "plum:write"
    code: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    roles: Mapped[list[Role]] = relationship(
        secondary=role_permissions, back_populates="permissions"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # SHA-256 of the opaque raw token — DB compromise does not expose raw tokens (T-02-04)
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # family links a rotation chain; reuse detection revokes the whole family (D-07)
    family: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # actor_id: None = system action (e.g. seed); str = user_id of acting user
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    # target_type: "user", "role", "session", etc.
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
