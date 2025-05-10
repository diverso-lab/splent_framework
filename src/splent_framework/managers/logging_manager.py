import logging as std_logging  # el módulo estándar
import os
import importlib
from logging.handlers import RotatingFileHandler


class LoggingManager:
    def __init__(self, app):
        self.app = app
        self.custom_logging = self._import_custom_logging()

    def setup_logging(self):
        if self.custom_logging and hasattr(self.custom_logging, "configure_logging"):
            return self.custom_logging.configure_logging(self.app)
        self._default_logging()

    def _import_custom_logging(self):
        module_name = os.getenv("SPLENT_APP", "splent_app")
        try:
            return importlib.import_module(f"{module_name}.logging")
        except ModuleNotFoundError:
            return None

    def _default_logging(self):
        formatter = std_logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        file_handler = RotatingFileHandler("app.log", maxBytes=10240, backupCount=10)
        file_handler.setLevel(std_logging.ERROR)
        file_handler.setFormatter(formatter)
        self.app.logger.addHandler(file_handler)

        if self.app.debug:
            stream_handler = std_logging.StreamHandler()
            stream_handler.setLevel(std_logging.INFO)
            stream_handler.setFormatter(formatter)
            self.app.logger.addHandler(stream_handler)

        self.app.logger.setLevel(std_logging.INFO)
