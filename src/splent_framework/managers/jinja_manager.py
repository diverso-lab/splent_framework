from flask import Flask
from splent_framework.context.context_manager import build_jinja_context
from splent_framework.hooks.template_hooks import get_template_hooks


class JinjaManager:
    def __init__(self, app: Flask, context: dict = None):
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
