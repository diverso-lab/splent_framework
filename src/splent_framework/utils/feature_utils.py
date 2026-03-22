import logging

from splent_framework.utils.pyproject_reader import PyprojectReader

logger = logging.getLogger(__name__)


def get_features_from_pyproject() -> list[str]:
    """
    Return the features list from [project.optional-dependencies].features
    in the active product's pyproject.toml.

    Returns [] if pyproject.toml does not exist.
    Raises RuntimeError if the TOML is malformed.
    """
    try:
        return PyprojectReader.for_active_app().features
    except FileNotFoundError:
        return []
