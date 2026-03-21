import os
import sys
import importlib
from dotenv import load_dotenv
from splent_framework.utils.path_utils import PathUtils

load_dotenv()


def get_create_app_in_testing_mode():
    """
    Import the active product's module and return create_app("testing").
    Used by splent_framework fixtures — no dependency on splent_cli required.
    """
    module_name = os.getenv("SPLENT_APP")
    if not module_name:
        raise RuntimeError("SPLENT_APP is not set.")

    dotenv_path = PathUtils.get_app_env_file()
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path, override=True)

    src_path = os.path.join(PathUtils.get_app_base_dir(), "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        raise RuntimeError(f"Failed to import module '{module_name}': {e}") from e

    if not hasattr(mod, "create_app"):
        raise RuntimeError(f"Module '{module_name}' does not define create_app().")

    return mod.create_app("testing")
