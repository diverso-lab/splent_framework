from flask import Flask
from splent_framework.assets.asset_registry import get_assets
from splent_framework.context.context_manager import build_jinja_context
from splent_framework.hooks.template_hooks import (
    get_template_hooks,
    render_template_hooks,
)
from splent_framework.i18n import localized
from splent_framework.settings.settings_schema import get_config, setting_value


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
        # The rendered output of a slot as one Markup string, so a template
        # can ask "did any feature contribute here?" and fall back to its own
        # markup only when the answer is no. Iterating get_template_hooks
        # cannot tell an empty contribution from an absent one.
        self.app.jinja_env.globals["render_template_hooks"] = render_template_hooks
        self.app.jinja_env.globals["get_assets"] = get_assets
        # Product-supplied strings that still have to follow the language
        # switcher. A feature translates its own text through gettext; a
        # value the product wrote in its .env cannot be in any catalog, and
        # without this it stays in one language forever.
        self.app.jinja_env.globals["localized"] = localized
        # A setting a feature declared as admin-editable, resolved through
        # the panel and then the environment. Templates reaching for
        # config.SOMETHING see only the environment, so a value changed in
        # the panel would appear to do nothing.
        self.app.jinja_env.globals["feature_setting"] = setting_value
        self.app.jinja_env.globals["feature_settings"] = get_config
        # Whether a URL endpoint exists in this product's derivation. Lets one
        # feature's template link to another's route only when that feature is
        # installed, degrading to nothing otherwise: {% if
        # has_endpoint('edition_staff.admin_edition') %}…{% endif %}.
        self.app.jinja_env.globals["has_endpoint"] = self._has_endpoint

    def _has_endpoint(self, name: str) -> bool:
        return name in self.app.view_functions
