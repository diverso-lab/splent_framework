"""
Reusable Alembic env.py logic for per-feature migrations in SPLENT.

Each feature that owns database tables should have:

    migrations/
    ├── alembic.ini     ← minimal config (no sqlalchemy.url needed)
    ├── env.py          ← calls run_feature_migrations() from here
    └── versions/       ← Alembic-generated migration scripts

Usage — in your feature's migrations/env.py:

    from splent_io.my_feature import models          # registers tables  # noqa
    from splent_framework.migrations.feature_env import run_feature_migrations

    FEATURE_NAME   = "splent_feature_auth"
    FEATURE_TABLES = {"user"}                        # table names owned by this feature

    run_feature_migrations(FEATURE_NAME, FEATURE_TABLES)

Design notes:
- Each feature uses a dedicated Alembic version table  ``alembic_<feature_name>``
  so migration tracking never collides between features that share the same DB.
- ``include_object`` restricts autogenerate to only the tables declared in
  ``FEATURE_TABLES``, preventing cross-feature migration interference.
- The DB connection is always taken from the running Flask app's engine, so
  ``sqlalchemy.url`` does not need to be set in alembic.ini.
"""

from logging.config import fileConfig

from flask import current_app
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from alembic import context

from splent_framework.db import db


def run_feature_migrations(feature_name: str, feature_tables: set[str]) -> None:
    """
    Execute Alembic migrations for a single SPLENT feature.

    Args:
        feature_name:   Python-safe feature identifier, e.g. ``"splent_feature_auth"``.
                        Used as the Alembic version table suffix (``alembic_<feature_name>``).
        feature_tables: Set of DB table names exclusively owned by this feature.
                        Only these tables are considered during autogenerate.
    """
    cfg = context.config

    if cfg.config_file_name is not None:
        fileConfig(cfg.config_file_name)

    target_metadata = db.metadata
    version_table = f"alembic_{feature_name}"

    def include_object(obj, name, type_, reflected, compare_to):
        if type_ == "table":
            return name in feature_tables
        return True

    def run_offline() -> None:
        # Offline mode: read URL from the Flask app config
        url = current_app.config.get("SQLALCHEMY_DATABASE_URI")
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            version_table=version_table,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()

    def run_online() -> None:
        # Online mode: reuse the Flask-SQLAlchemy engine directly
        connectable = current_app.extensions["migrate"].db.engine

        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                version_table=version_table,
                include_object=include_object,
            )
            with context.begin_transaction():
                context.run_migrations()

    if context.is_offline_mode():
        run_offline()
    else:
        run_online()
