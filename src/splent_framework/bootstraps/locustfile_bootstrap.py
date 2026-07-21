"""Default Locust entry point: load every feature's locustfile at once.

Locust is pointed at this module when no ``-f`` names a specific file. It
discovers the locustfiles a product ships, imports them, and re-exports the
``HttpUser`` subclasses it finds so Locust can offer them all.

Discovery covers the layouts SPLENT products actually use:

* ``app/features/<feature>/tests/locustfile.py`` — a product that keeps its
  features inside the application package.
* ``features/<namespace>/<feature>/**/tests/load/locustfile.py`` — a product
  composed from installed feature packages. These entries are symlinks into
  the workspace or the feature cache, so discovery follows symlinks.

Set ``SPLENT_LOCUSTFILES`` to override discovery entirely: a comma-separated
list of glob patterns, relative to ``WORKING_DIR`` unless absolute. Use it when
a product keeps its load tests somewhere else.
"""

import glob
import importlib.util
import inspect
import logging
import os

from dotenv import load_dotenv
from locust import HttpUser

logger = logging.getLogger(__name__)

# Relative to WORKING_DIR. Ordered from cheapest to widest.
DEFAULT_PATTERNS = (
    "app/features/*/tests/locustfile.py",
    "features/*/*/tests/load/locustfile.py",
    "features/*/*/tests/locustfile.py",
    "features/*/*/src/*/*/tests/load/locustfile.py",
)

# Never descend into these while following symlinked feature directories.
PRUNED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".splent_cache",
        "dist",
        "build",
    }
)


def _configured_patterns() -> list[str] | None:
    raw = os.getenv("SPLENT_LOCUSTFILES", "").strip()
    if not raw:
        return None
    return [p.strip() for p in raw.split(",") if p.strip()]


def _walk_for_locustfiles(root: str) -> list[str]:
    """Find locustfile.py under root, following symlinks.

    glob's ``**`` does not descend into symlinked directories, and a composed
    product links every feature in, so the recursive search is done by hand.
    """
    found = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        dirnames[:] = [d for d in dirnames if d not in PRUNED_DIRS]
        if "locustfile.py" in filenames:
            found.append(os.path.join(dirpath, "locustfile.py"))
    return found


def discover_locustfiles() -> list[str]:
    """Return the locustfile paths for this product, deduplicated and sorted."""
    working_dir = os.getenv("WORKING_DIR", "")

    patterns = _configured_patterns()
    if patterns is not None:
        logger.debug("SPLENT_LOCUSTFILES set, using %s", patterns)
    else:
        patterns = list(DEFAULT_PATTERNS)

    paths: set[str] = set()
    for pattern in patterns:
        absolute = (
            pattern if os.path.isabs(pattern) else os.path.join(working_dir, pattern)
        )
        paths.update(glob.glob(absolute))

    # A composed product links its features in, and the depth of the locustfile
    # inside each one varies with how the feature was installed, so walk them.
    features_root = os.path.join(working_dir, "features")
    if _configured_patterns() is None and os.path.isdir(features_root):
        paths.update(_walk_for_locustfiles(features_root))

    resolved = sorted({os.path.realpath(p) for p in paths})
    logger.debug("Discovered locustfiles: %s", resolved)
    return resolved


def _module_name_for(path: str) -> str:
    """A name unique per feature, so two locustfiles cannot shadow each other.

    Walks up past the test directories, so both
    ``<feature>/tests/locustfile.py`` and ``<feature>/tests/load/locustfile.py``
    resolve to the feature's own name.
    """
    parts = os.path.dirname(path).split(os.sep)
    while parts and parts[-1] in ("load", "tests", "test", "src"):
        parts.pop()
    name = parts[-1] if parts else "feature"
    return f"splent_locustfile_{name}"


def load_locustfiles():
    load_dotenv()

    locustfile_paths = discover_locustfiles()
    found_user_classes = []

    for path in locustfile_paths:
        logger.debug("Loading locustfile: %s", path)
        spec = importlib.util.spec_from_file_location(_module_name_for(path), path)
        locustfile = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(locustfile)
        except Exception:
            logger.exception("Skipping locustfile that failed to import: %s", path)
            continue

        for name, obj in vars(locustfile).items():
            if (
                inspect.isclass(obj)
                and issubclass(obj, HttpUser)
                and obj is not HttpUser
            ):
                unique_name = f"{name}_{_module_name_for(path)}"
                globals()[unique_name] = obj
                found_user_classes.append((unique_name, obj))
                logger.debug("Loaded user class: %s", unique_name)

    if not found_user_classes:
        raise ValueError(
            "No User class found. Looked for locustfiles under "
            f"{os.getenv('WORKING_DIR', '') or '.'} using patterns "
            f"{_configured_patterns() or list(DEFAULT_PATTERNS)}. "
            "Set SPLENT_LOCUSTFILES to a comma-separated list of glob patterns "
            "if this product keeps them somewhere else."
        )

    return found_user_classes


found_user_classes = load_locustfiles()
logger.info("Total user classes loaded: %d", len(found_user_classes))
