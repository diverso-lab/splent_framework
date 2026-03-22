import os
import importlib
import types
from collections.abc import Callable
from flask import render_template


class ErrorHandlerManager:
    def __init__(self, app) -> None:
        self.app = app
        self.custom_handlers = self._import_custom_handlers()

    def _import_custom_handlers(self) -> types.ModuleType | None:
        splent_app = os.getenv("SPLENT_APP", "splent_app")
        try:
            return importlib.import_module(f"{splent_app}.errors")
        except ModuleNotFoundError:
            return None

    def _get_handler(self, name: str, fallback: Callable) -> Callable:
        if self.custom_handlers and hasattr(self.custom_handlers, name):
            return getattr(self.custom_handlers, name)
        return fallback

    def register_error_handlers(self) -> None:
        @self.app.errorhandler(500)
        def internal_error(e):
            return self._get_handler("handle_500", self._default_500)(self.app, e)

        @self.app.errorhandler(404)
        def not_found_error(e):
            return self._get_handler("handle_404", self._default_404)(self.app, e)

        @self.app.errorhandler(401)
        def unauthorized_error(e):
            return self._get_handler("handle_401", self._default_401)(self.app, e)

        @self.app.errorhandler(400)
        def bad_request_error(e):
            return self._get_handler("handle_400", self._default_400)(self.app, e)

    @staticmethod
    def _default_500(app, e):
        app.logger.error("Internal Server Error: %s", str(e))
        return render_template("500.html"), 500

    @staticmethod
    def _default_404(app, e):
        app.logger.warning("Page Not Found: %s", str(e))
        return render_template("404.html"), 404

    @staticmethod
    def _default_401(app, e):
        app.logger.warning("Unauthorized Access: %s", str(e))
        return render_template("401.html"), 401

    @staticmethod
    def _default_400(app, e):
        app.logger.warning("Bad Request: %s", str(e))
        return render_template("400.html"), 400
