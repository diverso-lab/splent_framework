# module_manager.py
import os
import importlib.util
from flask import Blueprint
from dotenv import load_dotenv

from splent_cli.utils.path_utils import PathUtils

load_dotenv()


class ModuleManager:
    def __init__(self, app):
        self.app = app
        self.base_dir = os.path.abspath(os.path.dirname(__file__))
        self.modules_dir = PathUtils.get_modules_dir()

        self.ignored_modules_file = os.path.join(
            self.modules_dir, "..", ".moduleignore"
        )
        self.ignored_modules = self._load_ignored_modules()

    def _find_installed_modules_dir(self):
        """Intenta encontrar la carpeta 'app/modules' cuando splent_app está instalado desde PyPI."""
        package = importlib.util.find_spec("aspp")
        if package and package.origin:
            return os.path.join(os.path.dirname(package.origin), "modules")

        # Si no se encuentra, lanza error
        raise FileNotFoundError(
            "No se pudo encontrar 'app/modules'. Verifica la instalación de splent_app."
        )

    def _load_ignored_modules(self):
        ignored_modules = []
        if os.path.exists(self.ignored_modules_file):
            with open(self.ignored_modules_file) as f:
                ignored_modules = [line.strip() for line in f.readlines()]
        return ignored_modules

    def register_modules(self):
        self.app.modules = {}
        self.app.blueprint_url_prefixes = {}

        for module_name in os.listdir(self.modules_dir):

            if module_name in self.ignored_modules:
                continue

            module_path = os.path.join(self.modules_dir, module_name)
            if (
                os.path.isdir(module_path)
                and not module_name.startswith("__")
                and os.path.exists(os.path.join(module_path, "__init__.py"))
                and module_name != ".pytest_cache"
            ):
                try:
                    routes_module = importlib.import_module(
                        f"splent_app.modules.{module_name}.routes"
                    )
                    for item in dir(routes_module):
                        if isinstance(getattr(routes_module, item), Blueprint):
                            blueprint = getattr(routes_module, item)
                            self.app.register_blueprint(blueprint)
                except ModuleNotFoundError as e:
                    print(
                        f"Error registering modules: Could not load the module "
                        f"for Module '{module_name}': {e}"
                    )

    def register_module(self, module_name):
        module_path = os.path.join(self.modules_dir, module_name)
        if os.path.isdir(module_path) and not module_name.startswith("__"):
            try:
                routes_module = importlib.import_module(
                    f"splent_app.modules.{module_name}.routes"
                )
                for item in dir(routes_module):
                    if isinstance(getattr(routes_module, item), Blueprint):
                        blueprint = getattr(routes_module, item)
                        self.app.register_module(blueprint)
                return
            except ModuleNotFoundError as e:
                print(
                    f"Could not load the module for Blueprint '{module_name}': {e}"
                )

    def unregister_blueprints(self):
        for name, blueprint in list(self.app.modules.items()):
            print(f"Unregistering module: {name}")
            self.app.modules.pop(name)

    def reload_blueprints(self):
        self.unregister_blueprints()
        self.register_modules()

    def print_registered_modules(self):
        print("Registered blueprints")
        for name, blueprint in self.app.modules.items():
            url_prefix = self.app.blueprint_url_prefixes.get(
                name, "No URL prefix set"
            )
            print(f"Name: {name}, URL prefix: {url_prefix}")

    def get_modules(self):
        all_modules = []
        for module_name in os.listdir(self.modules_dir):
            module_path = os.path.join(self.modules_dir, module_name)
            if (
                os.path.isdir(module_path)
                and not module_name.startswith("__")
                and os.path.exists(os.path.join(module_path, "__init__.py"))
                and module_name != ".pytest_cache"
            ):
                all_modules.append(module_name)
        loaded_modules = [
            m for m in all_modules if m not in self.ignored_modules
        ]
        return loaded_modules, self.ignored_modules
