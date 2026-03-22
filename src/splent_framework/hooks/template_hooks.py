# splent_framework/template_hooks.py
#
# NOTE: _hooks is a module-level registry populated once at app startup
# (during feature registration) and read-only during request handling.
# It is NOT thread-safe for concurrent writes; do not call
# register_template_hook() from request handlers or background threads.

_hooks: dict[str, list] = {}


def register_template_hook(name: str, func) -> None:
    _hooks.setdefault(name, []).append(func)


def get_template_hooks(name: str) -> list:
    return _hooks.get(name, [])


def clear_hooks() -> None:
    """Remove all registered hooks. Intended for use in test teardown."""
    _hooks.clear()
