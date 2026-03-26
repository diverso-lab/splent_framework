"""
Tests for PyprojectReader env-aware feature reading.
"""
import pytest
from pathlib import Path


@pytest.fixture
def pyproject_file(tmp_path):
    """Write a pyproject.toml with base + dev + prod features."""
    content = '''\
[project]
name = "test_app"
version = "1.0.0"

[tool.splent]
features = ["splent-io/feat_auth@v1.0.0", "splent-io/feat_public@v1.0.0"]
features_dev = ["splent-io/feat_debug@v1.0.0"]
features_prod = ["splent-io/feat_monitor@v1.0.0"]

[tool.splent.uvl]
file = "test.uvl"
'''
    f = tmp_path / "pyproject.toml"
    f.write_text(content)
    return tmp_path


class TestFeaturesForEnv:

    def test_base_only(self, pyproject_file):
        from splent_framework.utils.pyproject_reader import PyprojectReader
        reader = PyprojectReader.for_product(str(pyproject_file))
        result = reader.features_for_env(None)
        assert len(result) == 2

    def test_dev_merges(self, pyproject_file):
        from splent_framework.utils.pyproject_reader import PyprojectReader
        reader = PyprojectReader.for_product(str(pyproject_file))
        result = reader.features_for_env("dev")
        assert len(result) == 3
        assert "splent-io/feat_debug@v1.0.0" in result

    def test_prod_merges(self, pyproject_file):
        from splent_framework.utils.pyproject_reader import PyprojectReader
        reader = PyprojectReader.for_product(str(pyproject_file))
        result = reader.features_for_env("prod")
        assert len(result) == 3
        assert "splent-io/feat_monitor@v1.0.0" in result

    def test_base_property_unchanged(self, pyproject_file):
        from splent_framework.utils.pyproject_reader import PyprojectReader
        reader = PyprojectReader.for_product(str(pyproject_file))
        assert len(reader.features) == 2
        assert len(reader.features_dev) == 1
        assert len(reader.features_prod) == 1

    def test_unknown_env_returns_base(self, pyproject_file):
        from splent_framework.utils.pyproject_reader import PyprojectReader
        reader = PyprojectReader.for_product(str(pyproject_file))
        result = reader.features_for_env("staging")
        assert len(result) == 2
