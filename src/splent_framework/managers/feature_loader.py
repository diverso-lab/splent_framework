"""
Feature loading infrastructure for SPLENT.

Each class has a single responsibility (SRP). FeatureLoader composes them via
constructor injection (DIP), so each collaborator can be swapped or mocked.

Classes:
    FeatureError            — domain exception
    FeatureRef              — immutable value object for a feature reference
    FeatureEntryParser      — parses "org/name@version" strings → FeatureRef
    FeatureLinkResolver     — locates the feature directory on the filesystem
    FeatureStructureValidator — validates the internal layout of a feature dir
    FeatureImporter         — handles all importlib operations
    FeatureIntegrator       — runs Flask integration hooks (config, init, blueprints)
    FeatureLoader           — orchestrates the full pipeline for one feature
"""

import glob
import importlib
import logging
import os
import sys
import types
from dataclasses import dataclass

from flask import Blueprint

logger = logging.getLogger(__name__)

# Conventional submodules attempted on every feature package
FEATURE_SUBMODULES = ("routes", "models", "hooks")


# ---------------------------------------------------------------------------
# Domain exception
# ---------------------------------------------------------------------------


class FeatureError(RuntimeError):
    """Raised when any stage of feature loading fails."""


# ---------------------------------------------------------------------------
# Value object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureRef:
    """Immutable reference to a feature package."""

    org: str  # original org slug        (e.g. "splent-io")
    org_safe: str  # Python-safe org namespace (e.g. "splent_io")
    name: str  # feature package name      (e.g. "splent_feature_auth")
    version: str | None  # declared version       (e.g. "v1.0.0"), or None if absent

    def import_name(self) -> str:
        """Fully qualified Python import name, e.g. 'splent_io.splent_feature_auth'."""
        return f"{self.org_safe}.{self.name}"


# ---------------------------------------------------------------------------
# SRP: parse raw entry strings
# ---------------------------------------------------------------------------


class FeatureEntryParser:
    """Parse raw feature entry strings into FeatureRef instances.

    Accepted formats::

        org/name@vX.Y.Z  |  name@vX.Y.Z  |  org/name  |  name
    """

    DEFAULT_ORG = "splent-io"

    def parse(self, entry: str) -> FeatureRef:
        """Return a FeatureRef for the given entry string.

        Raises FeatureError if the entry has an empty name.
        """
        if "/" in entry:
            org, rest = entry.split("/", 1)
        else:
            org, rest = self.DEFAULT_ORG, entry

        name, sep, version = rest.partition("@")
        version = version if sep else None
        if not name:
            raise FeatureError(f"Invalid feature entry (empty name): {entry!r}")

        return FeatureRef(
            org=org,
            org_safe=org.replace("-", "_"),
            name=name,
            version=version,
        )


# ---------------------------------------------------------------------------
# SRP: locate the feature directory on the filesystem
# ---------------------------------------------------------------------------


class FeatureLinkResolver:
    """Locate the symlink (or plain directory) for a feature on the filesystem.

    Falls back to the first installed version when the exact version is absent.
    """

    def resolve(self, features_dir: str, ref: FeatureRef) -> str:
        """Return the resolved path to the feature directory.

        Uses os.path.abspath instead of os.path.realpath so that relative
        symlinks resolve within the current filesystem (e.g. inside a Docker
        container) rather than expanding to the host absolute path.

        Raises FeatureError if no matching path exists.
        """
        link_path = self._expected_path(features_dir, ref)
        if not os.path.exists(link_path):
            link_path = self._fallback_path(features_dir, ref, link_path)
        return os.path.abspath(link_path)

    # ------------------------------------------------------------------

    def _expected_path(self, features_dir: str, ref: FeatureRef) -> str:
        if ref.version:
            return os.path.join(features_dir, ref.org_safe, f"{ref.name}@{ref.version}")
        return os.path.join(features_dir, ref.org_safe, ref.name)

    def _fallback_path(self, features_dir: str, ref: FeatureRef, expected: str) -> str:
        candidates = sorted(
            glob.glob(os.path.join(features_dir, ref.org_safe, f"{ref.name}@*"))
        )
        if candidates:
            logger.warning(
                "Using available version for %s: %s",
                ref.name,
                os.path.basename(candidates[0]),
            )
            return candidates[0]
        raise FeatureError(f"Feature link not found: {expected}")


# ---------------------------------------------------------------------------
# SRP: validate internal directory structure
# ---------------------------------------------------------------------------


class FeatureStructureValidator:
    """Validate that a resolved feature directory has the expected layout.

    Expected::

        <feature_dir>/
        └── src/
            └── <org_safe>/
                └── <name>/
    """

    def validate(self, feature_dir: str, ref: FeatureRef) -> tuple[str, str, str]:
        """Return (src_root, org_ns_dir, pkg_dir).

        Raises FeatureError if any expected directory is missing.
        """
        src_root = os.path.join(feature_dir, "src")
        org_ns_dir = os.path.join(src_root, ref.org_safe)
        pkg_dir = os.path.join(org_ns_dir, ref.name)

        if not os.path.isdir(src_root):
            raise FeatureError(f"Missing src/ in feature: {feature_dir}")
        if not os.path.isdir(org_ns_dir):
            raise FeatureError(f"Missing namespace folder: {org_ns_dir}")
        if not os.path.isdir(pkg_dir):
            raise FeatureError(f"Feature package not found: {pkg_dir}")

        return src_root, org_ns_dir, pkg_dir


# ---------------------------------------------------------------------------
# SRP: importlib operations
# ---------------------------------------------------------------------------


class FeatureImporter:
    """Handle all importlib operations for a feature package."""

    def add_to_syspath(self, src_root: str) -> None:
        """Insert src_root into sys.path so 'import org_safe.feature_name' works."""
        if src_root not in sys.path:
            sys.path.insert(0, src_root)
            logger.debug("Source path added: %s", src_root)

    def import_package(self, import_name: str) -> types.ModuleType:
        """Import and return the feature root package.

        Raises FeatureError on any import failure.
        """
        try:
            return importlib.import_module(import_name)
        except Exception as e:
            raise FeatureError(f"Cannot import {import_name}: {e}") from e

    def import_submodules(self, import_name: str) -> None:
        """Import conventional submodules (routes, models, hooks).

        Silently ignores missing modules; re-raises any other import error.
        """
        for sub in FEATURE_SUBMODULES:
            self._try_import(import_name, sub)

    # ------------------------------------------------------------------

    def _try_import(self, base: str, sub: str) -> None:
        try:
            importlib.import_module(f"{base}.{sub}")
        except ModuleNotFoundError:
            pass
        except Exception as e:
            raise FeatureError(f"Cannot import {base}.{sub}: {e}") from e


# ---------------------------------------------------------------------------
# SRP: Flask integration hooks
# ---------------------------------------------------------------------------


class FeatureIntegrator:
    """Run Flask integration hooks for a loaded feature module.

    Responsibilities (in order):
      1. Inject feature configuration via ``<feature>.config.inject_config(app)``
      2. Call ``<feature>.init_feature(app)`` if present
      3. Register all Flask Blueprints found in the feature modules
    """

    def __init__(self, app, strict: bool = True) -> None:
        self._app = app
        self._strict = strict

    def integrate(self, module, import_name: str) -> None:
        """Run all integration steps for the given feature module."""
        self._inject_config(import_name)
        self._call_init(module, import_name)
        self._register_blueprints(module, import_name)

    # ------------------------------------------------------------------

    def _inject_config(self, import_name: str) -> None:
        try:
            config_mod = importlib.import_module(f"{import_name}.config")
        except ModuleNotFoundError:
            if self._strict:
                raise FeatureError(f"{import_name}.config not found")
            return
        except Exception as e:
            raise FeatureError(f"Error importing {import_name}.config: {e}") from e

        if hasattr(config_mod, "inject_config"):
            try:
                config_mod.inject_config(self._app)
            except Exception as e:
                raise FeatureError(
                    f"Error in {import_name}.config.inject_config: {e}"
                ) from e
        elif self._strict:
            raise FeatureError(f"{import_name}.config lacks inject_config(app)")

    def _call_init(self, module, import_name: str) -> None:
        if hasattr(module, "init_feature"):
            try:
                module.init_feature(self._app)
            except Exception as e:
                raise FeatureError(
                    f"Error in {import_name}.init_feature(app): {e}"
                ) from e
        elif self._strict:
            raise FeatureError(f"{import_name} lacks init_feature(app)")

    def _register_blueprints(self, module, import_name: str) -> None:
        candidates = self._collect_candidate_modules(module, import_name)
        registered = sum(self._register_from_module(mod) for mod in candidates)

        if registered == 0:
            logger.warning("No blueprints registered for %s", import_name)
            if self._strict:
                raise FeatureError(f"No blueprints found in {import_name}")

    def _collect_candidate_modules(
        self, module: types.ModuleType, import_name: str
    ) -> list[types.ModuleType]:
        """Return the feature root module plus any already-imported submodules."""
        return [module] + [
            sys.modules[f"{import_name}.{sub}"]
            for sub in FEATURE_SUBMODULES
            if f"{import_name}.{sub}" in sys.modules
        ]

    def _register_from_module(self, mod: types.ModuleType) -> int:
        """Register all Blueprint instances found in *mod*. Returns count registered."""
        registered = 0
        for attr in dir(mod):
            try:
                obj = getattr(mod, attr)
            except Exception as e:
                logger.warning("Error accessing attribute '%s': %s", attr, e)
                continue

            if not isinstance(obj, Blueprint):
                continue

            if obj.name in self._app.blueprints:
                if self._strict:
                    raise FeatureError(
                        f"Blueprint name collision: {obj.name} in {mod.__name__}"
                    )
                continue

            try:
                self._app.register_blueprint(obj)
                registered += 1
            except Exception as e:
                logger.error("Failed to register blueprint '%s': %s", obj.name, e)

        return registered


# ---------------------------------------------------------------------------
# Orchestrator: load a single feature (DIP — collaborators injected)
# ---------------------------------------------------------------------------


class FeatureLoader:
    """Orchestrate the full loading pipeline for a single FeatureRef.

    All collaborators are injected so each can be replaced or mocked in tests.
    Default instances are created automatically when not provided.
    """

    def __init__(
        self,
        features_dir: str,
        integrator: FeatureIntegrator,
        *,
        resolver: FeatureLinkResolver | None = None,
        validator: FeatureStructureValidator | None = None,
        importer: FeatureImporter | None = None,
    ) -> None:
        self._features_dir = features_dir
        self._integrator = integrator
        self._resolver = resolver or FeatureLinkResolver()
        self._validator = validator or FeatureStructureValidator()
        self._importer = importer or FeatureImporter()

    def load(self, ref: FeatureRef) -> None:
        """Fully load and integrate one feature.

        In development, features live on disk (symlinks → cache or workspace
        root) so we resolve, validate, and add src/ to sys.path.

        In production, features are pip-installed from PyPI — there are no
        symlinks.  When the resolver cannot find a directory we fall back to
        a direct import, which works because pip already placed the package
        in site-packages.
        """
        try:
            feature_dir = self._resolver.resolve(self._features_dir, ref)
            src_root, _, _ = self._validator.validate(feature_dir, ref)
            self._importer.add_to_syspath(src_root)
        except FeatureError:
            # No local directory found — the feature must be pip-installed.
            logger.debug(
                "No local directory for %s — assuming pip-installed package.",
                ref.import_name(),
            )

        import_name = ref.import_name()
        module = self._importer.import_package(import_name)
        self._importer.import_submodules(import_name)

        self._integrator.integrate(module, import_name)
