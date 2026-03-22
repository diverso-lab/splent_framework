"""
Tests for context_manager.build_jinja_context.
"""

import pytest
from flask import Flask
from splent_framework.context.context_manager import build_jinja_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _app():
    app = Flask(__name__)
    app.context_processors = []
    return app


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

class TestBuildJinjaContext:
    def test_returns_base_context_unchanged_when_no_processors(self):
        app = _app()
        result = build_jinja_context(app, {"user": "alice"})
        assert result == {"user": "alice"}

    def test_does_not_mutate_base_context(self):
        app = _app()
        base = {"x": 1}
        build_jinja_context(app, base)
        assert base == {"x": 1}

    def test_processor_result_merged_into_context(self):
        app = _app()
        app.context_processors = [lambda a: {"greeting": "hello"}]
        result = build_jinja_context(app, {})
        assert result["greeting"] == "hello"

    def test_multiple_processors_all_merged(self):
        app = _app()
        app.context_processors = [
            lambda a: {"a": 1},
            lambda a: {"b": 2},
        ]
        result = build_jinja_context(app, {})
        assert result["a"] == 1
        assert result["b"] == 2

    def test_processor_overrides_base_key(self):
        app = _app()
        app.context_processors = [lambda a: {"key": "new"}]
        result = build_jinja_context(app, {"key": "old"})
        assert result["key"] == "new"

    def test_base_context_keys_preserved_when_not_overridden(self):
        app = _app()
        app.context_processors = [lambda a: {"extra": True}]
        result = build_jinja_context(app, {"original": 42})
        assert result["original"] == 42
        assert result["extra"] is True

    def test_processor_returning_non_dict_is_skipped(self):
        app = _app()
        app.context_processors = [lambda a: "not-a-dict"]
        result = build_jinja_context(app, {"safe": True})
        assert result == {"safe": True}

    def test_processor_raising_exception_is_skipped(self):
        app = _app()
        app.context_processors = [
            lambda a: (_ for _ in ()).throw(RuntimeError("boom")),
            lambda a: {"after": "ok"},
        ]
        result = build_jinja_context(app, {})
        assert result.get("after") == "ok"

    def test_empty_base_context_with_no_processors_returns_empty(self):
        app = _app()
        assert build_jinja_context(app, {}) == {}

    def test_works_when_context_processors_attribute_absent(self):
        """app objects without context_processors should behave like an empty list."""
        app = Flask(__name__)  # no context_processors attribute
        result = build_jinja_context(app, {"k": "v"})
        assert result == {"k": "v"}
