"""
Presentation helpers for form handling in routes.

These helpers live in the framework (not in BaseService) because they deal
with HTTP concerns: flash messages, redirects, and template rendering.
Services return data; routes use these helpers to turn data into responses.
"""

from flask import flash, redirect, render_template, url_for


def form_success(endpoint: str, message: str, category: str = "success", **url_kwargs):
    """Flash a success message and redirect."""
    flash(message, category)
    return redirect(url_for(endpoint, **url_kwargs))


def form_error(template: str, form, errors: dict | None = None, **context):
    """Flash field errors and re-render the form template."""
    for field, messages in (errors or {}).items():
        for msg in messages:
            flash(f"{field}: {msg}", "error")
    return render_template(template, form=form, **context)
