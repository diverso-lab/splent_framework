from abc import ABC, abstractmethod

from sqlalchemy.exc import IntegrityError

from splent_framework.db import db


class SeederError(RuntimeError):
    """Raised when a seed operation fails."""


class BaseSeeder(ABC):
    priority = 10

    def __init__(self):
        self.db = db

    @abstractmethod
    def run(self):
        """Execute the seed logic. Must be implemented by subclasses."""

    def seed(self, data):
        """
        Insert a list of model objects and return them with IDs assigned.

        :param data: List of model instances of the same type.
        :return: The same list after commit (IDs populated).
        :raises SeederError: If the DB insert fails due to integrity violations.
        """
        if not data:
            return []

        model = type(data[0])
        if not all(isinstance(obj, model) for obj in data):
            raise ValueError("All objects in data must be of the same model type.")

        try:
            self.db.session.add_all(data)
            self.db.session.commit()
        except IntegrityError as e:
            self.db.session.rollback()
            raise SeederError(
                f"Failed to insert data into `{model.__tablename__}`: {e}"
            ) from e

        return data
