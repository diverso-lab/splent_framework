import importlib
import logging
import os

logger = logging.getLogger(__name__)


# SPLENT_ENV is what the CLI and the entrypoints already agree on ("dev" in
# development, "prod" in every deploy artifact, "test" under the runner).
# The Flask config profile follows it, so a product never has to say which
# profile it wants: the environment it runs in already says so.
_PROFILE_BY_ENV = {
    "dev": "development",
    "development": "development",
    "prod": "production",
    "production": "production",
    "test": "testing",
    "testing": "testing",
}


def resolve_config_name(config_name: str | None = None) -> str:
    """The configuration profile to load.

    An explicit name wins, which keeps tests on ``testing`` and lets an
    entrypoint force ``production``. Without one, SPLENT_ENV decides, then
    FLASK_ENV, and development is the fallback. Before this the factory
    defaulted to ``development`` unconditionally, so gunicorn in a deploy
    ran DevelopmentConfig: DEBUG on and the framework's placeholder
    SECRET_KEY signing every session, CSRF token and reset link.
    """
    if config_name:
        return config_name
    for var in ("SPLENT_ENV", "FLASK_ENV"):
        value = os.getenv(var, "").strip().lower()
        if value in _PROFILE_BY_ENV:
            return _PROFILE_BY_ENV[value]
    return "development"


class ConfigManager:
    def __init__(self, app):
        self.app = app

    @classmethod
    def init_app(cls, app, config_name=None):
        """Factory method to initialize and load configuration."""
        manager = cls(app)
        manager.load_config(config_name)
        return manager

    def load_config(self, config_name: str | None = None) -> None:
        config_name = resolve_config_name(config_name)
        splent_app = os.getenv("SPLENT_APP", "splent_app")

        try:
            config_module = importlib.import_module(f"{splent_app}.config")
        except ModuleNotFoundError:
            from splent_framework.configuration import default_config as config_module

            logger.warning(
                "No product config.py found for '%s', using SPLENT default config.",
                splent_app,
            )

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

        # Trace: mark all product-level config keys
        trace = self.app.extensions.setdefault("splent_config_trace", {})
        for key, value in config_data.items():
            trace[key] = {
                "value": value,
                "source": f"product ({splent_app})",
                "action": "set",
            }
