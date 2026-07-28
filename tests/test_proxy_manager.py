"""Tests for ProxyManager — who the application thinks the client is.

``request.remote_addr`` is whoever opened the connection. Behind a reverse
proxy that is the proxy, for every caller in the world, so anything keyed on it
collapses into one bucket: a per caller rate limit becomes a global one a
stranger can hold against everybody. Exposed directly, the peer address is
right and ``X-Forwarded-For`` is a header the caller writes themselves, so
trusting it there hands an attacker an unlimited supply of identities.

Both mistakes are the same switch, set wrong in opposite directions, which is
why the switch is a COUNT of proxies rather than a boolean.
"""

import pytest
from flask import Flask, request

from splent_framework.managers.proxy_manager import CONFIG_KEY, ProxyManager


def _app(**config):
    app = Flask(__name__)
    app.config.update(config)

    @app.route("/who")
    def who():
        return request.remote_addr or ""

    return app


def _get(app, forwarded_for=None):
    headers = {"X-Forwarded-For": forwarded_for} if forwarded_for else {}
    with app.test_client() as client:
        return client.get(
            "/who", headers=headers, environ_overrides={"REMOTE_ADDR": "10.0.0.1"}
        ).get_data(as_text=True)


class TestNothingInFront:
    def test_the_peer_address_is_used_by_default(self, monkeypatch):
        monkeypatch.delenv(CONFIG_KEY, raising=False)
        app = _app()
        ProxyManager.init_app(app)
        assert _get(app) == "10.0.0.1"

    def test_a_forwarding_header_is_not_believed(self, monkeypatch):
        """Exposed directly, this header is text the attacker chose."""
        monkeypatch.delenv(CONFIG_KEY, raising=False)
        app = _app()
        ProxyManager.init_app(app)
        assert _get(app, forwarded_for="203.0.113.9") == "10.0.0.1"


class TestOneProxyInFront:
    def test_the_real_client_is_read_from_the_header(self):
        app = _app(**{CONFIG_KEY: 1})
        ProxyManager.init_app(app)
        assert _get(app, forwarded_for="203.0.113.9") == "203.0.113.9"

    def test_only_the_last_hop_is_taken(self):
        """With one proxy declared, only one entry from the right is trusted.

        Setting the count higher than the real number of proxies is what lets a
        caller inject an entry that gets read as the client address.
        """
        app = _app(**{CONFIG_KEY: 1})
        ProxyManager.init_app(app)
        assert _get(app, forwarded_for="1.2.3.4, 203.0.113.9") == "203.0.113.9"

    def test_the_peer_is_still_used_when_no_header_arrives(self):
        app = _app(**{CONFIG_KEY: 1})
        ProxyManager.init_app(app)
        assert _get(app) == "10.0.0.1"


class TestTheSwitchItself:
    def test_it_can_come_from_the_environment(self, monkeypatch):
        monkeypatch.setenv(CONFIG_KEY, "1")
        app = _app()
        ProxyManager.init_app(app)
        assert _get(app, forwarded_for="203.0.113.9") == "203.0.113.9"

    def test_the_product_config_wins_over_the_environment(self, monkeypatch):
        """A product may refuse to believe its environment."""
        monkeypatch.setenv(CONFIG_KEY, "1")
        app = _app(**{CONFIG_KEY: 0})
        ProxyManager.init_app(app)
        assert _get(app, forwarded_for="203.0.113.9") == "10.0.0.1"

    @pytest.mark.parametrize("value", ["", "yes", "true", None, -3])
    def test_anything_that_is_not_a_count_of_proxies_reads_as_none(self, value):
        app = _app(**{CONFIG_KEY: value})
        ProxyManager.init_app(app)
        assert _get(app, forwarded_for="203.0.113.9") == "10.0.0.1"

    def test_installing_it_twice_does_not_stack_the_middleware(self):
        app = _app(**{CONFIG_KEY: 1})
        ProxyManager.init_app(app)
        wrapped = app.wsgi_app
        ProxyManager.init_app(app)
        assert app.wsgi_app is not wrapped  # it does wrap again
        # and the answer is still the last hop, not one further left
        assert _get(app, forwarded_for="1.2.3.4, 203.0.113.9") == "203.0.113.9"
