"""
Tests for NamespaceManager private helpers.

NamespaceManager.init_app is integration-only (touches sys.path and importlib),
so we test the four extracted static methods in isolation using tmp_path.
"""

import os
import sys
import pytest
from splent_framework.managers.namespace_manager import NamespaceManager


# ---------------------------------------------------------------------------
# _detect_orgs
# ---------------------------------------------------------------------------

class TestDetectOrgs:
    def test_returns_all_subdirectories(self, tmp_path):
        (tmp_path / "org_a").mkdir()
        (tmp_path / "org_b").mkdir()
        result = NamespaceManager._detect_orgs(str(tmp_path))
        assert set(result) == {"org_a", "org_b"}

    def test_ignores_regular_files(self, tmp_path):
        (tmp_path / "org_a").mkdir()
        (tmp_path / "somefile.txt").write_text("x")
        result = NamespaceManager._detect_orgs(str(tmp_path))
        assert result == ["org_a"]

    def test_returns_empty_list_for_empty_dir(self, tmp_path):
        assert NamespaceManager._detect_orgs(str(tmp_path)) == []


# ---------------------------------------------------------------------------
# _ensure_init_files
# ---------------------------------------------------------------------------

class TestEnsureInitFiles:
    def test_creates_init_py_when_missing(self, tmp_path):
        (tmp_path / "myorg").mkdir()
        NamespaceManager._ensure_init_files(["myorg"], str(tmp_path))
        init = tmp_path / "myorg" / "__init__.py"
        assert init.exists()

    def test_init_py_contains_comment(self, tmp_path):
        (tmp_path / "myorg").mkdir()
        NamespaceManager._ensure_init_files(["myorg"], str(tmp_path))
        content = (tmp_path / "myorg" / "__init__.py").read_text()
        assert "myorg" in content

    def test_does_not_overwrite_existing_init_py(self, tmp_path):
        (tmp_path / "myorg").mkdir()
        init = tmp_path / "myorg" / "__init__.py"
        init.write_text("# custom content\n")
        NamespaceManager._ensure_init_files(["myorg"], str(tmp_path))
        assert init.read_text() == "# custom content\n"

    def test_creates_namespace_dir_if_missing(self, tmp_path):
        NamespaceManager._ensure_init_files(["neworg"], str(tmp_path))
        assert (tmp_path / "neworg").is_dir()


# ---------------------------------------------------------------------------
# _add_to_syspath
# ---------------------------------------------------------------------------

class TestAddToSyspath:
    def test_adds_src_dirs_to_syspath(self, tmp_path):
        src = tmp_path / "org_a" / "feature_x" / "src"
        src.mkdir(parents=True)
        before = list(sys.path)
        NamespaceManager._add_to_syspath(str(tmp_path))
        assert str(src) in sys.path
        # cleanup
        sys.path[:] = before

    def test_does_not_add_duplicate(self, tmp_path):
        src = tmp_path / "org_a" / "feature_x" / "src"
        src.mkdir(parents=True)
        sys.path.insert(0, str(src))
        count_before = sys.path.count(str(src))
        NamespaceManager._add_to_syspath(str(tmp_path))
        assert sys.path.count(str(src)) == count_before
        # cleanup
        sys.path.remove(str(src))

    def test_no_src_dirs_leaves_syspath_unchanged(self, tmp_path):
        before = list(sys.path)
        NamespaceManager._add_to_syspath(str(tmp_path))
        assert sys.path == before
