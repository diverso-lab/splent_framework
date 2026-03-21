"""
Per-feature database migration manager for SPLENT.

Each feature can ship its own migrations/ directory:

    src/splent_io/<feature>/
    └── migrations/
        ├── env.py          ← must call run_feature_migrations() from feature_env.py
        └── versions/       ← Alembic migration scripts

The ``splent_migrations`` table is the central tracking store:

    CREATE TABLE splent_migrations (
        feature        VARCHAR(255) NOT NULL,
        last_migration VARCHAR(255) DEFAULT NULL,
        PRIMARY KEY (feature)
    );

Each feature's Alembic state is additionally tracked in a dedicated table
``alembic_<feature_name>`` (set inside the feature's env.py).  After every
migrate/upgrade the CLI syncs the current revision into ``splent_migrations``.
"""

import os
import importlib.util

from flask_migrate import Migrate
from sqlalchemy import text

from splent_framework.db import db

SPLENT_MIGRATIONS_TABLE = "splent_migrations"


class MigrationManager:
    """
    Initialises Flask-Migrate and ensures the splent_migrations tracking table exists.

    Replaces the old MigrateManager — app factories should swap the import:

        from splent_framework.managers.migration_manager import MigrationManager
        MigrationManager(app)
    """

    def __init__(self, app):
        self.app = app
        self.migrate = None
        self._init_flask_migrate()
        self._ensure_splent_migrations_table()

    # ──────────────────────────── initialisation ───────────────────────────

    def _init_flask_migrate(self) -> None:
        from splent_cli.utils.path_utils import PathUtils

        self.migrate = Migrate(directory=PathUtils.get_migrations_dir())
        db.init_app(self.app)
        self.migrate.init_app(self.app, db)

    def _ensure_splent_migrations_table(self) -> None:
        """Create splent_migrations if it does not yet exist."""
        with self.app.app_context():
            try:
                with db.engine.begin() as conn:
                    conn.execute(
                        text(
                            f"""
                            CREATE TABLE IF NOT EXISTS `{SPLENT_MIGRATIONS_TABLE}` (
                                `feature`        VARCHAR(255) NOT NULL,
                                `last_migration` VARCHAR(255) DEFAULT NULL,
                                PRIMARY KEY (`feature`)
                            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                            """
                        )
                    )
            except Exception as exc:
                print(f"⚠️  Could not ensure {SPLENT_MIGRATIONS_TABLE} table: {exc}")

    # ──────────────────────────── static helpers ───────────────────────────

    @staticmethod
    def get_feature_migration_dir(feature_name: str) -> str | None:
        """
        Return the absolute path to the feature's ``migrations/`` directory, or
        ``None`` if the package cannot be resolved.

        Works with versioned names (``splent_feature_auth@v1.0.0``) by stripping
        the version suffix before the import lookup.
        """
        base_name = feature_name.split("@")[0]
        try:
            spec = importlib.util.find_spec(f"splent_io.{base_name}")
            if spec and spec.origin:
                return os.path.join(os.path.dirname(spec.origin), "migrations")
        except (ModuleNotFoundError, ValueError):
            pass
        return None

    @staticmethod
    def get_all_feature_migration_dirs() -> dict[str, str]:
        """
        Return ``{feature_name: migrations_dir}`` for every feature declared in
        the product's pyproject.toml that has a ``migrations/`` directory on disk.
        """
        from splent_cli.utils.feature_utils import get_features_from_pyproject

        result: dict[str, str] = {}
        for spec in get_features_from_pyproject() or []:
            name = spec.split("@")[0]
            mdir = MigrationManager.get_feature_migration_dir(name)
            if mdir and os.path.isdir(mdir):
                result[name] = mdir
        return result

    @staticmethod
    def get_current_feature_revision(feature_name: str, engine) -> str | None:
        """
        Query ``alembic_<feature_name>`` for the current revision, returning
        ``None`` if the table does not exist or is empty.

        This table is created by the feature's env.py (via ``feature_env.py``)
        using ``version_table=f"alembic_{feature_name}"``.
        """
        version_table = f"alembic_{feature_name}"
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(f"SELECT version_num FROM `{version_table}` LIMIT 1")
                ).fetchone()
                return row[0] if row else None
        except Exception:
            return None

    @staticmethod
    def update_feature_status(app, feature_name: str, revision: str | None) -> None:
        """Upsert ``(feature_name, revision)`` in splent_migrations."""
        with app.app_context():
            with db.engine.begin() as conn:
                conn.execute(
                    text(
                        f"""
                        INSERT INTO `{SPLENT_MIGRATIONS_TABLE}` (feature, last_migration)
                        VALUES (:feature, :revision)
                        ON DUPLICATE KEY UPDATE last_migration = :revision
                        """
                    ),
                    {"feature": feature_name, "revision": revision},
                )

    @staticmethod
    def get_all_status(app) -> list[tuple[str, str | None]]:
        """Return ``[(feature, last_migration), ...]`` from splent_migrations."""
        with app.app_context():
            with db.engine.connect() as conn:
                rows = conn.execute(
                    text(
                        f"SELECT feature, last_migration "
                        f"FROM `{SPLENT_MIGRATIONS_TABLE}` ORDER BY feature"
                    )
                ).fetchall()
                return [(r[0], r[1]) for r in rows]
