import os
import importlib
from flask import Blueprint
from splent_cli.utils.path_utils import PathUtils


class FeatureManager:
    def __init__(self, app):
        self.app = app
        self.features_file = PathUtils.get_features_file()

    def _load_features(self):
        features = []
        if os.path.exists(self.features_file):
            with open(self.features_file) as f:
                features = [line.strip() for line in f.readlines() if line.strip()]
        return features

    def register_features(self):
        self.app.modules = {}
        self.app.blueprint_url_prefixes = {}

        for feature_pkg in self._load_features():
            print(f"\n🔍 Registrando feature: {feature_pkg}")

            try:
                # Importar el módulo principal
                feature_module = importlib.import_module(feature_pkg)
                print(f"📦 Importado paquete: {feature_module}")

                # Forzar explícitamente la carga de routes.py
                try:
                    print(f"🧪 Intentando importar {feature_pkg}.routes...")
                    routes_module = importlib.import_module(f"{feature_pkg}.routes")
                    print(f"✅ Módulo de rutas cargado: {routes_module}")
                except ModuleNotFoundError as mnfe:
                    print(f"⚠️  {feature_pkg} no tiene routes.py (y no pasa nada si no necesita rutas)")
                except Exception as ex:
                    print(f"🚨 Error al importar rutas de {feature_pkg}: {ex}")

                # Registrar cualquier blueprint definido en __init__.py
                blueprints_registrados = 0
                for item in dir(feature_module):
                    maybe_bp = getattr(feature_module, item)
                    if isinstance(maybe_bp, Blueprint):
                        self.app.register_blueprint(maybe_bp)
                        blueprints_registrados += 1
                        print(f"✅ Registered blueprint '{maybe_bp.name}' from {feature_pkg}")

                if blueprints_registrados == 0:
                    print(f"⚠️  {feature_pkg} no contiene ningún blueprint en __init__.py")

            except Exception as e:
                print(f"❌ Could not import feature '{feature_pkg}': {e}")

