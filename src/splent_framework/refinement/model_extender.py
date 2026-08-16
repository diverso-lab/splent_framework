"""
Model extension via mixin injection.

Applies mixin classes to existing SQLAlchemy models, adding new columns
and methods without modifying the base feature's source code.
"""

import logging

from splent_framework.db import db

logger = logging.getLogger(__name__)


def apply_model_mixin(model_name: str, mixin_cls: type) -> bool:
    """Apply a mixin class to an existing SQLAlchemy model.

    Adds columns and methods from mixin_cls to the model class found
    in SQLAlchemy's mapper registry.

    Parameters
    ----------
    model_name : str
        Name of the model class (e.g. "User").
    mixin_cls : type
        Mixin class with db.Column attributes and/or methods.

    Returns
    -------
    bool
        True if the mixin was applied, False if model not found.
    """
    # Find the model class in SQLAlchemy's registry
    model_cls = _find_model(model_name)
    if model_cls is None:
        logger.warning(
            "Model '%s' not found in registry — cannot apply mixin.", model_name
        )
        return False

    applied = 0

    # Add columns from mixin
    for attr_name in dir(mixin_cls):
        if attr_name.startswith("_"):
            continue

        attr = getattr(mixin_cls, attr_name)

        # Column injection
        if isinstance(attr, db.Column):
            if hasattr(model_cls, attr_name):
                continue
            col = attr._copy() if hasattr(attr, "_copy") else attr.copy()
            col.name = col.name or attr_name
            # Assigning a Column to a mapped declarative class is what adds
            # it to the table AND to the mapper (DeclarativeMeta routes the
            # assignment through SQLAlchemy's _add_attribute). Appending it
            # to the table by hand as well attached the column twice, and a
            # column declared with index=True then registered its index
            # twice, which broke create_all with a duplicate key name.
            setattr(model_cls, attr_name, col)
            if col.table is None:
                # Not a declarative class: attach to the table explicitly.
                model_cls.__table__.append_column(col)
            applied += 1
            logger.info("Extended %s with column: %s", model_name, attr_name)

        # Method injection (non-column attributes)
        elif callable(attr) and not isinstance(attr, type):
            setattr(model_cls, attr_name, attr)
            applied += 1
            logger.info("Extended %s with method: %s", model_name, attr_name)

    if applied:
        logger.info(
            "Model %s extended with %d attribute(s) from %s",
            model_name,
            applied,
            mixin_cls.__name__,
        )

    return applied > 0


def _find_model(name: str) -> type | None:
    """Find a SQLAlchemy model class by name in the mapper registry."""
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        if cls.__name__ == name:
            return cls
    return None
