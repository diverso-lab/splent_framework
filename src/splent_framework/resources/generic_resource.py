from typing import Any

from flask import request
from flask_restful import Resource
from sqlalchemy import select

from splent_framework.db import db


class GenericResource(Resource):
    def __init__(self, model: type, serializer: Any) -> None:
        self.model = model
        self.model_name = model.__name__
        self.serializer = serializer

    def get(self, id: int | None = None) -> tuple:
        if id is not None:
            item = db.session.get(self.model, id)
            if not item:
                return {"message": f"{self.model_name} not found"}, 404
            return self.serializer.serialize(item), 200

        items = db.session.scalars(select(self.model)).all()
        return {"items": [self.serializer.serialize(i) for i in items]}, 200

    def post(self) -> tuple:
        data = request.get_json()
        if not data:
            return {"message": "No input data provided"}, 400

        if self.serializer.serialization_fields:
            data = {k: v for k, v in data.items() if k in self.serializer.serialization_fields}

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

        for key, value in data.items():
            if key in self.serializer.serialization_fields:
                setattr(item, key, value)
        db.session.commit()
        return self.serializer.serialize(item), 200

    def delete(self, id: int) -> tuple:
        item = db.session.get(self.model, id)
        if not item:
            return {"message": f"{self.model_name} not found"}, 404
        db.session.delete(item)
        db.session.commit()
        # 204 No Content must not include a body
        return "", 204


def create_resource(model: type, serialization_fields: list[str] | None = None) -> type:
    class ConcreteResource(GenericResource):
        def __init__(self):
            super().__init__(model, serialization_fields)

    return ConcreteResource
