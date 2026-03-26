from typing import Any

from flask import request
from flask_restful import Resource
from sqlalchemy import select

from splent_framework.db import db


class GenericResource(Resource):
    """REST resource backed by a SQLAlchemy model.

    Accepts either a ``Serializer`` instance (full control over serialization)
    or a plain list of allowed field names (convenience shortcut).
    """

    def __init__(self, model: type, serializer: Any = None) -> None:
        self.model = model
        self.model_name = model.__name__

        # Accept a Serializer object or a plain list of field names
        if serializer is None or isinstance(serializer, (list, tuple)):
            self._allowed_fields: list[str] | None = serializer
            self._serializer = None
        else:
            self._allowed_fields = None
            self._serializer = serializer

    def _serialize(self, item) -> dict:
        if self._serializer:
            return self._serializer.serialize(item)
        fields = self._allowed_fields or [
            c.name for c in self.model.__table__.columns
        ]
        return {f: getattr(item, f, None) for f in fields}

    def get(self, id: int | None = None) -> tuple:
        if id is not None:
            item = db.session.get(self.model, id)
            if not item:
                return {"message": f"{self.model_name} not found"}, 404
            return self._serialize(item), 200

        items = db.session.scalars(select(self.model)).all()
        return {"items": [self._serialize(i) for i in items]}, 200

    def post(self) -> tuple:
        data = request.get_json()
        if not data:
            return {"message": "No input data provided"}, 400

        if self._allowed_fields:
            data = {k: v for k, v in data.items() if k in self._allowed_fields}
        elif self._serializer and self._serializer.serialization_fields:
            data = {k: v for k, v in data.items() if k in self._serializer.serialization_fields}

        item = self.model(**data)
        db.session.add(item)
        db.session.commit()
        return {"message": f"{self.model_name} created successfully", "id": item.id}, 201

    def put(self, id: int) -> tuple:
        item = db.session.get(self.model, id)
        if not item:
            return {"message": f"{self.model_name} not found"}, 404

        data = request.get_json()
        if not data:
            return {"message": "No input data provided"}, 400

        allowed = self._allowed_fields
        if allowed is None and self._serializer and self._serializer.serialization_fields:
            allowed = list(self._serializer.serialization_fields)

        for key, value in data.items():
            if allowed is None or key in allowed:
                setattr(item, key, value)
        db.session.commit()
        return self._serialize(item), 200

    def delete(self, id: int) -> tuple:
        item = db.session.get(self.model, id)
        if not item:
            return {"message": f"{self.model_name} not found"}, 404
        db.session.delete(item)
        db.session.commit()
        return "", 204


def create_resource(model: type, serialization_fields: list[str] | None = None) -> type:
    """Factory that returns a GenericResource subclass for a given model."""
    class ConcreteResource(GenericResource):
        def __init__(self):
            super().__init__(model, serialization_fields)

    return ConcreteResource
