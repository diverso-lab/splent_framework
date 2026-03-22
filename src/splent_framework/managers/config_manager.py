import importlib
import logging
import os

logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, app):
        self.app = app

    @classmethod
    def init_app(cls, app, config_name="development"):
        """Factory method to initialize and load configuration."""
        manager = cls(app)
        manager.load_config(config_name)

    def load_config(self, config_name: str = "development") -> None:
        config_name = config_name or os.getenv("FLASK_ENV", "development")
        splent_app = os.getenv("SPLENT_APP", "splent_app")

        try:
            config_module = importlib.import_module(f"{splent_app}.config")
        except ModuleNotFoundError:
            from splent_framework.configuration import default_config as config_module

            logger.warning("No product config.py found for '%s', using SPLENT default config.", splent_app)

        config_class_name = f"{config_name.capitalize()}Config"
        config_class = getattr(config_module, config_class_name, None)

        if config_class is None:
            raise RuntimeError(
                f"Could not find class '{config_class_name}' in '{splent_app}.config'"
            )

        config_instance = config_class()

        # Combine instance attributes (set in __init__) with class-level uppercase attrs
        config_data = {k: v for k, v in config_instance.__dict__.items() if k.isupper()}
        for k in dir(config_instance):
            if k.isupper() and k not in config_data:
                config_data[k] = getattr(config_instance, k)

        self.app.config.from_mapping(config_data)
