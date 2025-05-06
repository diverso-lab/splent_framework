import os
import importlib
from flask import Blueprint
from splent_cli.utils.path_utils import PathUtils


class FeatureManager:
    def __init__(self, app):
        self.app = app
        self.features_file = PathUtils.get_features_file()

    def _load_features(self):
        if not os.path.exists(self.features_file):
            return []
        with open(self.features_file) as f:
            return [line.strip() for line in f if line.strip()]

    def register_features(self):
        for feature_pkg in self._load_features():
            print(f"\n🔍 Registrando feature: {feature_pkg}")
            try:
                # Importar el módulo principal
                module = importlib.import_module(feature_pkg)

                # Intentar importar explícitamente el módulo de rutas
                try:
                    module_name = f"{feature_pkg}.routes"
                    print(f"🧪 Forzando import: {module_name}")
                    imported = __import__(module_name, fromlist=["*"])
                    print(f"✅ Importado: {imported}")
                except Exception as e:
                    print(f"💥 Fallo real importando {module_name}: {type(e).__name__} -> {e}")


                # Registrar cualquier Blueprint definido en el módulo
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if isinstance(obj, Blueprint):
                        if obj.name not in self.app.blueprints:
                            self.app.register_blueprint(obj)
                            print(f"✅ Registered blueprint '{obj.name}' from {feature_pkg}")
                        else:
                            print(f"⚠️  Blueprint '{obj.name}' ya registrado, se omite.")
            except Exception as e:
                print(f"❌ Error registrando '{feature_pkg}': {e}")
