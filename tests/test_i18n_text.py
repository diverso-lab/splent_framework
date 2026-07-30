"""Product-supplied text that still has to follow the language switcher.

A feature translates its own strings through gettext. A string the product
writes in its .env cannot be in any catalog, and the first version of
SEARCH_PLACEHOLDER proved what that costs: a wiki switched to English and
went on saying "Buscar en esta wiki" in the one control a reader uses most.
"""

import pytest
from flask import Flask

from splent_framework.i18n import localized, parse_localized
from splent_framework.managers.locale_manager import LocaleManager


def make_app(default="es", supported=("es", "en")):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    app.config["BABEL_DEFAULT_LOCALE"] = default
    app.config["BABEL_SUPPORTED_LOCALES"] = list(supported)
    LocaleManager(app)
    return app


class TestOneStringForEveryLanguage:
    def test_a_plain_value_is_used_as_written(self):
        """Right for a proper noun, which is most of what a product sets."""
        app = make_app()
        with app.test_request_context("/"):
            assert localized("egc.us.es") == "egc.us.es"

    def test_an_empty_value_falls_back_to_the_features_own_default(self):
        app = make_app()
        with app.test_request_context("/"):
            assert localized("", "Search this site") == "Search this site"
            assert localized(None, "Search this site") == "Search this site"


class TestAVariantPerLanguage:
    def test_the_reader_gets_their_language(self):
        app = make_app(default="es")
        with app.test_request_context("/"):
            assert (
                localized("es:Buscar en esta wiki|en:Search this wiki")
                == "Buscar en esta wiki"
            )

    def test_and_the_other_one_when_they_switch(self):
        app = make_app(default="en", supported=("en", "es"))
        with app.test_request_context("/"):
            assert (
                localized("es:Buscar en esta wiki|en:Search this wiki")
                == "Search this wiki"
            )

    def test_a_region_falls_back_to_its_language(self):
        """pt-BR finds pt, so a product does not have to enumerate regions."""
        app = make_app(default="pt-BR", supported=("pt-BR",))
        with app.test_request_context("/"):
            assert localized("pt:Pesquisar|en:Search") == "Pesquisar"

    def test_a_language_nobody_wrote_gets_the_first_one(self):
        """A product that adds a language before translating its labels
        should show something rather than a blank control."""
        app = make_app(default="de", supported=("de",))
        with app.test_request_context("/"):
            assert localized("es:Buscar|en:Search") == "Buscar"


class TestWhatIsNotATaggedValue:
    """A value is only split when every piece carries a language tag.

    Otherwise a string that merely contains a colon would be sliced into
    nonsense, and the product would have written a perfectly good label.
    """

    @pytest.mark.parametrize(
        "raw",
        [
            "Buscar: en esta wiki",
            "https://example.org",
            "Abierto 9:00-14:00",
            "es:Buscar|Search this wiki",
            "Search this wiki",
        ],
    )
    def test_it_is_left_alone(self, raw):
        app = make_app()
        with app.test_request_context("/"):
            assert localized(raw) == raw

    def test_parsing_says_so_too(self):
        assert parse_localized("Abierto 9:00-14:00") == {}
        assert parse_localized("es:Buscar|en:Search") == {
            "es": "Buscar",
            "en": "Search",
        }


def test_it_answers_outside_a_request():
    """A mail body or a generated page has no locale to negotiate and still
    has to say something."""
    app = make_app(default="es")
    with app.app_context():
        assert localized("es:Buscar|en:Search") == "Buscar"
