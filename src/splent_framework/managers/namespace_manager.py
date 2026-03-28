# splent_framework/managers/namespace_manager.py

import glob
import importlib
import logging
import os
import sys

from splent_framework.utils.path_utils import PathUtils

logger = logging.getLogger(__name__)


class NamespaceManager:
    @staticmethod
    def init_app(app=None):
        """Register namespace packages for all organizations.

        In development: scans .splent_cache/features and workspace root.
        In production: features are pip-installed, so we just ensure
        the namespace packages are importable.
        """
        working_dir = PathUtils.get_working_dir()
        base_cache_dir = os.path.join(working_dir, ".splent_cache", "features")

        orgs: list[str] = []

        if os.path.exists(base_cache_dir):
            # Development: resolve from cache + workspace root
            orgs = NamespaceManager._detect_orgs(base_cache_dir)
            if orgs:
                NamespaceManager._ensure_init_files(orgs, base_cache_dir)
                NamespaceManager._add_to_syspath(base_cache_dir)
            NamespaceManager._add_workspace_root_features(working_dir)

        # Always try to import known namespace packages.
        # In production, pip-installed features make splent_io available
        # without any cache or workspace root directories.
        if not orgs:
            orgs = ["splent_io"]

        NamespaceManager._import_namespaces(orgs)

    # ------------------------------------------------------------------

    @staticmethod
    def _detect_orgs(base_cache_dir: str) -> list[str]:
        """Return the list of org directory names found under base_cache_dir."""
        return [
            d
            for d in os.listdir(base_cache_dir)
            if os.path.isdir(os.path.join(base_cache_dir, d))
        ]

    @staticmethod
    def _ensure_init_files(orgs: list[str], base_cache_dir: str) -> None:
        """Create missing __init__.py files so each org directory is a package."""
        for org in orgs:
            namespace_dir = os.path.join(base_cache_dir, org)
            init_file = os.path.join(namespace_dir, "__init__.py")
            os.makedirs(namespace_dir, exist_ok=True)
            if not os.path.exists(init_file):
                with open(init_file, "w") as f:
                    f.write(f"# {org} namespace package\n")
                logger.debug("Created missing namespace __init__.py for '%s'", org)

    @staticmethod
    def _add_to_syspath(base_cache_dir: str) -> None:
        """Insert every feature src/ directory into sys.path."""
        for src in glob.glob(os.path.join(base_cache_dir, "*", "*", "src")):
            if src not in sys.path:
                sys.path.insert(0, src)

    @staticmethod
    def _add_workspace_root_features(working_dir: str) -> None:
        """Add src/ directories of editable features at the workspace root to sys.path.

        Editable features live at {workspace}/{feature_name}/ with an internal
        src/ directory.  Only directories matching the splent_feature_* naming
        convention are considered.
        """
        for entry in os.listdir(working_dir):
            if not entry.startswith("splent_feature_"):
                continue
            src = os.path.join(working_dir, entry, "src")
            if os.path.isdir(src) and src not in sys.path:
                sys.path.insert(0, src)
                logger.debug("Workspace root feature src added: %s", src)

    @staticmethod
    def _import_namespaces(orgs: list[str]) -> None:
        """Import each org namespace package so Python can resolve feature imports."""
        importlib.invalidate_caches()
        for org in orgs:
            try:
                importlib.import_module(org)
                logger.debug("Namespace '%s' registered.", org)
            except (ImportError, ModuleNotFoundError) as e:
                logger.error(
                    "Failed to import namespace '%s': %s", org, e, exc_info=True
                )
