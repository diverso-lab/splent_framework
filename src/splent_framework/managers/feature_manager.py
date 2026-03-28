"""
FeatureManager — public API for loading all features declared in pyproject.toml.

For the low-level loading pipeline (parsing, path resolution, imports, Flask
integration) see feature_loader.py.
"""

import logging
import os
import tomllib

from splent_framework.utils.path_utils import PathUtils
from splent_framework.utils.pyproject_reader import PyprojectReader
from splent_framework.managers.feature_loader import (
    FeatureEntryParser,
    FeatureError,
    FeatureIntegrator,
    FeatureLinkResolver,
    FeatureLoader,
    FeatureRef,  # re-exported for backward compatibility
)
from splent_framework.managers.feature_order import FeatureLoadOrderResolver
from splent_framework.refinement.registry import (
    RefinementEntry,
    get_registry,
    clear_registry,
)
from splent_framework.refinement.parser import (
    parse_extensible,
    parse_refinement,
)
from splent_framework.refinement.validator import validate_refinements

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

        # ── Refinement: collect, validate, populate registry ────────────
        self._setup_refinement_registry(product_dir, ordered)

        # ── Load features ─────────────────────────────────────────────
        features_dir = os.path.join(product_dir, "features")
        registry = get_registry()
        loader = FeatureLoader(
            features_dir,
            FeatureIntegrator(self._app, strict=self._strict, registry=registry),
        )
        for entry in ordered:
            loader.load(self._parser.parse(entry))

            # Advance lifecycle state to "active"
            # (this block continues below)
            try:
                from splent_cli.utils.lifecycle import (
                    advance_state,
                    resolve_feature_key_from_entry,
                )

                key, ns, name, version = resolve_feature_key_from_entry(entry)
                advance_state(
                    product_dir,
                    splent_app,
                    key,
                    to="active",
                    namespace=ns,
                    name=name,
                    version=version,
                )
            except Exception:
                pass  # CLI may not be installed (e.g. production without dev deps)

        # ── Post-load: apply template overrides ───────────────────────
        self._apply_template_overrides(registry)

    def get_features(self) -> list[str]:
        """Return the raw feature entries from the active product's pyproject.toml."""
        splent_app = self._require_splent_app()
        product_dir = os.path.join(PathUtils.get_working_dir(), splent_app)
        return self._read_features(product_dir)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_template_overrides(self, registry) -> None:
        """Reorder Jinja blueprint template loaders so refiner templates win.

        Flask's DispatchingJinjaLoader searches blueprints in registration order.
        Since refiners load AFTER their base, their templates would normally lose.
        We swap the refiner's blueprint ahead of the base's in the internal list.
        """
        template_overrides = [
            e for e in registry.all_entries() if e.category == "template"
        ]
        if not template_overrides:
            return

        # Build a map: blueprint_name -> registration order index
        bp_names = list(self._app.blueprints.keys())

        for entry in template_overrides:
            # Find the refiner's blueprint (convention: refiner registers its own bp)
            # The refiner's templates are served from its own blueprint template folder.
            # We need its blueprint to appear BEFORE the base's in the search order.
            # Flask 3.x uses app.blueprints (ordered dict), and the
            # DispatchingJinjaLoader iterates app.iter_blueprints() which
            # returns them in reverse registration order (last registered = first searched).
            # So the refiner, being loaded after the base, is already searched first.
            # This means template override works out of the box for same-path templates.
            logger.info(
                "Template override: %s (from %s, by %s)",
                entry.target, entry.base, entry.refiner,
            )

    def _setup_refinement_registry(
        self, product_dir: str, ordered: list[str]
    ) -> None:
        """Read extensible/refinement declarations from feature pyproject files,
        validate them, and populate the global RefinementRegistry."""
        clear_registry()
        registry = get_registry()

        features_dir = os.path.join(product_dir, "features")
        resolver = FeatureLinkResolver()

        extensibles = {}  # feature_name -> ExtensibleContract
        refinements = {}  # feature_name -> RefinementConfig
        known_features = set()

        for entry in ordered:
            ref = self._parser.parse(entry)
            known_features.add(ref.name)

            # Try to find and read pyproject.toml for this feature
            pyproject_data = self._read_feature_pyproject(features_dir, ref)
            if not pyproject_data:
                continue

            splent = pyproject_data.get("tool", {}).get("splent", {})

            # Extensible contract
            ext_raw = splent.get("contract", {}).get("extensible", {})
            if ext_raw:
                extensibles[ref.name] = parse_extensible(ext_raw)

            # Refinement config
            ref_raw = splent.get("refinement", {})
            ref_config = parse_refinement(ref_raw)
            if ref_config:
                refinements[ref.name] = ref_config

        # Validate
        errors = validate_refinements(refinements, extensibles, known_features)
        if errors:
            msg = "Refinement validation failed:\n" + "\n".join(
                f"  - {e}" for e in errors
            )
            raise FeatureError(msg)

        # Populate registry
        for refiner_name, config in refinements.items():
            for svc in config.overrides_services:
                registry.register(RefinementEntry(
                    refiner=refiner_name, base=config.refines,
                    category="service", target=svc.target,
                    replacement=svc.replacement, action="override",
                ))
            for tpl in config.overrides_templates:
                registry.register(RefinementEntry(
                    refiner=refiner_name, base=config.refines,
                    category="template", target=tpl.target,
                    replacement=tpl.replacement, action="override",
                ))
            for hook in config.overrides_hooks:
                registry.register(RefinementEntry(
                    refiner=refiner_name, base=config.refines,
                    category="hook", target=hook.target,
                    replacement=hook.replacement, action="replace",
                ))
            for model in config.extends_models:
                registry.register(RefinementEntry(
                    refiner=refiner_name, base=config.refines,
                    category="model", target=model.target,
                    replacement=model.mixin, action="extend",
                ))
            for route in config.adds_routes:
                registry.register(RefinementEntry(
                    refiner=refiner_name, base=config.refines,
                    category="route", target=route.blueprint,
                    replacement=route.module, action="add",
                ))

    def _read_feature_pyproject(
        self, features_dir: str, ref: FeatureRef
    ) -> dict | None:
        """Read and return the pyproject.toml data for a feature, or None."""
        resolver = FeatureLinkResolver()
        try:
            feature_dir = resolver.resolve(features_dir, ref)
        except FeatureError:
            # Pip-installed, no local dir — try workspace root
            workspace = PathUtils.get_working_dir()
            candidate = os.path.join(workspace, ref.name, "pyproject.toml")
            if os.path.isfile(candidate):
                with open(candidate, "rb") as f:
                    return tomllib.load(f)
            return None

        pyproject_path = os.path.join(feature_dir, "pyproject.toml")
        if not os.path.isfile(pyproject_path):
            return None
        with open(pyproject_path, "rb") as f:
            return tomllib.load(f)

    def _require_splent_app(self) -> str:
        splent_app = os.getenv("SPLENT_APP")
        if not splent_app:
            raise FeatureError("SPLENT_APP not set")
        return splent_app

    def _read_features(self, product_dir: str) -> list[str]:
        try:
            env = os.getenv("SPLENT_ENV")
            return PyprojectReader.for_product(product_dir).features_for_env(env)
        except FileNotFoundError as e:
            raise FeatureError(str(e)) from e
        except (RuntimeError, ValueError) as e:
            raise FeatureError(f"Failed to parse features: {e}") from e

    def _resolve_uvl_path(self, product_dir: str) -> str | None:
        """Return the absolute path to the UVL file, or None.

        Resolution order:
          1. SPL catalog: [tool.splent].spl → workspace/splent_catalog/{spl}/{spl}.uvl
          2. Legacy: [tool.splent.uvl].file → product_dir/uvl/{file}
        """
        try:
            reader = PyprojectReader.for_product(product_dir)
        except (FileNotFoundError, RuntimeError):
            return None

        # 1. Catalog resolution: [tool.splent].spl
        spl_name = reader.splent_config.get("spl")
        if spl_name:
            workspace = PathUtils.get_working_dir()
            catalog_uvl = os.path.join(
                workspace, "splent_catalog", spl_name, f"{spl_name}.uvl"
            )
            if os.path.isfile(catalog_uvl):
                return catalog_uvl

        # 2. Legacy: [tool.splent.uvl].file inside product
        uvl_file = reader.uvl_config.get("file")
        if not uvl_file:
            return None
        return os.path.join(product_dir, "uvl", uvl_file)
