"""
Service locator for SPLENT features.

Provides a registry on `app.splent_services` where features register their
services by name. Refinement features can override services by writing to
the same key.

Usage in a base feature::

    from splent_framework.services.service_locator import register_service

    def init_feature(app):
        register_service(app, "AuthenticationService", AuthenticationService)

Usage in a refinement feature::

    from splent_framework.services.service_locator import register_service

    def init_feature(app):
        register_service(app, "AuthenticationService", AuthenticationService2FA)

Usage from routes (consumers)::

    from splent_framework.services.service_locator import get_service_class

    @bp.route("/login")
    def login():
        svc_cls = get_service_class(current_app, "AuthenticationService")
        svc = svc_cls()
        ...
"""

from flask import Flask


def _ensure_registry(app: Flask) -> dict[str, type]:
    if not hasattr(app, "splent_services"):
        app.splent_services = {}
    return app.splent_services


def register_service(app: Flask, name: str, cls: type) -> None:
    """Register a service class. Later calls override earlier ones."""
    registry = _ensure_registry(app)
    registry[name] = cls


def get_service_class(app: Flask, name: str) -> type:
    """Return the registered service class (possibly overridden by a refiner)."""
    registry = _ensure_registry(app)
    if name not in registry:
        raise KeyError(
            f"Service '{name}' not registered. "
            "Use register_service() in init_feature()."
        )
    return registry[name]


def get_all_services(app: Flask) -> dict[str, type]:
    """Return the full service registry (read-only snapshot)."""
    return dict(_ensure_registry(app))
