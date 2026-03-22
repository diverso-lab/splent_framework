"""
FeatureManager — public API for loading all features declared in pyproject.toml.

For the low-level loading pipeline (parsing, path resolution, imports, Flask
integration) see feature_loader.py.
"""

import logging
import os

from splent_framework.utils.path_utils import PathUtils
from splent_framework.utils.pyproject_reader import PyprojectReader
from splent_framework.managers.feature_loader import (
    FeatureEntryParser,
    FeatureError,
    FeatureIntegrator,
    FeatureLoader,
    FeatureRef,  # re-exported for backward compatibility
)
from splent_framework.managers.feature_order import FeatureLoadOrderResolver

__all__ = ["FeatureManager", "FeatureError", "FeatureRef"]

logger = logging.getLogger(__name__)


class FeatureManager:
    """
    Load and register all features declared in the active product's pyproject.toml.

    Load order is determined by the UVL constraints file: if the UVL declares
    'A => B' (A requires B), B is guaranteed to load before A.  When no UVL
    is available the order from pyproject.toml is preserved.

    Usage::

        FeatureManager(app, strict=False).register_features()
    """

    def __init__(self, app, *, strict: bool = True) -> None:
        self._app = app
        self._strict = strict
        self._registered = False
        self._parser = FeatureEntryParser()
        self._order_resolver = FeatureLoadOrderResolver(self._parser)

    def register_features(self) -> None:
        """Parse pyproject.toml, resolve load order via UVL, and load every feature."""
        if self._registered:
            return
        self._registered = True

        splent_app = self._require_splent_app()
        product_dir = os.path.join(PathUtils.get_working_dir(), splent_app)

        features_raw = self._read_features(product_dir)
        if not features_raw:
            logger.info("No features declared.")
            return

        uvl_path = self._resolve_uvl_path(product_dir)
        ordered = self._order_resolver.resolve(features_raw, uvl_path)

        features_dir = os.path.join(product_dir, "features")
        loader = FeatureLoader(
            features_dir,
            FeatureIntegrator(self._app, strict=self._strict),
        )
        for entry in ordered:
            loader.load(self._parser.parse(entry))

    def get_features(self) -> list[str]:
        """Return the raw feature entries from the active product's pyproject.toml."""
        splent_app = self._require_splent_app()
        product_dir = os.path.join(PathUtils.get_working_dir(), splent_app)
        return self._read_features(product_dir)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_splent_app(self) -> str:
        splent_app = os.getenv("SPLENT_APP")
        if not splent_app:
            raise FeatureError("SPLENT_APP not set")
        return splent_app

    def _read_features(self, product_dir: str) -> list[str]:
        try:
            return PyprojectReader.for_product(product_dir).features
        except FileNotFoundError as e:
            raise FeatureError(str(e)) from e
        except (RuntimeError, ValueError) as e:
            raise FeatureError(f"Failed to parse features: {e}") from e

    def _resolve_uvl_path(self, product_dir: str) -> str | None:
        """Return the absolute path to the product's UVL file, or None."""
        try:
            uvl_cfg = PyprojectReader.for_product(product_dir).uvl_config
        except (FileNotFoundError, RuntimeError):
            return None
        uvl_file = uvl_cfg.get("file")
        if not uvl_file:
            return None
        return os.path.join(product_dir, "uvl", uvl_file)
