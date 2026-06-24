"""add_auth_tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-23 00:00:00.000000+00:00

Phase 2 — Authentication & Users.

Creates all seven auth tables in a single revision within the existing
Alembic history (Phase 1 established the single history).

Tables:
  users              — account records (UUID-string PK, email unique+indexed)
  roles              — role definitions (int PK, name unique)
  permissions        — module:action permission codes (int PK, code unique+indexed)
  user_roles         — M2M association: users ↔ roles
  role_permissions   — M2M association: roles ↔ permissions
  refresh_tokens     — server-side refresh token tracking (token_hash SHA-256,
                       family for chain revocation — D-05, D-07)
  audit_log          — minimal auth/identity audit log (D-14)

Migration was authored from the SQLAlchemy models in app/modules/auth/models.py
with no live DB available at plan time; structure matches the ORM definitions
exactly.  After running `podman-compose up`, `alembic upgrade head` will apply
this migration to the live PostgreSQL instance.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # roles
    # ------------------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    # ------------------------------------------------------------------
    # permissions
    # ------------------------------------------------------------------
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        # Format: "module:action" e.g. "syerp:read", "users:manage"
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=True)

    # ------------------------------------------------------------------
    # user_roles  (M2M association table — no mapped class)
    # ------------------------------------------------------------------
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
    )

    # ------------------------------------------------------------------
    # role_permissions  (M2M association table — no mapped class)
    # ------------------------------------------------------------------
    op.create_table(
        "role_permissions",
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            sa.Integer(),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
    )

    # ------------------------------------------------------------------
    # refresh_tokens
    # token_hash: SHA-256 hex of raw token (T-02-04 — store hash, not raw)
    # family: links a rotation chain for reuse-detection revocation (D-07)
    # ------------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("family", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )
    op.create_index("ix_refresh_tokens_family", "refresh_tokens", ["family"], unique=False)

    # ------------------------------------------------------------------
    # audit_log  (D-14 — minimal auth/identity audit trail)
    # actor_id is nullable: None = system action (e.g. seed run)
    # ------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("audit_log")
    op.drop_index("ix_refresh_tokens_family", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_index("ix_permissions_code", table_name="permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
