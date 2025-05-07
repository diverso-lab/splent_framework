import pytest
from splent_cli.utils.dynamic_imports import get_db

db = get_db()

@pytest.fixture(scope="function")
def clean_database():
    db.session.remove()
    db.drop_all()
    db.create_all()
    yield
    db.session.remove()
    db.drop_all()
    db.create_all()
