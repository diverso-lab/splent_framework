import os
import importlib
import tomllib
from flask import Blueprint
from splent_cli.utils.path_utils import PathUtils


class FeatureManager:
    _already_registered = False

    def __init__(self, app):
        self.app = app

    def _load_features(self):
        pyproject_path = os.path.join(PathUtils.get_working_dir(), "splent_app", "pyproject.toml")

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

    def register_features(self):
        if FeatureManager._already_registered:
            print("⚠️ Features already registered. Skipping duplicate call.")
            return

        FeatureManager._already_registered = True

        for feature_pkg in self._load_features():

            try:
                try:
                    importlib.import_module(f"{feature_pkg}.routes")
                except ModuleNotFoundError:
                    print(f"⚠️  {feature_pkg}.routes not found, omitting...")
                    continue

                module = importlib.import_module(feature_pkg)

                for attr in dir(module):
                    obj = getattr(module, attr)
                    if isinstance(obj, Blueprint):
                        if obj.name not in self.app.blueprints:
                            self.app.register_blueprint(obj)

            except Exception as e:
                print(f"❌ Error registring '{feature_pkg}': {type(e).__name__} -> {e}")

    def get_features(self):
        """
        Returns a tuple: (loaded_features, ignored_features)
        """
        all_features = self._load_features()
        ignored_features = []

        # Read .featureignore if exists
        featureignore_path = os.path.join(PathUtils.get_app_base_dir(), ".featureignore")
        if os.path.exists(featureignore_path):
            with open(featureignore_path) as f:
                ignored_features = [line.strip() for line in f if line.strip()]

        # Features loaded are all but ignored
        loaded_features = [f for f in all_features if f not in ignored_features]

        return loaded_features, ignored_features
