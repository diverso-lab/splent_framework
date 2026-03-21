import os
import tomllib
from splent_framework.utils.path_utils import PathUtils


def get_features_from_pyproject() -> list[str]:
    """
    Return the features list from [project.optional-dependencies].features
    in the active product's pyproject.toml.
    """
    pyproject_path = os.path.join(PathUtils.get_app_base_dir(), "pyproject.toml")
    if not os.path.exists(pyproject_path):
        return []
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["optional-dependencies"].get("features", [])
    except Exception:
        return []
