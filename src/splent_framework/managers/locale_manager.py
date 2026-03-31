"""
LocaleManager — i18n/l10n support for SPLENT products.

Initialises Flask-Babel and discovers translation directories from all
loaded features so that each feature can ship its own translations.

Configuration (in product config.py or .env):
    BABEL_DEFAULT_LOCALE    — fallback locale (default: "en")
    BABEL_SUPPORTED_LOCALES — list of enabled locales (default: ["en"])

Locale selection priority:
    1. URL prefix (/es/login) if BABEL_URL_PREFIX is True
    2. Session key "locale"
    3. Accept-Language header
    4. BABEL_DEFAULT_LOCALE
"""

import logging
import os

from flask import request, session
from flask_babel import Babel

logger = logging.getLogger(__name__)

_babel: Babel | None = None


def get_locale():
    """Select the best locale for the current request."""
    # 1. Explicit session override (set by a language switcher)
    locale = session.get("locale")
    if locale:
        return locale

    # 2. Accept-Language header negotiation
    from flask import current_app

    supported = current_app.config.get("BABEL_SUPPORTED_LOCALES", ["en"])
    return request.accept_languages.best_match(supported)


class LocaleManager:
    def __init__(self, app):
        global _babel

        app.config.setdefault("BABEL_DEFAULT_LOCALE", "en")
        app.config.setdefault("BABEL_SUPPORTED_LOCALES", ["en"])

        _babel = Babel(app, locale_selector=get_locale)

        # Store reference for feature translation directory registration
        app.extensions["splent_babel"] = _babel
        app.extensions["splent_translation_dirs"] = []

        logger.debug(
            "LocaleManager initialised (default=%s, supported=%s)",
            app.config["BABEL_DEFAULT_LOCALE"],
            app.config["BABEL_SUPPORTED_LOCALES"],
        )

    @staticmethod
    def register_translation_dir(app, translations_dir: str) -> None:
        """Register a feature's translations/ directory with Babel.

        Called by the FeatureIntegrator after loading each feature.
        """
        if not os.path.isdir(translations_dir):
            return

        dirs = app.extensions.get("splent_translation_dirs", [])
        if translations_dir not in dirs:
            dirs.append(translations_dir)

            # Babel supports multiple translation directories
            babel = app.extensions.get("splent_babel")
            if babel and hasattr(babel, "translation_directories"):
                babel.translation_directories.append(translations_dir)

            logger.debug("Registered translations: %s", translations_dir)
