"""
PyprojectReader — single source of truth for reading pyproject.toml in SPLENT.

All framework and CLI code that needs to *read* a pyproject.toml should go
through this class instead of calling ``tomllib.load()`` directly.

Write operations (feature add/remove, version bumps) are CLI-specific and
remain in the CLI using ``tomli_w``.

Usage::

    # Active app (uses SPLENT_APP + WORKING_DIR env vars)
    reader = PyprojectReader.for_active_app()

    # Explicit directory containing a pyproject.toml
    reader = PyprojectReader.for_product("/workspace/my_app")

    # Specific file path
    reader = PyprojectReader("/workspace/my_app/pyproject.toml")

    reader.features       # list[str]
    reader.name           # str | None
    reader.version        # str | None
    reader.uvl_config     # dict  ([tool.splent.uvl])
    reader.splent_config  # dict  ([tool.splent])
"""

import logging
import os
import tomllib

logger = logging.getLogger(__name__)


class PyprojectReader:
    """Read-only access to the contents of a pyproject.toml file."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._data: dict = self._load()

    # ── constructors ──────────────────────────────────────────────────────

    @classmethod
    def for_active_app(cls) -> "PyprojectReader":
        """
        Load pyproject.toml for the currently active SPLENT_APP.
        Resolves path via WORKING_DIR + SPLENT_APP environment variables.
        """
        from splent_framework.utils.path_utils import PathUtils

        path = os.path.join(PathUtils.get_app_base_dir(), "pyproject.toml")
        return cls(path)

    @classmethod
    def for_product(cls, product_dir: str) -> "PyprojectReader":
        """Load pyproject.toml from a product root directory."""
        return cls(os.path.join(product_dir, "pyproject.toml"))

    # ── internal ──────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if not os.path.exists(self._path):
            raise FileNotFoundError(f"pyproject.toml not found at {self._path}")
        try:
            with open(self._path, "rb") as f:
                return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise RuntimeError(f"Invalid TOML in {self._path}: {e}") from e

    # ── [project] ─────────────────────────────────────────────────────────

    @property
    def name(self) -> str | None:
        """Value of [project].name."""
        return self._data.get("project", {}).get("name")

    @property
    def version(self) -> str | None:
        """Value of [project].version."""
        return self._data.get("project", {}).get("version")

    @property
    def optional_dependencies(self) -> dict[str, list[str]]:
        """Full contents of [project.optional-dependencies] as {group: [entries]}."""
        raw = self._data.get("project", {}).get("optional-dependencies", {})
        return {
            group: [x.strip() for x in entries if isinstance(x, str) and x.strip()]
            for group, entries in raw.items()
            if isinstance(entries, list)
        }

    def _read_feature_list(self, key: str) -> list[str]:
        """Read a feature list from [tool.splent.<key>], with legacy fallback for base key."""
        raw = self._data.get("tool", {}).get("splent", {}).get(key)
        if raw is None and key == "features":
            raw = (
                self._data
                .get("project", {})
                .get("optional-dependencies", {})
                .get("features", [])
            )
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValueError(
                f"[tool.splent.{key}] in {self._path} must be a list, got {type(raw).__name__}"
            )
        return [x.strip() for x in raw if isinstance(x, str) and x.strip()]

    @property
    def features(self) -> list[str]:
        """Base feature entries from ``[tool.splent.features]`` (always active)."""
        return self._read_feature_list("features")

    @property
    def features_dev(self) -> list[str]:
        """Dev-only feature entries from ``[tool.splent.features_dev]``."""
        return self._read_feature_list("features_dev")

    @property
    def features_prod(self) -> list[str]:
        """Prod-only feature entries from ``[tool.splent.features_prod]``."""
        return self._read_feature_list("features_prod")

    def features_for_env(self, env: str | None = None) -> list[str]:
        """Return merged feature list: base + env-specific (deduplicated).

        Args:
            env: ``"dev"``, ``"prod"``, or ``None`` (base only).
        """
        base = list(self.features)
        if env:
            seen = set(base)
            for f in self._read_feature_list(f"features_{env}"):
                if f not in seen:
                    base.append(f)
                    seen.add(f)
        return base

    # ── [tool.splent] ─────────────────────────────────────────────────────

    @property
    def splent_config(self) -> dict:
        """Full contents of [tool.splent]."""
        return self._data.get("tool", {}).get("splent", {})

    @property
    def uvl_config(self) -> dict:
        """Contents of [tool.splent.uvl] (mirror, doi, file, …)."""
        return self.splent_config.get("uvl", {})

    # ── helpers ───────────────────────────────────────────────────────────

    @property
    def path(self) -> str:
        """Absolute path to the pyproject.toml file."""
        return self._path

    def __repr__(self) -> str:
        return f"PyprojectReader({self._path!r})"
