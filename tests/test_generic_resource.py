"""
Tests for GenericResource — verifies both Serializer objects and plain
field lists work correctly as the serializer parameter.
"""
import json
import pytest
from flask import Flask

flask_restful = pytest.importorskip("flask_restful")
Api = flask_restful.Api

from splent_framework.db import db as _db
from splent_framework.resources.generic_resource import GenericResource, create_resource


# ---------------------------------------------------------------------------
# Model fixture
# ---------------------------------------------------------------------------

class Item(_db.Model):
    __tablename__ = "item"
    id = _db.Column(_db.Integer, primary_key=True)
    name = _db.Column(_db.String(100))
    secret = _db.Column(_db.String(100))


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    _db.init_app(app)
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Tests: create_resource with field list
# ---------------------------------------------------------------------------

class TestCreateResourceWithFieldList:

    def test_post_filters_by_allowed_fields(self, app, client):
        api = Api(app)
        ResourceClass = create_resource(Item, ["name"])
        api.add_resource(ResourceClass, "/items", "/items/<int:id>")

        resp = client.post("/items", json={"name": "test", "secret": "hidden"})
        assert resp.status_code == 201

    def test_get_returns_allowed_fields(self, app, client):
        api = Api(app)
        ResourceClass = create_resource(Item, ["id", "name"])
        api.add_resource(ResourceClass, "/items", "/items/<int:id>")

        with app.app_context():
            item = Item(name="test", secret="hidden")
            _db.session.add(item)
            _db.session.commit()
            item_id = item.id

        resp = client.get(f"/items/{item_id}")
        data = resp.get_json()
        assert "name" in data
        assert "secret" not in data

    def test_get_list_returns_items(self, app, client):
        api = Api(app)
        ResourceClass = create_resource(Item, ["id", "name"])
        api.add_resource(ResourceClass, "/items", "/items/<int:id>")

        with app.app_context():
            _db.session.add(Item(name="a", secret="s"))
            _db.session.add(Item(name="b", secret="s"))
            _db.session.commit()

        resp = client.get("/items")
        data = resp.get_json()
        assert len(data["items"]) == 2

    def test_put_updates_allowed_fields(self, app, client):
        api = Api(app)
        ResourceClass = create_resource(Item, ["name"])
        api.add_resource(ResourceClass, "/items", "/items/<int:id>")

        with app.app_context():
            item = Item(name="old", secret="keep")
            _db.session.add(item)
            _db.session.commit()
            item_id = item.id

        resp = client.put(f"/items/{item_id}", json={"name": "new", "secret": "changed"})
        assert resp.status_code == 200

        with app.app_context():
            updated = _db.session.get(Item, item_id)
            assert updated.name == "new"
            assert updated.secret == "keep"  # not in allowed fields, should not change

    def test_delete_removes_item(self, app, client):
        api = Api(app)
        ResourceClass = create_resource(Item, ["name"])
        api.add_resource(ResourceClass, "/items", "/items/<int:id>")

        with app.app_context():
            item = Item(name="gone", secret="s")
            _db.session.add(item)
            _db.session.commit()
            item_id = item.id

        resp = client.delete(f"/items/{item_id}")
        assert resp.status_code == 204


class TestCreateResourceWithNone:

    def test_post_with_no_fields_accepts_all(self, app, client):
        api = Api(app)
        ResourceClass = create_resource(Item)
        api.add_resource(ResourceClass, "/items", "/items/<int:id>")

        resp = client.post("/items", json={"name": "test", "secret": "visible"})
        assert resp.status_code == 201

    def test_get_with_no_fields_returns_all_columns(self, app, client):
        api = Api(app)
        ResourceClass = create_resource(Item)
        api.add_resource(ResourceClass, "/items", "/items/<int:id>")

        with app.app_context():
            item = Item(name="test", secret="visible")
            _db.session.add(item)
            _db.session.commit()
            item_id = item.id

        resp = client.get(f"/items/{item_id}")
        data = resp.get_json()
        assert "name" in data
        assert "secret" in data


class TestCreateResourceWithSerializer:

    def test_works_with_serializer_object(self, app, client):
        from splent_framework.serialisers.serializer import Serializer

        api = Api(app)
        ser = Serializer({"name": "name"})

        class ItemResource(GenericResource):
            def __init__(self):
                super().__init__(Item, ser)

        api.add_resource(ItemResource, "/items", "/items/<int:id>")

        with app.app_context():
            item = Item(name="test", secret="hidden")
            _db.session.add(item)
            _db.session.commit()
            item_id = item.id

        resp = client.get(f"/items/{item_id}")
        data = resp.get_json()
        assert data == {"name": "test"}
