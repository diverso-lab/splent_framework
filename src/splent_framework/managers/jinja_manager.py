from flask import Flask
from splent_framework.assets.asset_registry import get_assets
from splent_framework.context.context_manager import build_jinja_context
from splent_framework.hooks.template_hooks import get_template_hooks
from splent_framework.i18n import localized


class JinjaManager:
    def __init__(self, app: Flask, context: dict | None = None):
        self.app = app
        self.context = context or {}
        self._register_context_processor()
        self._register_globals()

    def _register_context_processor(self):
        @self.app.context_processor
        def inject_vars():
            return build_jinja_context(self.app, self.context)

    def _register_globals(self):
        self.app.jinja_env.globals["get_template_hooks"] = get_template_hooks
        self.app.jinja_env.globals["get_assets"] = get_assets
        # Product-supplied strings that still have to follow the language
        # switcher. A feature translates its own text through gettext; a
        # value the product wrote in its .env cannot be in any catalog, and
        # without this it stays in one language forever.
        self.app.jinja_env.globals["localized"] = localized
