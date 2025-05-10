import importlib
import os


class ConfigManager:
    def __init__(self, app):
        self.app = app

    @classmethod
    def init_app(cls, app, config_name="development"):
        """Factory method to initialize and load configuration."""
        manager = cls(app)
        manager.load_config(config_name)

    def load_config(self, config_name="development"):
        config_name = config_name or os.getenv("FLASK_ENV", "development")
        splent_app = os.getenv("SPLENT_APP", "splent_app")

        try:
            config_module = importlib.import_module(f"{splent_app}.config")
        except ModuleNotFoundError:
            from splent_framework.configuration import default_config as config_module
            print(f"⚠️ Using SPLENT default config (no product config.py found)")

        config_class_name = f"{config_name.capitalize()}Config"
        config_class = getattr(config_module, config_class_name, None)

        if config_class is None:
            raise RuntimeError(f"❌ Could not find class '{config_class_name}' in '{splent_app}.config'")

        self.app.config.from_object(config_class)
