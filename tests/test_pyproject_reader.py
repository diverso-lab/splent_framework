"""
Tests for splent_framework.utils.pyproject_reader.PyprojectReader

Covers all properties and both factory constructors.
"""
import pytest
from splent_framework.utils.pyproject_reader import PyprojectReader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_pyproject(directory, content: str) -> str:
    path = directory / "pyproject.toml"
    path.write_text(content)
    return str(path)


FULL_PYPROJECT = """\
[project]
name = "my_app"
version = "1.2.3"

[project.optional-dependencies]
features = [
    "splent_feature_auth@v1.0.0",
    "splent_feature_public@v1.0.0",
]

[tool.splent.uvl]
mirror = "uvlhub.io"
doi = "10.5281/zenodo.123"
file = "my_app.uvl"
"""


# ---------------------------------------------------------------------------
# Constructor: direct path
# ---------------------------------------------------------------------------

class TestDirectPath:
    def test_loads_valid_file(self, tmp_path):
        write_pyproject(tmp_path, FULL_PYPROJECT)
        r = PyprojectReader(str(tmp_path / "pyproject.toml"))
        assert r.name == "my_app"

    def test_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="pyproject.toml not found"):
            PyprojectReader(str(tmp_path / "nonexistent" / "pyproject.toml"))

    def test_raises_on_malformed_toml(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("not valid toml ][[[")
        with pytest.raises(RuntimeError, match="Invalid TOML"):
            PyprojectReader(str(tmp_path / "pyproject.toml"))

    def test_path_property(self, tmp_path):
        p = write_pyproject(tmp_path, FULL_PYPROJECT)
        assert PyprojectReader(p).path == p


# ---------------------------------------------------------------------------
# Constructor: for_product
# ---------------------------------------------------------------------------

class TestForProduct:
    def test_loads_from_product_dir(self, tmp_path):
        write_pyproject(tmp_path, FULL_PYPROJECT)
        r = PyprojectReader.for_product(str(tmp_path))
        assert r.name == "my_app"

    def test_raises_when_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            PyprojectReader.for_product(str(tmp_path / "missing_app"))


# ---------------------------------------------------------------------------
# Constructor: for_active_app
# ---------------------------------------------------------------------------

class TestForActiveApp:
    def test_reads_active_app(self, tmp_path, monkeypatch):
        app_dir = tmp_path / "test_app"
        app_dir.mkdir()
        write_pyproject(app_dir, FULL_PYPROJECT)
        monkeypatch.setenv("WORKING_DIR", str(tmp_path))
        monkeypatch.setenv("SPLENT_APP", "test_app")
        r = PyprojectReader.for_active_app()
        assert r.name == "my_app"

    def test_raises_when_active_app_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("WORKING_DIR", str(tmp_path))
        monkeypatch.setenv("SPLENT_APP", "nonexistent")
        with pytest.raises(FileNotFoundError):
            PyprojectReader.for_active_app()


# ---------------------------------------------------------------------------
# Properties: [project]
# ---------------------------------------------------------------------------

class TestProjectProperties:
    def test_name(self, tmp_path):
        write_pyproject(tmp_path, FULL_PYPROJECT)
        assert PyprojectReader.for_product(str(tmp_path)).name == "my_app"

    def test_version(self, tmp_path):
        write_pyproject(tmp_path, FULL_PYPROJECT)
        assert PyprojectReader.for_product(str(tmp_path)).version == "1.2.3"

    def test_name_returns_none_when_absent(self, tmp_path):
        write_pyproject(tmp_path, "[project.optional-dependencies]\nfeatures = []\n")
        assert PyprojectReader.for_product(str(tmp_path)).name is None

    def test_version_returns_none_when_absent(self, tmp_path):
        write_pyproject(tmp_path, "[project]\nname = \"app\"\n")
        assert PyprojectReader.for_product(str(tmp_path)).version is None


# ---------------------------------------------------------------------------
# Properties: features
# ---------------------------------------------------------------------------

class TestFeaturesProperty:
    def test_returns_feature_list(self, tmp_path):
        write_pyproject(tmp_path, FULL_PYPROJECT)
        features = PyprojectReader.for_product(str(tmp_path)).features
        assert features == ["splent_feature_auth@v1.0.0", "splent_feature_public@v1.0.0"]

    def test_returns_empty_list_when_key_absent(self, tmp_path):
        write_pyproject(tmp_path, "[project]\nname = \"app\"\n")
        assert PyprojectReader.for_product(str(tmp_path)).features == []

    def test_returns_empty_list_for_empty_array(self, tmp_path):
        write_pyproject(tmp_path, "[project.optional-dependencies]\nfeatures = []\n")
        assert PyprojectReader.for_product(str(tmp_path)).features == []

    def test_strips_whitespace_from_entries(self, tmp_path):
        write_pyproject(tmp_path,
            '[project.optional-dependencies]\nfeatures = ["  auth  ", " public "]\n'
        )
        assert PyprojectReader.for_product(str(tmp_path)).features == ["auth", "public"]

    def test_skips_blank_entries(self, tmp_path):
        write_pyproject(tmp_path,
            '[project.optional-dependencies]\nfeatures = ["auth", "", "  "]\n'
        )
        assert PyprojectReader.for_product(str(tmp_path)).features == ["auth"]

    def test_raises_when_features_not_a_list(self, tmp_path):
        write_pyproject(tmp_path,
            '[project.optional-dependencies]\nfeatures = "not-a-list"\n'
        )
        with pytest.raises(ValueError, match="must be a list"):
            PyprojectReader.for_product(str(tmp_path)).features


# ---------------------------------------------------------------------------
# Properties: [tool.splent]
# ---------------------------------------------------------------------------

class TestSplentConfig:
    def test_uvl_config(self, tmp_path):
        write_pyproject(tmp_path, FULL_PYPROJECT)
        uvl = PyprojectReader.for_product(str(tmp_path)).uvl_config
        assert uvl["mirror"] == "uvlhub.io"
        assert uvl["doi"] == "10.5281/zenodo.123"
        assert uvl["file"] == "my_app.uvl"

    def test_uvl_config_empty_when_absent(self, tmp_path):
        write_pyproject(tmp_path, "[project]\nname = \"app\"\n")
        assert PyprojectReader.for_product(str(tmp_path)).uvl_config == {}

    def test_splent_config_empty_when_absent(self, tmp_path):
        write_pyproject(tmp_path, "[project]\nname = \"app\"\n")
        assert PyprojectReader.for_product(str(tmp_path)).splent_config == {}
