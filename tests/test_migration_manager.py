"""
Tests for MigrationManager — filesystem-based migration directory resolution
and UVL-ordered feature discovery.
"""
import os
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def feature_workspace(tmp_path, monkeypatch):
    """
    Workspace with features that have migrations/ directories, linked
    via relative symlinks (like product:sync creates).
    """
    monkeypatch.setenv("WORKING_DIR", str(tmp_path))
    monkeypatch.setenv("SPLENT_APP", "test_app")

    product = tmp_path / "test_app"
    features_dir = product / "features" / "splent_io"
    features_dir.mkdir(parents=True)

    cache = tmp_path / ".splent_cache" / "features" / "splent_io"
    cache.mkdir(parents=True)

    pyproject = product / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "test_app"\nversion = "1.0.0"\n'
        '[project.optional-dependencies]\n'
        'features = [\n'
        '    "splent-io/splent_feature_auth@v1.0.0",\n'
        '    "splent-io/splent_feature_profile@v1.0.0",\n'
        ']\n'
    )

    # Create cached features with migrations
    for feat in ("splent_feature_auth", "splent_feature_profile"):
        feat_dir = cache / f"{feat}@v1.0.0"
        mig_dir = feat_dir / "src" / "splent_io" / feat / "migrations" / "versions"
        mig_dir.mkdir(parents=True)
        # Write a dummy migration
        (mig_dir / "001_initial.py").write_text("revision = '001'\n")

    # Create relative symlinks (like product:sync does)
    for feat in ("splent_feature_auth", "splent_feature_profile"):
        target = os.path.relpath(
            cache / f"{feat}@v1.0.0", features_dir
        )
        (features_dir / f"{feat}@v1.0.0").symlink_to(target)

    return tmp_path


@pytest.fixture
def feature_workspace_no_migrations(tmp_path, monkeypatch):
    """Workspace with features that have NO migrations."""
    monkeypatch.setenv("WORKING_DIR", str(tmp_path))
    monkeypatch.setenv("SPLENT_APP", "test_app")

    product = tmp_path / "test_app"
    features_dir = product / "features" / "splent_io"
    features_dir.mkdir(parents=True)

    cache = tmp_path / ".splent_cache" / "features" / "splent_io"
    cache.mkdir(parents=True)

    pyproject = product / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "test_app"\nversion = "1.0.0"\n'
        '[project.optional-dependencies]\n'
        'features = ["splent-io/splent_feature_redis@v1.0.0"]\n'
    )

    feat_dir = cache / "splent_feature_redis@v1.0.0" / "src" / "splent_io" / "splent_feature_redis"
    feat_dir.mkdir(parents=True)
    # No migrations/ directory

    target = os.path.relpath(
        cache / "splent_feature_redis@v1.0.0", features_dir
    )
    (features_dir / "splent_feature_redis@v1.0.0").symlink_to(target)

    return tmp_path


# ---------------------------------------------------------------------------
# Tests: get_feature_migration_dir
# ---------------------------------------------------------------------------

class TestGetFeatureMigrationDir:

    def test_finds_migration_dir_via_filesystem(self, feature_workspace):
        from splent_framework.managers.migration_manager import MigrationManager

        result = MigrationManager.get_feature_migration_dir("splent_feature_auth")
        assert result is not None
        assert result.endswith("migrations")
        assert os.path.isdir(result)

    def test_returns_none_when_no_migrations(self, feature_workspace_no_migrations):
        from splent_framework.managers.migration_manager import MigrationManager

        result = MigrationManager.get_feature_migration_dir("splent_feature_redis")
        assert result is None

    def test_returns_none_for_unknown_feature(self, feature_workspace):
        from splent_framework.managers.migration_manager import MigrationManager

        result = MigrationManager.get_feature_migration_dir("splent_feature_nonexistent")
        assert result is None

    def test_strips_version_from_name(self, feature_workspace):
        from splent_framework.managers.migration_manager import MigrationManager

        result = MigrationManager.get_feature_migration_dir("splent_feature_auth@v1.0.0")
        assert result is not None
        assert "migrations" in result

    def test_strips_org_from_name(self, feature_workspace):
        from splent_framework.managers.migration_manager import MigrationManager

        result = MigrationManager.get_feature_migration_dir("splent-io/splent_feature_auth")
        assert result is not None


# ---------------------------------------------------------------------------
# Tests: get_all_feature_migration_dirs
# ---------------------------------------------------------------------------

class TestGetAllFeatureMigrationDirs:

    def test_finds_all_features_with_migrations(self, feature_workspace):
        from splent_framework.managers.migration_manager import MigrationManager

        dirs = MigrationManager.get_all_feature_migration_dirs()
        assert len(dirs) == 2
        assert "splent_feature_auth" in dirs
        assert "splent_feature_profile" in dirs

    def test_returns_empty_when_no_features(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKING_DIR", str(tmp_path))
        monkeypatch.setenv("SPLENT_APP", "test_app")

        product = tmp_path / "test_app"
        product.mkdir()
        (product / "pyproject.toml").write_text(
            '[project]\nname = "test_app"\nversion = "1.0.0"\n'
            '[project.optional-dependencies]\nfeatures = []\n'
        )

        from splent_framework.managers.migration_manager import MigrationManager
        dirs = MigrationManager.get_all_feature_migration_dirs()
        assert dirs == {}

    def test_returns_empty_when_no_splent_app(self, monkeypatch):
        monkeypatch.delenv("SPLENT_APP", raising=False)

        from splent_framework.managers.migration_manager import MigrationManager
        dirs = MigrationManager.get_all_feature_migration_dirs()
        assert dirs == {}

    def test_skips_features_without_migrations(self, feature_workspace_no_migrations):
        from splent_framework.managers.migration_manager import MigrationManager

        dirs = MigrationManager.get_all_feature_migration_dirs()
        assert len(dirs) == 0

    def test_paths_are_absolute(self, feature_workspace):
        from splent_framework.managers.migration_manager import MigrationManager

        dirs = MigrationManager.get_all_feature_migration_dirs()
        for path in dirs.values():
            assert os.path.isabs(path)

    def test_paths_exist_on_disk(self, feature_workspace):
        from splent_framework.managers.migration_manager import MigrationManager

        dirs = MigrationManager.get_all_feature_migration_dirs()
        for path in dirs.values():
            assert os.path.isdir(path)


# ---------------------------------------------------------------------------
# Tests: relative symlinks work correctly
# ---------------------------------------------------------------------------

class TestSymlinkResolution:

    def test_symlinks_are_relative(self, feature_workspace):
        features_dir = feature_workspace / "test_app" / "features" / "splent_io"
        for link in features_dir.iterdir():
            assert link.is_symlink()
            target = os.readlink(str(link))
            assert not os.path.isabs(target), f"Symlink {link} has absolute target: {target}"

    def test_relative_symlinks_resolve_correctly(self, feature_workspace):
        features_dir = feature_workspace / "test_app" / "features" / "splent_io"
        for link in features_dir.iterdir():
            assert link.exists(), f"Symlink {link} is broken"
            assert (link / "src").is_dir(), f"src/ missing in {link}"
