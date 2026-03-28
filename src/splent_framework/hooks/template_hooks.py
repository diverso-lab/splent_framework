# splent_framework/template_hooks.py
#
# NOTE: _hooks is a module-level registry populated once at app startup
# (during feature registration) and read-only during request handling.
# It is NOT thread-safe for concurrent writes; do not call
# register_template_hook() from request handlers or background threads.

_hooks: dict[str, list] = {}


def register_template_hook(name: str, func) -> None:
    """Append a callback to a named hook slot (additive)."""
    _hooks.setdefault(name, []).append(func)


def replace_template_hook(name: str, func) -> None:
    """Replace ALL existing callbacks for a named hook slot.

    Used by refinement features to override a base feature's hook content.
    """
    _hooks[name] = [func]


def remove_template_hook(name: str, func) -> None:
    """Remove a specific callback from a hook slot."""
    if name in _hooks:
        _hooks[name] = [f for f in _hooks[name] if f is not func]


def get_template_hooks(name: str) -> list:
    return _hooks.get(name, [])


def clear_hooks() -> None:
    """Remove all registered hooks. Intended for use in test teardown."""
    _hooks.clear()
