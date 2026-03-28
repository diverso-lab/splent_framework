"""
RefinementValidator — validates that refinement overrides target extensible points.
"""

from __future__ import annotations

from splent_framework.refinement.parser import (
    ExtensibleContract,
    RefinementConfig,
)


def validate_refinements(
    refinements: dict[str, RefinementConfig],
    extensibles: dict[str, ExtensibleContract],
    known_features: set[str],
) -> list[str]:
    """Validate all refinement declarations against extensible contracts.

    Parameters
    ----------
    refinements : dict[str, RefinementConfig]
        Mapping of refiner feature name -> its refinement config.
    extensibles : dict[str, ExtensibleContract]
        Mapping of base feature name -> its extensible contract.
    known_features : set[str]
        Set of all feature names in the product.

    Returns
    -------
    list[str]
        List of error messages. Empty = all valid.
    """
    errors: list[str] = []
    # Track targets to detect duplicate overrides
    claimed: dict[tuple[str, str, str], str] = {}  # (base, category, target) -> refiner

    for refiner, config in refinements.items():
        base = config.refines

        # 1. Base feature must exist
        if base not in known_features:
            errors.append(
                f"{refiner}: refines '{base}' but it is not declared in the product."
            )
            continue

        ext = extensibles.get(base, ExtensibleContract())

        # 2. Service overrides
        for svc in config.overrides_services:
            key = (base, "service", svc.target)
            if svc.target not in ext.services:
                errors.append(
                    f"{refiner}: overrides service '{svc.target}' from {base}, "
                    f"but {base} does not declare it as extensible."
                )
            elif key in claimed:
                errors.append(
                    f"{refiner}: overrides service '{svc.target}' from {base}, "
                    f"but it is already overridden by {claimed[key]}."
                )
            else:
                claimed[key] = refiner

        # 3. Template overrides
        for tpl in config.overrides_templates:
            key = (base, "template", tpl.target)
            if tpl.target not in ext.templates:
                errors.append(
                    f"{refiner}: overrides template '{tpl.target}' from {base}, "
                    f"but {base} does not declare it as extensible."
                )
            elif key in claimed:
                errors.append(
                    f"{refiner}: overrides template '{tpl.target}' from {base}, "
                    f"but it is already overridden by {claimed[key]}."
                )
            else:
                claimed[key] = refiner

        # 4. Hook overrides
        for hook in config.overrides_hooks:
            key = (base, "hook", hook.target)
            if hook.target not in ext.hooks:
                errors.append(
                    f"{refiner}: overrides hook '{hook.target}' from {base}, "
                    f"but {base} does not declare it as extensible."
                )
            elif key in claimed:
                errors.append(
                    f"{refiner}: overrides hook '{hook.target}' from {base}, "
                    f"but it is already overridden by {claimed[key]}."
                )
            else:
                claimed[key] = refiner

        # 5. Model extensions
        for model in config.extends_models:
            key = (base, "model", model.target)
            if model.target not in ext.models:
                errors.append(
                    f"{refiner}: extends model '{model.target}' from {base}, "
                    f"but {base} does not declare it as extensible."
                )
            elif key in claimed:
                errors.append(
                    f"{refiner}: extends model '{model.target}' from {base}, "
                    f"but it is already extended by {claimed[key]}."
                )
            else:
                claimed[key] = refiner

        # 6. Route additions
        for route in config.adds_routes:
            if not ext.routes:
                errors.append(
                    f"{refiner}: adds routes to blueprint '{route.blueprint}' from {base}, "
                    f"but {base} does not declare routes as extensible."
                )

    return errors
