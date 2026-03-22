"""
Tests for splent_framework.utils.feature_utils.get_features_from_pyproject

Covers:
- Returns list of features from a valid pyproject.toml
- Returns [] when pyproject.toml does not exist
- Returns [] when [project.optional-dependencies] key is missing
- Raises RuntimeError on malformed TOML (not silent swallow)
"""
import pytest
from splent_framework.utils.feature_utils import get_features_from_pyproject


@pytest.fixture(autouse=True)
def set_env(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKING_DIR", str(tmp_path))
    monkeypatch.setenv("SPLENT_APP", "test_app")


@pytest.fixture
def app_dir(tmp_path):
    d = tmp_path / "test_app"
    d.mkdir()
    return d


class TestGetFeaturesFromPyproject:
    def test_returns_features_list(self, app_dir):
        (app_dir / "pyproject.toml").write_text(
            '[project.optional-dependencies]\n'
            'features = ["splent_feature_auth@v1.0.0", "splent_feature_public@v1.0.0"]\n'
        )
        result = get_features_from_pyproject()
        assert result == ["splent_feature_auth@v1.0.0", "splent_feature_public@v1.0.0"]

    def test_returns_empty_list_when_features_key_missing(self, app_dir):
        (app_dir / "pyproject.toml").write_text(
            '[project.optional-dependencies]\n'
            'core = ["flask"]\n'
        )
        result = get_features_from_pyproject()
        assert result == []

    def test_returns_empty_list_when_optional_dependencies_missing(self, app_dir):
        (app_dir / "pyproject.toml").write_text(
            '[project]\nname = "test_app"\nversion = "1.0.0"\n'
        )
        result = get_features_from_pyproject()
        assert result == []

    def test_returns_empty_list_when_file_does_not_exist(self):
        # app_dir not created, pyproject.toml doesn't exist
        result = get_features_from_pyproject()
        assert result == []

    def test_raises_on_malformed_toml(self, app_dir):
        (app_dir / "pyproject.toml").write_text("this is not valid toml ][[[")
        with pytest.raises(RuntimeError, match="Invalid TOML"):
            get_features_from_pyproject()

    def test_returns_empty_list_for_empty_features(self, app_dir):
        (app_dir / "pyproject.toml").write_text(
            '[project.optional-dependencies]\nfeatures = []\n'
        )
        result = get_features_from_pyproject()
        assert result == []

    def test_returns_single_feature(self, app_dir):
        (app_dir / "pyproject.toml").write_text(
            '[project.optional-dependencies]\nfeatures = ["splent_feature_auth"]\n'
        )
        result = get_features_from_pyproject()
        assert result == ["splent_feature_auth"]
