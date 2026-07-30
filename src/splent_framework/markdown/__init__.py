"""Markdown rendering, shared by every feature that stores prose.

A content feature renders a stored body with::

    from splent_framework.markdown import render_markdown

    html = render_markdown(page.body_md)

and gets the same dialect, the same code highlighting and, most
importantly, the same allowlist as every other feature.
"""

from splent_framework.markdown.render import (
    ALLOWED_ATTRIBUTES,
    ALLOWED_TAGS,
    TOKEN_PREFIX,
    build_renderer,
    highlight_code,
    render_markdown,
)

__all__ = [
    "ALLOWED_ATTRIBUTES",
    "ALLOWED_TAGS",
    "TOKEN_PREFIX",
    "build_renderer",
    "highlight_code",
    "render_markdown",
]
