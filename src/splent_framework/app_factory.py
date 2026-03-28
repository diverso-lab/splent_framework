"""
SPLENT App Factory — the canonical way to create a SPLENT product application.

Usage in a product's __init__.py::

    from splent_framework import create_splent_app

    def create_app(config_name="development"):
        return create_splent_app(__name__, config_name)

The factory initialises all framework subsystems in the correct order.
Products should not import individual managers — the factory handles it.
"""

import logging
import os

from flask import Flask

from splent_framework.managers.namespace_manager import NamespaceManager
from splent_framework.managers.config_manager import ConfigManager
from splent_framework.managers.migration_manager import MigrationManager
from splent_framework.managers.session_manager import SessionManager
from splent_framework.managers.logging_manager import LoggingManager
from splent_framework.managers.error_handler_manager import ErrorHandlerManager
from splent_framework.managers.jinja_manager import JinjaManager
from splent_framework.managers.feature_manager import FeatureManager

logger = logging.getLogger(__name__)

# Initialisation pipeline — order matters.
# Each step is a (label, callable) pair.  The callable receives (app, **kwargs).
_PIPELINE = [
    ("namespaces", lambda app, **kw: NamespaceManager.init_app(app)),
    ("config", lambda app, **kw: ConfigManager.init_app(app, kw.get("config_name", "development"))),
    ("database", lambda app, **kw: MigrationManager(app)),
    ("sessions", lambda app, **kw: SessionManager(app)),
    ("logging", lambda app, **kw: LoggingManager(app).setup_logging()),
    ("error_handlers", lambda app, **kw: ErrorHandlerManager(app).register_error_handlers()),
    ("jinja_context", lambda app, **kw: JinjaManager(app, kw.get("context", {}))),
    ("features", lambda app, **kw: FeatureManager(app, strict=kw.get("strict", False)).register_features()),
]


def create_splent_app(
    import_name: str,
    config_name: str = "development",
    *,
    strict: bool = False,
    extra_context: dict | None = None,
) -> Flask:
    """Create and fully initialise a SPLENT Flask application.

    Parameters
    ----------
    import_name : str
        The ``__name__`` of the calling product package.
    config_name : str
        Configuration profile: ``"development"``, ``"testing"``, or ``"production"``.
    strict : bool
        If True, missing features raise errors instead of warnings.
    extra_context : dict | None
        Additional Jinja context variables injected into every template.

    Returns
    -------
    Flask
        A fully configured Flask application with all features loaded.
    """
    app = Flask(import_name)

    context = {"SPLENT_APP": os.getenv("SPLENT_APP", "")}
    if extra_context:
        context.update(extra_context)

    kwargs = {
        "config_name": config_name,
        "context": context,
        "strict": strict,
    }

    for label, init_fn in _PIPELINE:
        try:
            init_fn(app, **kwargs)
            logger.debug("Initialised: %s", label)
        except Exception:
            logger.exception("Failed to initialise: %s", label)
            raise

    return app
