"""
Tests for ConfigManager.init_app — verifies it returns the manager instance.
"""
import pytest
from flask import Flask
from splent_framework.managers.config_manager import ConfigManager


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SPLENT_APP", "nonexistent_app")
    app = Flask(__name__)
    return app


class TestConfigManagerInitApp:

    def test_init_app_returns_manager_instance(self, app):
        manager = ConfigManager.init_app(app, config_name="development")
        assert manager is not None
        assert isinstance(manager, ConfigManager)

    def test_init_app_loads_config(self, app):
        ConfigManager.init_app(app, config_name="development")
        # Default config should set DEBUG
        assert "DEBUG" in app.config
