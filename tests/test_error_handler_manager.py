"""
Tests for ErrorHandlerManager.
"""

import types
import pytest
from unittest.mock import MagicMock, patch
from flask import Flask
from splent_framework.managers.error_handler_manager import ErrorHandlerManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


# ---------------------------------------------------------------------------
# _import_custom_handlers
# ---------------------------------------------------------------------------

class TestImportCustomHandlers:
    def test_returns_none_when_module_not_found(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_app_xyz")
        manager = ErrorHandlerManager.__new__(ErrorHandlerManager)
        manager.app = _make_app()
        result = manager._import_custom_handlers()
        assert result is None

    def test_returns_module_when_found(self, monkeypatch):
        fake_mod = types.ModuleType("fake_errors")
        fake_mod.handle_404 = lambda app, e: ("custom 404", 404)
        monkeypatch.setenv("SPLENT_APP", "fake_app")
        with patch("importlib.import_module", return_value=fake_mod):
            manager = ErrorHandlerManager.__new__(ErrorHandlerManager)
            manager.app = _make_app()
            result = manager._import_custom_handlers()
        assert result is fake_mod


# ---------------------------------------------------------------------------
# _get_handler
# ---------------------------------------------------------------------------

class TestGetHandler:
    def _manager_with_handlers(self, handlers_dict):
        mod = types.SimpleNamespace(**handlers_dict)
        manager = ErrorHandlerManager.__new__(ErrorHandlerManager)
        manager.app = _make_app()
        manager.custom_handlers = mod
        return manager

    def test_returns_custom_handler_when_present(self):
        custom = lambda app, e: ("custom", 404)
        manager = self._manager_with_handlers({"handle_404": custom})
        result = manager._get_handler("handle_404", lambda a, e: ("default", 404))
        assert result is custom

    def test_returns_fallback_when_custom_missing(self):
        fallback = lambda app, e: ("default", 404)
        manager = self._manager_with_handlers({})
        result = manager._get_handler("handle_404", fallback)
        assert result is fallback

    def test_returns_fallback_when_no_custom_handlers_module(self):
        fallback = lambda app, e: ("default", 500)
        manager = ErrorHandlerManager.__new__(ErrorHandlerManager)
        manager.app = _make_app()
        manager.custom_handlers = None
        result = manager._get_handler("handle_500", fallback)
        assert result is fallback


# ---------------------------------------------------------------------------
# register_error_handlers + default handlers
# ---------------------------------------------------------------------------

class TestRegisterErrorHandlers:
    def test_registers_500_handler(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_xyz")
        app = _make_app()
        manager = ErrorHandlerManager(app)
        manager.register_error_handlers()
        assert 500 in app.error_handler_spec[None]

    def test_registers_404_handler(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_xyz")
        app = _make_app()
        manager = ErrorHandlerManager(app)
        manager.register_error_handlers()
        assert 404 in app.error_handler_spec[None]

    def test_registers_401_handler(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_xyz")
        app = _make_app()
        manager = ErrorHandlerManager(app)
        manager.register_error_handlers()
        assert 401 in app.error_handler_spec[None]

    def test_registers_400_handler(self, monkeypatch):
        monkeypatch.setenv("SPLENT_APP", "nonexistent_xyz")
        app = _make_app()
        manager = ErrorHandlerManager(app)
        manager.register_error_handlers()
        assert 400 in app.error_handler_spec[None]
