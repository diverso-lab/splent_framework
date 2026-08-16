# splent_framework/nav/nav_registry.py
#
# SPL navigation registry. Each CONTENT feature declares its public main-nav
# entry in init_feature() via register_nav_item(); the menu is therefore
# *composed from the features actually selected in the product's derivation*,
# not hardcoded. The theme reads get_nav_items() and layers the admin "Menus"
# editor's runtime overrides (order / visibility / label) and custom links on
# top. Remove a feature (re-derive) and its entry disappears on its own; add
# one and it shows up — that is the SPL variability surfacing in the UI.
#
# Populated once at app startup during feature registration; read-only during
# request handling. Registration is idempotent by key, so a second create_app()
# (tests, reload) does not duplicate entries. Not thread-safe for writes — do
# not call register_nav_item() from request handlers.

_nav_items: dict = {}


def register_nav_item(
    key: str, label: str, href: str, order: int = 100, icon=None, children=None
) -> None:
    """Declare one entry in the public main navigation (opt-in, per feature).

    Args:
        key: stable identifier (e.g. "projects"); used to reconcile runtime
            overrides across re-derivations. Unique per feature.
        label: default human label (translated at render time via gettext).
        href: public URL/path the entry points to (e.g. "/projects").
        order: lower sorts first when no runtime override exists.
        icon: optional feather icon name.
        children: optional sub-entries rendered as a dropdown under the
            entry: a list of ``{"label", "href"}`` dicts, or a zero-argument
            callable returning that list. A callable is resolved on every
            render, which is how an entry lists content that changes at
            runtime (the editions of an event, the categories of a blog)
            without re-registering. Empty means a plain link.
    """
    _nav_items[key] = {
        "key": key,
        "label": label,
        "href": href,
        "order": order,
        "icon": icon,
        "children": children,
    }


def resolve_children(item: dict) -> list:
    """The rendered sub-entries of a nav item: ``[{"label", "href"}, …]``.

    Resolves a callable ``children`` at call time and never raises: a
    feature whose lookup fails (no database yet, a table missing) renders a
    plain link rather than breaking every page's header.
    """
    children = item.get("children")
    if callable(children):
        try:
            children = children()
        except Exception:
            children = []
    out = []
    for child in children or []:
        if not isinstance(child, dict):
            continue
        label = child.get("label")
        href = child.get("href")
        if label and href:
            out.append({"label": label, "href": href, "current": bool(child.get("current"))})
    return out


def get_nav_items() -> list:
    """All declared nav entries, sorted by (order, label)."""
    return sorted(
        _nav_items.values(), key=lambda i: (i.get("order", 100), i.get("label", ""))
    )


def clear_nav_items() -> None:
    """Drop all entries. Intended for test teardown."""
    _nav_items.clear()
