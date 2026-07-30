"""
LocaleManager — i18n/l10n support for SPLENT products.

Initialises Flask-Babel and discovers translation directories from all
loaded features so that each feature can ship its own translations.

Configuration (in product config.py or .env):
    BABEL_DEFAULT_LOCALE    — fallback locale (default: "en")
    BABEL_SUPPORTED_LOCALES — list of enabled locales (default: ["en"])

Locale selection priority:
    1. Session key "locale", when it names a supported locale
    2. Accept-Language header
    3. BABEL_DEFAULT_LOCALE

Templates get ``html_lang``, ``current_locale`` and ``supported_locales``
from here, so a theme never has to work the active language out for itself.
"""

import logging
import os

from flask import current_app, has_request_context, request, session
from flask_babel import Babel

logger = logging.getLogger(__name__)

_babel: Babel | None = None


def get_locale():
    """Select the best locale for the current request."""
    supported = current_app.config.get("BABEL_SUPPORTED_LOCALES", ["en"])

    # 1. Explicit session override (set by a language switcher).
    #    Checked against what the product offers rather than trusted: the
    #    session is writable by any feature and survives a product dropping a
    #    language, so an unchecked value here would ask Babel for a catalog
    #    that is not there and answer in the default while the switcher kept
    #    highlighting the language nobody is reading.
    locale = session.get("locale")
    if locale and locale in supported:
        return locale

    # 2. The language the product says it speaks.
    #
    #    Ahead of the Accept-Language header, and off by default, because a
    #    product line builds sites for institutions: a course wiki written in
    #    Spanish is a Spanish site, and answering a browser configured in
    #    English with an English interface wrapped around Spanish material
    #    serves nobody. It also surprises the people who run it, who set the
    #    language in the .env and then find the site answering in another one
    #    depending on whose laptop is open.
    #
    #    Readers who want the other language are not stuck: the switcher puts
    #    their choice in the session, which is step 1 and beats this.
    #
    #    A product that genuinely wants the browser to decide, a marketplace
    #    or a public site with no home country, sets
    #    BABEL_NEGOTIATE_FROM_HEADER.
    if not current_app.config.get("BABEL_NEGOTIATE_FROM_HEADER", False):
        return current_app.config.get("BABEL_DEFAULT_LOCALE", "en")

    # 3. Accept-Language header negotiation
    return request.accept_languages.best_match(supported)


def current_locale() -> str:
    """The locale in force, as a string, always answerable.

    Falls back to the product's default outside a request, where there is no
    header to negotiate and no session to read, so a template rendered offline
    (a mail body, a generated page) still states a language.
    """
    default = current_app.config.get("BABEL_DEFAULT_LOCALE", "en")
    if not has_request_context():
        return default
    from flask_babel import get_locale as babel_locale

    return str(babel_locale() or default)


def html_lang() -> str:
    """The locale in force, spelled for an HTML ``lang`` attribute.

    Babel writes a locale with an underscore (``pt_BR``); BCP 47, which is
    what ``lang`` takes, uses a hyphen (``pt-BR``). The difference matters to
    a screen reader choosing a voice and to a browser offering to translate
    the page, and it is the kind of detail every theme would otherwise have to
    get right on its own.
    """
    return current_locale().replace("_", "-")


class LocaleManager:
    def __init__(self, app):
        global _babel

        app.config.setdefault("BABEL_DEFAULT_LOCALE", "en")
        app.config.setdefault("BABEL_SUPPORTED_LOCALES", ["en"])

        _babel = Babel(app, locale_selector=get_locale)

        # Store reference for feature translation directory registration
        app.extensions["splent_babel"] = _babel
        app.extensions["splent_translation_dirs"] = []

        # Every page needs the active language in its <html> tag, and it is
        # this manager that decides what the active language is. Leaving each
        # theme to work it out meant the one variable the base template asked
        # for, html_lang, was defined by nobody: every product declared
        # English in its markup for as long as themes have existed, however
        # loudly the rest of the page spoke Spanish.
        @app.context_processor
        def inject_locale():
            return {
                "html_lang": html_lang(),
                "current_locale": current_locale(),
                "supported_locales": app.config.get("BABEL_SUPPORTED_LOCALES", ["en"]),
            }

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

            # flask-babel computes its translation directories ONCE in init_app
            # (BabelConfiguration.translation_directories) and never re-reads the
            # config. Features load AFTER Babel is initialised, so we (1) keep the
            # config in sync and (2) mutate the live BabelConfiguration list
            # (app.extensions["babel"]) so the new directory actually takes effect.
            app.config["BABEL_TRANSLATION_DIRECTORIES"] = ";".join(dirs)
            babel_cfg = app.extensions.get("babel")
            live = getattr(babel_cfg, "translation_directories", None)
            if isinstance(live, list) and translations_dir not in live:
                live.append(translations_dir)

            logger.debug("Registered translations: %s", translations_dir)
