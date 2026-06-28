# splent_framework/template_hooks.py
#
# NOTE: _hooks is a module-level registry populated once at app startup
# (during feature registration) and read-only during request handling.
# It is NOT thread-safe for concurrent writes; do not call
# register_template_hook() from request handlers or background threads.

# Each slot holds (order, func) pairs; get_template_hooks returns the funcs
# sorted by order (lower first), so slots like "home.section" compose features
# in a deterministic order regardless of feature load order.
_hooks: dict[str, list] = {}


def register_template_hook(name: str, func, order: int = 100) -> None:
    """Append a callback to a named hook slot (additive).

    order: lower renders first within the slot (default 100).
    """
    _hooks.setdefault(name, []).append((order, func))


def replace_template_hook(name: str, func, order: int = 100) -> None:
    """Replace ALL existing callbacks for a named hook slot.

    Used by refinement features to override a base feature's hook content.
    """
    _hooks[name] = [(order, func)]


def remove_template_hook(name: str, func) -> None:
    """Remove a specific callback from a hook slot."""
    if name in _hooks:
        _hooks[name] = [(o, f) for (o, f) in _hooks[name] if f is not func]


def get_template_hooks(name: str) -> list:
    """Callbacks for a slot, ordered by their registration `order`."""
    return [f for _, f in sorted(_hooks.get(name, []), key=lambda pair: pair[0])]


def clear_hooks() -> None:
    """Remove all registered hooks. Intended for use in test teardown."""
    _hooks.clear()
