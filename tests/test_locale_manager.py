"""What language a product answers in, and what it says it answers in.

Two things went wrong here at once and neither was visible from the other.
The product's .env named Spanish and nothing read it, so every product ran
in English; and the base template asked for ``html_lang``, which no manager
ever defined, so the markup claimed English even once the pages were
Spanish. Both are pinned here, at the seam that owns them.
"""

import pytest
from flask import Flask, render_template_string

from splent_framework.managers.locale_manager import (
    LocaleManager,
    current_locale,
    html_lang,
)


def make_app(default="es", supported=("es", "en")):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    app.config["BABEL_DEFAULT_LOCALE"] = default
    app.config["BABEL_SUPPORTED_LOCALES"] = list(supported)
    LocaleManager(app)
    return app


class TestTheProductsDefaultIsHonoured:
    def test_a_reader_who_asks_for_nothing_gets_the_products_language(self):
        app = make_app(default="es")
        with app.test_request_context("/"):
            assert current_locale() == "es"

    def test_the_config_is_not_overwritten_by_the_manager(self):
        """setdefault used to be the only thing here, which was fine; the bug
        was upstream. Kept so a future refactor cannot start clobbering it."""
        app = make_app(default="es", supported=("es", "en"))
        assert app.config["BABEL_DEFAULT_LOCALE"] == "es"
        assert app.config["BABEL_SUPPORTED_LOCALES"] == ["es", "en"]

    def test_a_product_that_says_nothing_still_gets_english(self):
        app = Flask(__name__)
        LocaleManager(app)
        assert app.config["BABEL_DEFAULT_LOCALE"] == "en"
        assert app.config["BABEL_SUPPORTED_LOCALES"] == ["en"]


class TestTheReadersChoiceIsChecked:
    def test_a_supported_choice_wins_over_the_header(self):
        app = make_app()
        with app.test_request_context("/", headers={"Accept-Language": "es"}):
            from flask import session

            session["locale"] = "en"
            assert current_locale() == "en"

    def test_a_locale_the_product_does_not_offer_is_ignored(self):
        """A session survives a product dropping a language, and any feature
        can write to it. Trusting it asked Babel for a catalog that is not
        there while the switcher went on highlighting it."""
        app = make_app(default="es", supported=("es", "en"))
        with app.test_request_context("/", headers={"Accept-Language": "es"}):
            from flask import session

            session["locale"] = "de"
            assert current_locale() == "es"


class TestTheMarkupSaysWhatThePageSpeaks:
    def test_html_lang_reaches_a_template_without_the_theme_defining_it(self):
        app = make_app(default="es")
        with app.test_request_context("/"):
            rendered = render_template_string('<html lang="{{ html_lang }}">')
        assert rendered == '<html lang="es">'

    def test_a_regional_locale_is_spelled_the_way_html_wants_it(self):
        """Babel writes pt_BR, BCP 47 wants pt-BR, and lang is BCP 47."""
        app = make_app(default="pt_BR", supported=("pt_BR",))
        with app.test_request_context("/"):
            assert html_lang() == "pt-BR"

    def test_templates_also_get_the_list_for_a_language_switcher(self):
        app = make_app(default="es", supported=("es", "en"))
        with app.test_request_context("/"):
            rendered = render_template_string("{{ supported_locales | join(',') }}")
        assert rendered == "es,en"

    def test_it_answers_outside_a_request_too(self):
        """A mail body or a generated page is rendered with no request to
        negotiate against, and it still has to state a language."""
        app = make_app(default="es")
        with app.app_context():
            assert html_lang() == "es"


@pytest.mark.parametrize("supported", [["es", "en"], ["en"]])
def test_the_active_locale_is_always_one_the_product_offers(supported):
    app = make_app(default=supported[0], supported=supported)
    with app.test_request_context("/", headers={"Accept-Language": "de,fr;q=0.9"}):
        assert current_locale() in supported
