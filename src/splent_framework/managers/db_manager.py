from splent_framework.managers.migration_manager import MigrationManager


class MigrateManager(MigrationManager):
    """
    Backward-compatible alias for MigrationManager.

    App factories that import MigrateManager continue to work without changes:

        from splent_framework.managers.db_manager import MigrateManager
        MigrateManager(app)

    All migration logic — including splent_migrations table creation and
    per-feature migration support — is now in MigrationManager.
    """
