import os
import importlib
from flask import Blueprint
from splent_cli.utils.path_utils import PathUtils


class FeatureManager:
    _already_registered = False

    def __init__(self, app):
        self.app = app
        self.features_file = PathUtils.get_features_file()

    def _load_features(self):
        if not os.path.exists(self.features_file):
            return []
        with open(self.features_file) as f:
            return [line.strip() for line in f if line.strip()]

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
