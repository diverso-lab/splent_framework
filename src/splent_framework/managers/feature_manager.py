import os
import sys
import importlib
import tomllib
from flask import Blueprint
from splent_cli.utils.path_utils import PathUtils


class FeatureManager:
    _already_registered = False

    def __init__(self, app):
        self.app = app

    # ------------------------------------------------------------
    # 1️⃣ Cargar lista de features desde el pyproject.toml
    # ------------------------------------------------------------
    def _load_features(self):
        splent_app = os.getenv("SPLENT_APP")
        pyproject_path = os.path.join(PathUtils.get_working_dir(), splent_app, "pyproject.toml")

        if not os.path.exists(pyproject_path):
            print(f"❌ pyproject.toml not found at {pyproject_path}")
            return []

        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            return data["project"]["optional-dependencies"].get("features", [])
        except Exception as e:
            print(f"❌ Failed to parse features from pyproject.toml: {e}")
            return []

    # ------------------------------------------------------------
    # 2️⃣ Registrar features dinámicamente
    # ------------------------------------------------------------
    def register_features(self):
        if FeatureManager._already_registered:
            return
        FeatureManager._already_registered = True

        if not hasattr(self.app, "context_processors"):
            self.app.context_processors = []

        splent_app = os.getenv("SPLENT_APP")
        features_dir = os.path.join(PathUtils.get_working_dir(), splent_app, "features")

        features = self._load_features()
        import_paths = {}

        # 🔹 PRIMER PASO: añadir todos los posibles paths de features al sys.path
        for feature_entry in features:
            name, _, version = feature_entry.partition("@")
            version = version or "v1.0.0"
            feature_path = os.path.join(features_dir, f"{name}@{version}")

            src_pkg_path = os.path.join(feature_path, "src", name)
            inner_pkg_path = os.path.join(feature_path, name)

            if os.path.exists(os.path.join(src_pkg_path, "__init__.py")):
                import_path = os.path.join(feature_path, "src")
            elif os.path.exists(os.path.join(inner_pkg_path, "__init__.py")):
                import_path = feature_path
            elif os.path.exists(os.path.join(feature_path, "__init__.py")):
                import_path = feature_path
            else:
                import_path = None

            if import_path:
                import_paths[name] = import_path
                if import_path not in sys.path:
                    sys.path.insert(0, import_path)
            else:
                print(f"⚠️ Could not locate package path for {name} in {feature_path}")

        # 🔹 SEGUNDO PASO: importar y registrar cada feature
        for feature_entry in features:
            name, _, version = feature_entry.partition("@")
            version = version or "v1.0.0"

            import_path = import_paths.get(name)
            if not import_path:
                print(f"⚠️ Skipping {name}@{version}, no valid import path found.")
                continue

            try:
                module = importlib.import_module(name)
            except ModuleNotFoundError:
                print(f"❌ Could not import {name} (expected path: {import_path})")
                continue
            except Exception as e:
                print(f"❌ Error importing {name}: {e}")
                continue

            # routes.py
            try:
                importlib.import_module(f"{name}.routes")
            except ModuleNotFoundError:
                pass
            except Exception as e:
                print(f"❌ Error in {name}.routes: {e}")

            # models.py
            try:
                importlib.import_module(f"{name}.models")
            except ModuleNotFoundError:
                pass
            except Exception as e:
                print(f"❌ Error in {name}.models: {e}")

            # config.py → inject_config()
            try:
                config_module = importlib.import_module(f"{name}.config")
                if hasattr(config_module, "inject_config"):
                    config_module.inject_config(self.app)
            except ModuleNotFoundError:
                pass
            except Exception as e:
                print(f"❌ Error in {name}.config: {e}")

            # init_feature()
            try:
                if hasattr(module, "init_feature") and callable(module.init_feature):
                    module.init_feature(self.app)
            except Exception as e:
                print(f"❌ Error in {name}.init_feature: {e}")

            # Blueprints
            try:
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if isinstance(obj, Blueprint):
                        if obj.name not in self.app.blueprints:
                            self.app.register_blueprint(obj)
            except Exception as e:
                print(f"❌ Error registering blueprint for {name}: {e}")

            # Context vars
            try:
                if hasattr(module, "inject_context_vars"):
                    fn = getattr(module, "inject_context_vars")
                    if callable(fn):
                        self.app.context_processors.append(fn)
            except Exception as e:
                print(f"⚠️ Error registering context vars from {name}: {e}")

            # hooks.py
            try:
                importlib.import_module(f"{name}.hooks")
            except ModuleNotFoundError:
                pass
            except Exception as e:
                print(f"⚠️ Error in {name}.hooks: {e}")

    # ------------------------------------------------------------
    # 3️⃣ Obtener lista de features y filtrarlas
    # ------------------------------------------------------------
    def get_features(self):
        all_features = self._load_features()
        ignored_features = []

        featureignore_path = os.path.join(PathUtils.get_app_base_dir(), ".featureignore")
        if os.path.exists(featureignore_path):
            with open(featureignore_path) as f:
                ignored_features = [line.strip() for line in f if line.strip()]

        loaded_features = [f for f in all_features if f not in ignored_features]
        return loaded_features, ignored_features
