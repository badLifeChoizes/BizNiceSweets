"""
Alembic migration environment — single history, multi-module autogenerate.

Key wiring:
  1. import app.core.models  — side-effect populates Base.metadata with every
     module's table definitions (Pitfall 1: never skip this import).
  2. target_metadata = Base.metadata — the metadata Alembic autogenerates from.
  3. settings.database_url_sync — psycopg2 URL injected at runtime (T-01-02:
     no hardcoded URL in alembic.ini).

Alembic CLI is synchronous; env.py uses a sync engine even though the app
uses an async engine (asyncpg). This is the standard production pattern
(Open Question 1 in RESEARCH.md).
"""
import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# CRITICAL: import the central model aggregator BEFORE configuring Alembic.
# This populates Base.metadata with every module's table definitions so that
# autogenerate can see them. Never comment this out or move it below the
# context.configure call.
# ---------------------------------------------------------------------------
import app.core.models  # noqa: F401 — side-effect: populates Base.metadata

from app.core.base import Base
from app.core.config import settings

# ---------------------------------------------------------------------------
# Alembic config object (provides access to alembic.ini values)
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# ---------------------------------------------------------------------------
# Inject DB URL from pydantic-settings (T-01-02: no hardcoded URL in .ini)
# ---------------------------------------------------------------------------
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# The single target metadata for autogenerate — fully populated by the import
# above.
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline migrations (generate SQL without a live DB connection)
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well. By skipping the Engine creation we
    don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (run against a live DB connection)
# ---------------------------------------------------------------------------


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
