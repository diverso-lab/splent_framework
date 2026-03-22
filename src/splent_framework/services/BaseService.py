from typing import Any

from flask import flash, redirect, render_template, url_for


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

    def handle_service_response(
        self,
        result: Any,
        errors: dict | None,
        success_url_redirect: str,
        success_msg: str,
        error_template: str,
        form: Any,
    ) -> Any:
        if result:
            flash(success_msg, "success")
            return redirect(url_for(success_url_redirect))

        for error_field, error_messages in (errors or {}).items():
            for error_message in error_messages:
                flash(f"{error_field}: {error_message}", "error")
        return render_template(error_template, form=form)
