import logging
import os

from splent_framework.utils.pyproject_reader import PyprojectReader

logger = logging.getLogger(__name__)


def get_features_from_pyproject(env: str | None = None) -> list[str]:
    """
    Return the merged features list (base + env-specific) from the active
    product's pyproject.toml.

    Args:
        env: ``"dev"``, ``"prod"``, or ``None``. When None, reads ``SPLENT_ENV``.

    Returns [] if pyproject.toml does not exist.
    Raises RuntimeError if the TOML is malformed.
    """
    if env is None:
        env = os.getenv("SPLENT_ENV")
    try:
        return PyprojectReader.for_active_app().features_for_env(env)
    except FileNotFoundError:
        return []
