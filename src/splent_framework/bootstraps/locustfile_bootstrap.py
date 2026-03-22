import os
import glob
import inspect
import importlib.util
import logging
from locust import HttpUser
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_locustfiles():
    load_dotenv()
    working_dir = os.getenv("WORKING_DIR", "")
    logger.debug("Working directory: %s", working_dir)

    module_dir = os.path.join(working_dir, "app", "modules")
    logger.debug("Module directory: %s", module_dir)

    locustfile_paths = glob.glob(
        os.path.join(module_dir, "*", "tests", "locustfile.py")
    )
    logger.debug("Found locustfiles: %s", locustfile_paths)

    found_user_classes = []

    for path in locustfile_paths:
        logger.debug("Loading locustfile: %s", path)
        module_name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(module_name, path)
        locustfile = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(locustfile)

        # Collect all classes that inherit from HttpUser
        for name, obj in vars(locustfile).items():
            if (
                inspect.isclass(obj)
                and issubclass(obj, HttpUser)
                and obj is not HttpUser
            ):
                unique_name = f"{name}_{os.path.basename(path).split('.')[0]}"
                globals()[unique_name] = obj  # Add to globals
                found_user_classes.append((unique_name, obj))
                logger.debug("Loaded user class: %s", unique_name)

    if not found_user_classes:
        raise ValueError("No User class found!")

    return found_user_classes


found_user_classes = load_locustfiles()
logger.info("Total user classes loaded: %d", len(found_user_classes))
