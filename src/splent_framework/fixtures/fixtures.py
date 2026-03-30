import pytest
from sqlalchemy import text
from splent_framework.db import db
from splent_framework.utils.app_loader import get_create_app_in_testing_mode


def _reset_db():
    """Drop and recreate all tables. Disables FK checks for MariaDB."""
    db.session.remove()
    with db.engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        db.metadata.drop_all(bind=conn)
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        db.metadata.create_all(bind=conn)
        conn.commit()


@pytest.fixture(scope="session")
def test_app():
    """
    Creates and initializes the Flask app for the test session.
    Drops and creates all tables once per session.
    """
    app = get_create_app_in_testing_mode()
    with app.app_context():
        _reset_db()
    yield app


@pytest.fixture(scope="function")
def test_client(test_app):
    """
    Provides a test client with a clean database for each test.
    Tables are dropped and recreated before the test runs.
    """
    with test_app.app_context():
        _reset_db()
    with test_app.test_client() as client:
        yield client


@pytest.fixture(scope="module")
def test_client_module(test_app):
    """
    Shared test client for the entire module.
    Resets the database once at the start of the module.
    Tests within the module share database state.
    """
    with test_app.app_context():
        _reset_db()

        with test_app.test_client() as client:
            yield client


@pytest.fixture(scope="function")
def clean_database(test_app):
    """
    Manually resets the database within a test.
    Combine with test_client_module when you need a selective
    reset inside a module-scoped session.
    """
    with test_app.app_context():
        _reset_db()
        yield
