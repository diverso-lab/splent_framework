"""
SPLENT Refinement API.

High-level helpers for refinement features. Use these in your
``init_feature(app)`` instead of calling the lower-level internals directly.

Usage::

    from splent_framework.refinement import refine_model, refine_service

    from .models import NotesTagsMixin
    from .services import NotesServiceWithTags

    def init_feature(app):
        refine_model("Notes", NotesTagsMixin)
        refine_service(app, "NotesService", NotesServiceWithTags)
"""

from splent_framework.refinement.model_extender import apply_model_mixin
from splent_framework.services.service_locator import (
    get_service_class,
    register_service,
)


def refine_model(model_name: str, mixin_cls: type) -> bool:
    """Extend an existing model with a mixin.

    Injects columns and methods from ``mixin_cls`` into the model
    registered under ``model_name`` in SQLAlchemy's mapper registry.

    Parameters
    ----------
    model_name : str
        Name of the base model class (e.g. ``"Notes"``).
    mixin_cls : type
        Mixin class containing ``db.Column`` attributes and/or methods.

    Returns
    -------
    bool
        True if the mixin was applied successfully.
    """
    return apply_model_mixin(model_name, mixin_cls)


def refine_service(app, service_name: str, replacement_cls: type) -> None:
    """Override a registered service with a replacement class.

    Automatically resolves the base service, sets ``replacement_cls``
    to inherit from it, and registers the replacement under the same name.

    Parameters
    ----------
    app : Flask
        The Flask application instance.
    service_name : str
        Name of the service to override (e.g. ``"NotesService"``).
    replacement_cls : type
        Replacement class. Will inherit from the base service at runtime.
    """
    base_cls = get_service_class(app, service_name)

    # Create a new class that inherits from the base and mixes in the
    # replacement's methods. This avoids __bases__ assignment errors
    # that occur when base classes have incompatible memory layouts.
    merged = type(
        replacement_cls.__name__,
        (base_cls,),
        {k: v for k, v in vars(replacement_cls).items() if not k.startswith("__")},
    )
    register_service(app, service_name, merged)
