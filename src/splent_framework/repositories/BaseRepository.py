from typing import Any, Generic, NoReturn, TypeVar

from sqlalchemy import func, select

from splent_framework.db import db

T = TypeVar("T")


class BaseRepository(Generic[T]):
    def __init__(self, model: type[T]):
        self.model = model
        self.session = db.session

    def create(self, commit: bool = True, **kwargs) -> T:
        instance: T = self.model(**kwargs)
        self.session.add(instance)
        if commit:
            self.session.commit()
        else:
            self.session.flush()
        return instance

    def get_by_id(self, id: int) -> T | None:
        return self.session.get(self.model, id)

    def get_by_column(self, column_name: str, value: Any) -> list[T]:
        stmt = select(self.model).where(
            getattr(self.model, column_name) == value
        )
        return list(self.session.scalars(stmt).all())

    def get_or_404(self, id: int) -> T | NoReturn:
        return db.get_or_404(self.model, id)

    def update(self, id: int, **kwargs) -> T | None:
        instance = self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            self.session.commit()
            return instance
        return None

    def delete(self, id: int) -> bool:
        instance = self.get_by_id(id)
        if instance:
            self.session.delete(instance)
            self.session.commit()
            return True
        return False

    def delete_by_column(self, column_name: str, value: Any) -> bool:
        instances = self.get_by_column(column_name, value)
        if not instances:
            return False
        for instance in instances:
            self.session.delete(instance)
        self.session.commit()
        return True

    def count(self) -> int:
        return self.session.scalar(
            select(func.count()).select_from(self.model)
        ) or 0
