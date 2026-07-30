"""Cross-site request forgery, which the product had no protection against.

Nothing registered CSRFProtect, so the only forms that checked a token were
the ones whose feature happened to build a FlaskForm. Forty writes across
sixteen features accepted a POST from anywhere, the media library's delete
among them: a page on another site, opened in a tab by a logged-in member
of staff, could empty it.

Registered in the framework rather than per feature, because a protection
each feature has to remember is a protection sixteen features forgot.
"""

import pytest
from flask import Flask

from splent_framework.managers.csrf_manager import CSRFManager


def make_app(enabled=True):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    app.config["WTF_CSRF_ENABLED"] = enabled

    @app.route("/delete-everything", methods=["POST"])
    def destructive():
        return "gone"

    @app.route("/token")
    def token():
        """Stands in for a page with a form on it.

        The token has to come from a page the same session was served.
        Minting one on the side and posting it back would prove nothing
        about whether the two ends agree.
        """
        from flask_wtf.csrf import generate_csrf

        return generate_csrf()

    CSRFManager(app)
    return app


class TestAWriteFromNowhere:
    def test_a_post_without_a_token_is_refused(self):
        app = make_app()
        response = app.test_client().post("/delete-everything")
        assert response.status_code == 400

    def test_a_post_with_the_token_goes_through(self):
        app = make_app()
        client = app.test_client()
        token = client.get("/token").get_data(as_text=True)

        response = client.post("/delete-everything", data={"csrf_token": token})
        assert response.status_code == 200

    def test_the_header_form_works_too(self):
        """What an AJAX call sends, the live preview among them."""
        app = make_app()
        client = app.test_client()
        token = client.get("/token").get_data(as_text=True)

        response = client.post("/delete-everything", headers={"X-CSRFToken": token})
        assert response.status_code == 200

    def test_somebody_elses_token_is_not_good_enough(self):
        """The whole point: a token has to belong to this session, or it is
        just a string an attacker can fetch for themselves."""
        app = make_app()
        stolen = app.test_client().get("/token").get_data(as_text=True)

        response = app.test_client().post(
            "/delete-everything", data={"csrf_token": stolen}
        )
        assert response.status_code == 400


class TestTheCookieHelpsToo:
    """SameSite=Lax stops a browser attaching the session to a cross-site
    POST at all, one step earlier than the token does. The token stays,
    because Lax is a browser's promise and not ours."""

    @pytest.mark.parametrize(
        "key,expected",
        [
            ("SESSION_COOKIE_SAMESITE", "Lax"),
            ("SESSION_COOKIE_HTTPONLY", True),
        ],
    )
    def test_the_defaults_are_set(self, key, expected):
        assert make_app().config[key] == expected

    def test_a_product_can_still_choose(self):
        app = Flask(__name__)
        app.config["SECRET_KEY"] = "test"
        app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
        CSRFManager(app)
        assert app.config["SESSION_COOKIE_SAMESITE"] == "Strict"


def test_the_testing_configuration_can_turn_it_off():
    """Otherwise every functional test in every feature would have to mint
    a token to post a form."""
    app = make_app(enabled=False)
    assert app.test_client().post("/delete-everything").status_code == 200
