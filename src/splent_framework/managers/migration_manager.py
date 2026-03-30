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

import logging
import os
import importlib.util

from flask_migrate import Migrate
from sqlalchemy import text
from sqlalchemy import exc as sa_exc

from splent_framework.db import db

logger = logging.getLogger(__name__)

SPLENT_MIGRATIONS_TABLE = "splent_migrations"


def alembic_version_table(feature_name: str) -> str:
    """Return the Alembic version table name for a given feature."""
    return f"alembic_{feature_name}"


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
        from splent_framework.utils.path_utils import PathUtils

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
            except sa_exc.SQLAlchemyError as exc:
                logger.error(
                    "Could not ensure %s table: %s",
                    SPLENT_MIGRATIONS_TABLE,
                    exc,
                    exc_info=True,
                )

    # ──────────────────────────── static helpers ───────────────────────────

    @staticmethod
    def get_feature_migration_dir(feature_name: str) -> str | None:
        """
        Return the absolute path to the feature's ``migrations/`` directory, or
        ``None`` if the package cannot be resolved.

        Resolution order:
          1. Filesystem lookup via product features/ symlinks (works everywhere).
          2. Fallback to importlib (for editable/pip-installed features).
        """
        base_name = feature_name.split("@")[0]
        if "/" in base_name:
            base_name = base_name.split("/")[-1]

        # 1. Filesystem lookup via features/ directory
        from splent_framework.utils.path_utils import PathUtils

        features_base = os.path.join(PathUtils.get_app_base_dir(), "features")
        if os.path.isdir(features_base):
            for org_dir in os.listdir(features_base):
                org_path = os.path.join(features_base, org_dir)
                if not os.path.isdir(org_path):
                    continue
                for entry in os.listdir(org_path):
                    entry_name = entry.split("@")[0]
                    if entry_name == base_name:
                        mdir = os.path.join(
                            org_path, entry, "src", org_dir, base_name, "migrations"
                        )
                        if os.path.isdir(mdir):
                            return os.path.abspath(mdir)

        # 2. Fallback to importlib
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

        The dict is ordered according to the UVL dependency constraints so that
        features are migrated after their dependencies (e.g. auth before profile).
        """
        from splent_framework.utils.path_utils import PathUtils
        from splent_framework.utils.pyproject_reader import PyprojectReader
        from splent_framework.managers.feature_order import FeatureLoadOrderResolver
        from splent_framework.managers.feature_loader import FeatureEntryParser

        splent_app = os.getenv("SPLENT_APP")
        if not splent_app:
            return {}

        product_dir = os.path.join(PathUtils.get_working_dir(), splent_app)

        try:
            reader = PyprojectReader.for_product(product_dir)
            env = os.getenv("SPLENT_ENV")
            features_raw = reader.features_for_env(env)
        except (FileNotFoundError, RuntimeError):
            return {}

        if not features_raw:
            return {}

        # Resolve UVL-based load order
        uvl_file = None
        try:
            uvl_cfg = reader.uvl_config
            if uvl_cfg.get("file"):
                uvl_file = os.path.join(product_dir, "uvl", uvl_cfg["file"])
        except (RuntimeError, KeyError):
            pass

        parser = FeatureEntryParser()
        resolver = FeatureLoadOrderResolver(parser)
        ordered = resolver.resolve(features_raw, uvl_file)

        result: dict[str, str] = {}
        for entry in ordered:
            name = entry.split("@")[0]
            if "/" in name:
                name = name.split("/")[-1]
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
        using ``alembic_version_table(feature_name)``.
        """
        version_table = alembic_version_table(feature_name)
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(f"SELECT version_num FROM `{version_table}` LIMIT 1")
                ).fetchone()
                return row[0] if row else None
        except sa_exc.SQLAlchemyError:
            # Table may not exist yet (feature not yet migrated) — this is expected
            logger.debug(
                "No revision found for feature '%s' (table may not exist yet)",
                feature_name,
            )
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
    def delete_feature_status(app, feature_name: str) -> None:
        """Remove the row for *feature_name* from splent_migrations."""
        with app.app_context():
            with db.engine.begin() as conn:
                conn.execute(
                    text(
                        f"DELETE FROM `{SPLENT_MIGRATIONS_TABLE}` WHERE feature = :feature"
                    ),
                    {"feature": feature_name},
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
