from typing import Any


class BaseService:
    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def create(self, **kwargs) -> Any:
        return self.repository.create(**kwargs)

    def count(self) -> int:
        return self.repository.count()

    def get_by_id(self, id: int) -> Any:
        return self.repository.get_by_id(id)

    def get_or_404(self, id: int) -> Any:
        return self.repository.get_or_404(id)

    def update(self, id: int, **kwargs) -> Any:
        return self.repository.update(id, **kwargs)

    def delete(self, id: int) -> Any:
        return self.repository.delete(id)
