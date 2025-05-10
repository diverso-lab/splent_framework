from flask import Flask
from splent_framework.context.context_manager import build_jinja_context


class JinjaManager:
    def __init__(self, app: Flask, context: dict = None):
        self.app = app
        self.context = context or {}
        self._register_context_processor()

    def _register_context_processor(self):
        @self.app.context_processor
        def inject_vars():
            return build_jinja_context(self.app, self.context)
