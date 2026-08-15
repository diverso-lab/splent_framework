"""
Tests for ConfigManager.load_config.
"""

import pytest
from flask import Flask
from splent_framework.managers.config_manager import ConfigManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app():
    return Flask(__name__)


# ---------------------------------------------------------------------------
# load_config — uses splent_framework default config (no product module)
# ---------------------------------------------------------------------------


class TestLoadConfigDefaults:
    def test_development_sets_debug_true(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        app = _make_app()
        ConfigManager.init_app(app, "development")
        assert app.config.get("DEBUG") is True

    def test_testing_sets_testing_true(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        app = _make_app()
        ConfigManager.init_app(app, "testing")
        assert app.config.get("TESTING") is True

    def test_development_has_database_uri(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        app = _make_app()
        ConfigManager.init_app(app, "development")
        assert "SQLALCHEMY_DATABASE_URI" in app.config

    def test_track_modifications_disabled(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        app = _make_app()
        ConfigManager.init_app(app, "development")
        assert app.config.get("SQLALCHEMY_TRACK_MODIFICATIONS") is False

    def test_secret_key_present(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        app = _make_app()
        ConfigManager.init_app(app, "development")
        assert app.config.get("SECRET_KEY")

    def test_raises_for_unknown_config_name(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        app = _make_app()
        with pytest.raises(RuntimeError, match="Could not find class"):
            ConfigManager.init_app(app, "unknown_env")

    def test_config_name_defaults_to_development(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        monkeypatch.delenv("SPLENT_ENV", raising=False)
        monkeypatch.delenv("FLASK_ENV", raising=False)
        app = _make_app()
        ConfigManager.init_app(app)  # no config_name arg
        assert app.config.get("DEBUG") is True


class TestProfileFollowsEnvironment:
    """A deploy sets SPLENT_ENV=prod and nothing else; gunicorn calls the
    product's create_app() with no profile. That used to load
    DevelopmentConfig in production, DEBUG on and the placeholder
    SECRET_KEY signing every session and reset link."""

    def test_prod_env_loads_production(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        monkeypatch.setenv("SPLENT_ENV", "prod")
        monkeypatch.setenv("SECRET_KEY", "a-real-secret")
        app = _make_app()
        ConfigManager.init_app(app)
        assert app.config.get("DEBUG") is False
        assert app.config.get("SECRET_KEY") == "a-real-secret"

    def test_production_refuses_to_start_without_a_secret(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        monkeypatch.setenv("SPLENT_ENV", "prod")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            ConfigManager.init_app(_make_app())

    def test_test_env_loads_testing(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        monkeypatch.setenv("SPLENT_ENV", "test")
        app = _make_app()
        ConfigManager.init_app(app)
        assert app.config.get("TESTING") is True

    def test_an_explicit_profile_beats_the_environment(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        monkeypatch.setenv("SPLENT_ENV", "prod")
        app = _make_app()
        ConfigManager.init_app(app, "testing")
        assert app.config.get("TESTING") is True

    def test_flask_env_is_the_fallback(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        monkeypatch.delenv("SPLENT_ENV", raising=False)
        monkeypatch.setenv("FLASK_ENV", "testing")
        app = _make_app()
        ConfigManager.init_app(app)
        assert app.config.get("TESTING") is True

    def test_timezone_set(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        app = _make_app()
        ConfigManager.init_app(app, "development")
        assert "TIMEZONE" in app.config

    def test_timezone_respects_env_var(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_product_xyz")
        monkeypatch.setenv("TIMEZONE", "America/New_York")
        app = _make_app()
        ConfigManager.init_app(app, "development")
        assert app.config["TIMEZONE"] == "America/New_York"
