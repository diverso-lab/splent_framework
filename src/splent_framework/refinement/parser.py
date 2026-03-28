"""
RefinementParser — reads extensible and refinement declarations from pyproject.toml.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExtensibleContract:
    """What a base feature declares as overridable/extendable."""

    services: list[str] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)
    routes: bool = False  # if True, other features can add routes to this blueprint


@dataclass
class RefinementOverride:
    target: str
    replacement: str = ""


@dataclass
class RefinementModelExtension:
    target: str  # base model name, e.g. "User"
    mixin: str  # mixin class name, e.g. "User2FAMixin"


@dataclass
class RefinementRouteAddition:
    blueprint: str  # base blueprint name, e.g. "auth"
    module: str  # module with routes, e.g. "routes_2fa"


@dataclass
class RefinementConfig:
    """What a refining feature declares about its overrides."""

    refines: str  # base feature name, e.g. "splent_feature_auth"
    overrides_services: list[RefinementOverride] = field(default_factory=list)
    overrides_templates: list[RefinementOverride] = field(default_factory=list)
    overrides_hooks: list[RefinementOverride] = field(default_factory=list)
    extends_models: list[RefinementModelExtension] = field(default_factory=list)
    adds_routes: list[RefinementRouteAddition] = field(default_factory=list)


def parse_extensible(raw: dict) -> ExtensibleContract:
    """Parse [tool.splent.contract.extensible] from pyproject.toml data."""
    if not raw:
        return ExtensibleContract()

    return ExtensibleContract(
        services=_list(raw.get("services")),
        templates=_list(raw.get("templates")),
        models=_list(raw.get("models")),
        hooks=_list(raw.get("hooks")),
        routes=bool(raw.get("routes", False)),
    )


def parse_refinement(raw: dict) -> RefinementConfig | None:
    """Parse [tool.splent.refinement] from pyproject.toml data.

    Returns None if the feature does not declare any refinement.
    """
    refines = raw.get("refines")
    if not refines:
        return None

    overrides = raw.get("overrides", {})
    extends = raw.get("extends", {})

    return RefinementConfig(
        refines=refines,
        overrides_services=[
            RefinementOverride(target=o["target"], replacement=o.get("replacement", ""))
            for o in _list_of_dicts(overrides.get("services"))
        ],
        overrides_templates=[
            RefinementOverride(target=o["target"], replacement=o.get("replacement", ""))
            for o in _list_of_dicts(overrides.get("templates"))
        ],
        overrides_hooks=[
            RefinementOverride(target=o["target"], replacement=o.get("replacement", ""))
            for o in _list_of_dicts(overrides.get("hooks"))
        ],
        extends_models=[
            RefinementModelExtension(target=o["target"], mixin=o["mixin"])
            for o in _list_of_dicts(extends.get("models"))
        ],
        adds_routes=[
            RefinementRouteAddition(blueprint=o["blueprint"], module=o["module"])
            for o in _list_of_dicts(extends.get("routes"))
        ],
    )


def _list(val) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    return []


def _list_of_dicts(val) -> list[dict]:
    if val is None:
        return []
    if isinstance(val, list):
        return [x for x in val if isinstance(x, dict)]
    return []
