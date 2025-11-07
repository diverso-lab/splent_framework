import glob
import importlib
import os
import sys
from splent_cli.utils.path_utils import PathUtils


def get_namespaces():
    base_cache_dir = os.path.join(PathUtils.get_working_dir(), ".splent_cache", "features")

    if not os.path.exists(base_cache_dir):
        print(f"⚠️  No feature cache found at {base_cache_dir}")
        return

    # 1️⃣ Detect all orgs (namespace roots)
    orgs = [d for d in os.listdir(base_cache_dir) if os.path.isdir(os.path.join(base_cache_dir, d))]

    if not orgs:
        print("⚠️  No org namespaces found under .splent_cache/features/")
        return

    for org in orgs:
        namespace_dir = os.path.join(base_cache_dir, org)
        init_file = os.path.join(namespace_dir, "__init__.py")

        # Ensure namespace package exists
        os.makedirs(namespace_dir, exist_ok=True)
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write(f"# {org} namespace package\n")
            print(f"🪄 Created missing namespace __init__.py for '{org}'")

    # 2️⃣ Add every feature src directory to sys.path
    for src in glob.glob(os.path.join(base_cache_dir, "*", "*", "src")):
        if src not in sys.path:
            sys.path.insert(0, src)

    # 3️⃣ Register all org namespaces
    importlib.invalidate_caches()
    for org in orgs:
        try:
            importlib.import_module(org)
        except Exception as e:
            print(f"❌ Failed to import namespace '{org}': {e}")
