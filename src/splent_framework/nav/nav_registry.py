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
    key: str, label: str, href: str, order: int = 100, icon=None
) -> None:
    """Declare one entry in the public main navigation (opt-in, per feature).

    Args:
        key: stable identifier (e.g. "projects"); used to reconcile runtime
            overrides across re-derivations. Unique per feature.
        label: default human label (translated at render time via gettext).
        href: public URL/path the entry points to (e.g. "/projects").
        order: lower sorts first when no runtime override exists.
        icon: optional feather icon name.
    """
    _nav_items[key] = {
        "key": key,
        "label": label,
        "href": href,
        "order": order,
        "icon": icon,
    }


def get_nav_items() -> list:
    """All declared nav entries, sorted by (order, label)."""
    return sorted(
        _nav_items.values(), key=lambda i: (i.get("order", 100), i.get("label", ""))
    )


def clear_nav_items() -> None:
    """Drop all entries. Intended for test teardown."""
    _nav_items.clear()
