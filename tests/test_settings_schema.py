"""Where a setting's value comes from, when three places could answer.

A feature declares a variable in its pyproject and the product sets it in
its environment. The same feature can also declare that setting editable,
and then somebody types a different value into the admin panel. Both are
the same setting reached at a different moment, and resolving them in the
wrong order makes one of the two look broken: an environment ignored means
a deployment's decision is silently dropped, a panel ignored means typing
in it does nothing.
"""

import pytest
from flask import Flask

from splent_framework.settings import settings_schema
from splent_framework.settings.settings_schema import (
    clear_settings_schemas,
    env_key,
    get_config,
    register_settings,
    setting_value,
)


@pytest.fixture(autouse=True)
def registry():
    clear_settings_schemas()
    yield
    clear_settings_schemas()


@pytest.fixture
def app():
    return Flask(__name__)


@pytest.fixture
def stored(monkeypatch):
    """Stand in for the settings table, which lives in a feature."""

    def use(values):
        monkeypatch.setattr(settings_schema, "_stored_values", lambda: values)

    return use


def declare():
    register_settings(
        "search",
        "Search",
        [
            {
                "key": "placeholder",
                "env": "SEARCH_PLACEHOLDER",
                "type": "text",
                "default": "",
            },
            {"key": "nav", "env": "SEARCH_NAV", "type": "bool", "default": "1"},
            {"key": "limit", "env": "SEARCH_LIMIT", "type": "int", "default": "20"},
        ],
    )


class TestWhichAnswerWins:
    def test_the_panel_beats_the_environment(self, app, stored):
        """Somebody typed it after the app started, so it is the newer
        decision of the two."""
        declare()
        stored({"search_placeholder": "Buscar aquí"})
        app.config["SEARCH_PLACEHOLDER"] = "Search this site"

        with app.app_context():
            assert get_config("search")["placeholder"] == "Buscar aquí"

    def test_the_environment_beats_the_declared_default(self, app, stored):
        """Without this the panel and the .env are separate universes: a
        product setting the variable would see the panel offer an empty box
        and filling it in would silently disagree with the file."""
        declare()
        stored({})
        app.config["SEARCH_PLACEHOLDER"] = "Search this site"

        with app.app_context():
            assert get_config("search")["placeholder"] == "Search this site"

    def test_the_default_answers_when_nobody_else_does(self, app, stored):
        declare()
        stored({})

        with app.app_context():
            assert get_config("search")["limit"] == 20

    def test_an_empty_stored_value_means_follow_the_environment(self, app, stored):
        """The panel stores empty for a field left alone, so a later change
        to the .env is not shadowed by a copy nobody remembers making."""
        declare()
        stored({"search_placeholder": ""})
        app.config["SEARCH_PLACEHOLDER"] = "Search this site"

        with app.app_context():
            assert get_config("search")["placeholder"] == "Search this site"


class TestTypes:
    def test_a_bool_from_the_environment_arrives_as_a_bool(self, app, stored):
        """config.py has already turned SEARCH_NAV into a Python bool by the
        time this reads it, unlike the panel, which stores "0" and "1"."""
        declare()
        stored({})
        app.config["SEARCH_NAV"] = False

        with app.app_context():
            assert get_config("search")["nav"] is False

    def test_a_bool_turned_off_in_the_panel_stays_off(self, app, stored):
        declare()
        stored({"search_nav": "0"})
        app.config["SEARCH_NAV"] = True

        with app.app_context():
            assert get_config("search")["nav"] is False

    def test_an_int_from_the_environment_is_cast(self, app, stored):
        declare()
        stored({})
        app.config["SEARCH_LIMIT"] = "50"

        with app.app_context():
            assert get_config("search")["limit"] == 50


class TestWhichVariableAFieldShadows:
    def test_it_is_stated_when_the_name_is_not_the_features(self):
        """The theme's site_name field shadows SITE_NAME, not
        THEME_SITE_NAME, and most settings are named like that."""
        field = {"key": "site_name", "env": "SITE_NAME"}

        assert env_key("theme", field) == "SITE_NAME"

    def test_otherwise_it_is_the_feature_and_the_key(self):
        assert env_key("slider", {"key": "autoplay"}) == "SLIDER_AUTOPLAY"


class TestAskingForOneValue:
    def test_it_resolves_exactly_as_the_whole_schema_does(self, app, stored):
        declare()
        stored({"search_placeholder": "Buscar aquí"})

        with app.app_context():
            assert setting_value("search", "placeholder") == "Buscar aquí"

    def test_an_unknown_feature_is_not_an_error(self, app):
        """A feature reading its own setting before init_feature has run, or
        after a product removed it, gets nothing rather than a crash."""
        with app.app_context():
            assert setting_value("nowhere", "anything") is None

    def test_an_unknown_field_is_not_an_error(self, app, stored):
        declare()
        stored({})

        with app.app_context():
            assert setting_value("search", "invented") is None


class TestWithoutTheSettingsFeature:
    def test_everything_falls_back_to_the_environment(self, app):
        """A product can install a feature and not the settings panel. The
        value it set in its .env still has to be what the feature reads."""
        declare()
        app.config["SEARCH_PLACEHOLDER"] = "Search this site"

        with app.app_context():
            assert get_config("search")["placeholder"] == "Search this site"


class TestAListEditedAsOneLine:
    def test_it_arrives_joined_rather_than_as_a_python_list(self, app, stored):
        """config.py has often already split a comma separated variable by
        the time this reads app.config, and a form field rendering
        ['Teoría', 'Prácticas'] is not something anybody can edit."""
        register_settings(
            "courses",
            "Courses",
            [
                {
                    "key": "sections",
                    "env": "COURSES_SECTIONS",
                    "type": "text",
                    "default": "",
                }
            ],
        )
        stored({})
        app.config["COURSES_SECTIONS"] = ["Teoría", "Prácticas"]

        with app.app_context():
            assert get_config("courses")["sections"] == "Teoría,Prácticas"
