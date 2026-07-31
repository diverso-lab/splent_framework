# splent_framework/settings/settings_schema.py
#
# SPL feature-settings schema registry — the generic way to make any feature
# that injects UI configurable from the admin.
#
# A feature DECLARES its admin-editable settings (a typed schema) via
# register_settings() in init_feature(). The `settings` feature renders ONE
# generic admin panel for every declared schema and persists values through
# SettingsService. No per-feature panel code, no ad-hoc config modules: declare
# the schema, get a panel + typed reads.
#
# Setting keys are namespaced as "<feature>_<field>" automatically, so features
# never collide. Cleared per app at feature-load (like the nav/asset registries).

_schemas: dict = {}

FIELD_TYPES = ("bool", "int", "text", "color", "select")


def register_settings(
    feature: str, title: str, fields: list, icon: str = "sliders"
) -> None:
    """Declare a feature's admin-editable settings.

    Args:
        feature: stable key, e.g. "slider" (also the panel URL segment and the
            setting-key namespace).
        title: human title shown in the panel/sidebar, e.g. "Slider".
        fields: list of dicts ``{key, type, default, label, help?, options?,
            env?}``. ``type`` in bool/int/text/color/select. For select,
            provide ``options`` as a list of ``(value, label)`` pairs.
            ``env`` names the environment variable this field shadows, and
            defaults to ``<FEATURE>_<KEY>`` uppercased. State it whenever the
            variable is not named after the feature: the theme's ``site_name``
            field shadows ``SITE_NAME``, not ``THEME_SITE_NAME``.
        icon: feather icon name for the sidebar entry.

    A field should shadow a variable the feature also declares under
    ``[tool.splent.config]`` in its pyproject. The two are the same setting
    reached at different moments: the environment is what a deployment
    decided before the app started, the panel is what somebody changed
    afterwards without asking anybody.
    """
    _schemas[feature] = {
        "feature": feature,
        "title": title,
        "icon": icon,
        "fields": list(fields),
    }


def get_schemas() -> list:
    """All declared schemas, sorted by title."""
    return sorted(_schemas.values(), key=lambda s: s["title"].lower())


def get_schema(feature: str):
    return _schemas.get(feature)


def clear_settings_schemas() -> None:
    _schemas.clear()


def setting_key(feature: str, field_key: str) -> str:
    """The namespaced SettingsService key for a feature field."""
    return f"{feature}_{field_key}"


def env_key(feature: str, field: dict) -> str:
    """The environment variable a field shadows.

    Explicit when the field says so, because a variable is rarely named
    after the feature that happens to expose it.
    """
    return field.get("env") or f"{feature}_{field['key']}".upper()


def _stored_values() -> dict:
    """Every stored setting, read once per request.

    get_config asks for a whole schema at a time and is called from template
    hooks, so a query per field would mean a page rendering the nav paying
    for one round trip per switch on it. The store is small and read on
    nearly every request, so it is fetched whole and memoised on ``g``.
    """
    from splent_framework.services.service_locator import service_proxy

    try:
        from flask import g, has_request_context
    except ImportError:  # pragma: no cover - Flask is always present
        return {}

    if has_request_context() and hasattr(g, "_splent_settings"):
        return g._splent_settings

    try:
        values = service_proxy("SettingsService").all_dict()
    except Exception:
        # No settings feature installed, or no database yet. Every caller
        # falls back to the environment, which is where the value lived
        # before any of this existed.
        values = {}

    if has_request_context():
        g._splent_settings = values
    return values


def _cast(field: dict, raw):
    """Coerce a stored raw string to the field's type, falling back to default."""
    t = field.get("type")
    default = field.get("default")
    if t == "bool":
        if raw is None:
            return default in (True, "1", 1)
        return raw in (True, "1", 1)
    if t == "int":
        try:
            return int(raw)
        except (TypeError, ValueError):
            try:
                return int(default)
            except (TypeError, ValueError):
                return 0
    if t == "color":
        import re

        if raw and re.match(r"^#[0-9a-fA-F]{3,8}$", raw):
            return raw
        return default if default else "#000000"
    # text / select
    return raw if raw not in (None, "") else (default if default is not None else "")


def get_config(feature: str) -> dict:
    """Typed current values for a feature's settings, keyed by the SHORT field
    key (e.g. ``{"autoplay": True, "interval": 6}``).

    Three places hold an answer, and they are consulted in the order of how
    recently somebody decided it:

    1. the stored setting, which is what an administrator typed into the
       panel and therefore beats anything decided before the app started;
    2. ``app.config``, which is the variable the feature declared and the
       product set in its environment;
    3. the default declared in the schema.

    Without the second step the panel and the environment would be separate
    universes: a product setting SITE_NAME in its .env would see the panel
    offer an empty box, and filling that box in would silently disagree with
    the file. The environment is the value the panel starts from.
    """
    from flask import current_app

    schema = _schemas.get(feature)
    if not schema:
        return {}

    stored = _stored_values()
    try:
        config = current_app.config
    except RuntimeError:  # outside an application context
        config = {}

    out = {}
    for f in schema["fields"]:
        raw = stored.get(setting_key(feature, f["key"])) or None
        if raw is None:
            raw = config.get(env_key(feature, f))
        out[f["key"]] = _cast(f, raw)
    return out


def setting_value(feature: str, field_key: str):
    """One typed setting, resolved exactly as :func:`get_config` resolves them.

    For a caller that wants a single value and would otherwise read
    ``config.SOMETHING`` in a template, which is the environment alone and so
    ignores anything the panel changed.
    """
    schema = _schemas.get(feature)
    if not schema:
        return None
    for f in schema["fields"]:
        if f["key"] == field_key:
            return get_config(feature).get(field_key)
    return None
