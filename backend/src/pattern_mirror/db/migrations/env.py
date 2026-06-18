"""Alembic environment.

The database URL is taken from the Alembic config's ``sqlalchemy.url`` when one
is set (the test harness sets it to the test database) and otherwise from the
application settings, so ``alembic`` on the command line targets the dev/prod
database without the URL being written down twice. Importing the models package
populates ``Base.metadata`` so ``--autogenerate`` and ``check`` see every table.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from pattern_mirror import models  # noqa: F401  (imported for its metadata side effect)
from pattern_mirror.core.config import get_settings
from pattern_mirror.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    configured = config.get_main_option("sqlalchemy.url")
    return configured or get_settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout against a URL, without a live connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live connection to the resolved database."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
