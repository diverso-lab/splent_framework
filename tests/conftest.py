"""
Shared pytest fixtures for splent_framework tests.

- `flask_app`   → minimal Flask app with SQLite in-memory, no features loaded
- `app_ctx`     → pushes an app context (needed for db/session operations)
- `client`      → Flask test client
"""
import pytest
from flask import Flask
from splent_framework.db import db as _db


@pytest.fixture(scope="function")
def flask_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SECRET_KEY"] = "test-secret"
    _db.init_app(app)
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope="function")
def client(flask_app):
    return flask_app.test_client()
