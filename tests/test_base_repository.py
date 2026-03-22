"""
Tests for splent_framework.repositories.BaseRepository

Uses SQLite in-memory via a minimal Flask app.
Covers all CRUD methods and edge cases.
"""
import pytest
from flask import Flask
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from splent_framework.db import db as _db
from splent_framework.repositories.BaseRepository import BaseRepository


# ---------------------------------------------------------------------------
# Minimal model for testing
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class Widget(_db.Model):
    __tablename__ = "widgets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(50), default="red")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def app():
    application = Flask(__name__)
    application.config["TESTING"] = True
    application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    application.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    application.config["SECRET_KEY"] = "test"
    _db.init_app(application)
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture
def repo(app):
    return BaseRepository(Widget)


@pytest.fixture
def one_widget(repo):
    return repo.create(name="Gear", color="blue")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreate:
    def test_creates_and_returns_instance(self, repo):
        w = repo.create(name="Bolt", color="silver")
        assert w.id is not None
        assert w.name == "Bolt"
        assert w.color == "silver"

    def test_create_without_commit_flushes(self, repo):
        w = repo.create(name="Nut", commit=False)
        assert w.id is not None  # flushed → id assigned

    def test_multiple_creates_get_different_ids(self, repo):
        w1 = repo.create(name="A")
        w2 = repo.create(name="B")
        assert w1.id != w2.id


class TestGetById:
    def test_returns_existing(self, repo, one_widget):
        result = repo.get_by_id(one_widget.id)
        assert result is not None
        assert result.name == "Gear"

    def test_returns_none_for_missing(self, repo):
        assert repo.get_by_id(9999) is None


class TestGetByColumn:
    def test_finds_matching_records(self, repo):
        repo.create(name="X", color="green")
        repo.create(name="Y", color="green")
        repo.create(name="Z", color="red")
        results = repo.get_by_column("color", "green")
        assert len(results) == 2

    def test_returns_empty_list_when_none_match(self, repo):
        repo.create(name="A", color="blue")
        assert repo.get_by_column("color", "purple") == []


class TestGetOr404:
    def test_returns_record_when_found(self, repo, one_widget, app):
        with app.test_request_context():
            result = repo.get_or_404(one_widget.id)
            assert result.id == one_widget.id

    def test_raises_404_when_not_found(self, repo, app):
        from werkzeug.exceptions import NotFound
        with app.test_request_context():
            with pytest.raises(NotFound):
                repo.get_or_404(9999)


class TestUpdate:
    def test_updates_existing_record(self, repo, one_widget):
        updated = repo.update(one_widget.id, name="Updated Gear", color="gold")
        assert updated.name == "Updated Gear"
        assert updated.color == "gold"

    def test_returns_none_for_missing_id(self, repo):
        assert repo.update(9999, name="X") is None

    def test_persists_to_db(self, repo, one_widget):
        repo.update(one_widget.id, name="Persisted")
        fetched = repo.get_by_id(one_widget.id)
        assert fetched.name == "Persisted"


class TestDelete:
    def test_deletes_existing(self, repo, one_widget):
        result = repo.delete(one_widget.id)
        assert result is True
        assert repo.get_by_id(one_widget.id) is None

    def test_returns_false_for_missing_id(self, repo):
        assert repo.delete(9999) is False


class TestDeleteByColumn:
    def test_deletes_all_matching(self, repo):
        repo.create(name="A", color="yellow")
        repo.create(name="B", color="yellow")
        repo.create(name="C", color="blue")
        result = repo.delete_by_column("color", "yellow")
        assert result is True
        assert repo.get_by_column("color", "yellow") == []
        assert len(repo.get_by_column("color", "blue")) == 1

    def test_returns_false_when_nothing_matches(self, repo):
        assert repo.delete_by_column("color", "nonexistent") is False


class TestCount:
    def test_zero_when_empty(self, repo):
        assert repo.count() == 0

    def test_counts_all_records(self, repo):
        repo.create(name="A")
        repo.create(name="B")
        repo.create(name="C")
        assert repo.count() == 3

    def test_decreases_after_delete(self, repo, one_widget):
        assert repo.count() == 1
        repo.delete(one_widget.id)
        assert repo.count() == 0
