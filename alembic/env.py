"""Alembic migration environment."""

from __future__ import annotations

from logging.config import fileConfig

import archium.infrastructure.database.models  # noqa: F401
from alembic import context
from archium.config.settings import get_settings
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.session import create_engine_from_settings
from sqlalchemy import create_engine, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return get_settings().resolved_database_url


def run_migrations_offline() -> None:
    context.configure(
        url=config.attributes.get("engine_url") or get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=get_settings().is_sqlite,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine_url = config.attributes.get("engine_url")
    if engine_url:
        connectable = create_engine(engine_url, poolclass=pool.NullPool)
    else:
        connectable = create_engine_from_settings(get_settings(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=get_settings().is_sqlite,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
