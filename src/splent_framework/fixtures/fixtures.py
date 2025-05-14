import pytest
from splent_framework.db import db
from splent_cli.utils.dynamic_imports import get_create_app_in_testing_mode


@pytest.fixture(scope="session")
def test_app():
    """
    Creates and initializes the Flask app for the test session.
    Drops and creates all tables once per session.
    """
    app = get_create_app_in_testing_mode()
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app


@pytest.fixture(scope="function")
def test_client(test_app):
    """
    Provides a test client and resets the DB before and after each test.
    This ensures test isolation.
    """
    with test_app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
    with test_app.test_client() as client:
        yield client
    with test_app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()


@pytest.fixture(scope="module")
def test_client_module(test_app):
    """
    Test client compartido para todo el módulo. 
    Limpia la DB solo al principio y al final del módulo.
    """
    with test_app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()

        with test_app.test_client() as client:
            yield client

        db.session.remove()
        db.drop_all()
        db.create_all()


@pytest.fixture(scope="function")
def clean_database(test_app):
    """
    Provides a manual DB reset during a test when needed.
    Useful if you want to control when the DB is cleaned.
    """
    with test_app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()
        db.create_all()
