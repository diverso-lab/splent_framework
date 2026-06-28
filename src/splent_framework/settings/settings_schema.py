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


def register_settings(feature: str, title: str, fields: list, icon: str = "sliders") -> None:
    """Declare a feature's admin-editable settings.

    Args:
        feature: stable key, e.g. "slider" (also the panel URL segment and the
            setting-key namespace).
        title: human title shown in the panel/sidebar, e.g. "Slider".
        fields: list of dicts ``{key, type, default, label, help?, options?}``.
            ``type`` in bool/int/text/color/select. For select, provide
            ``options`` as a list of ``(value, label)`` pairs.
        icon: feather icon name for the sidebar entry.
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
    key (e.g. {"autoplay": True, "interval": 6}). Reads SettingsService and
    falls back to declared defaults."""
    from splent_framework.services.service_locator import service_proxy

    schema = _schemas.get(feature)
    if not schema:
        return {}
    try:
        svc = service_proxy("SettingsService")
    except Exception:
        svc = None
    out = {}
    for f in schema["fields"]:
        raw = svc.get(setting_key(feature, f["key"]), None) if svc else None
        out[f["key"]] = _cast(f, raw)
    return out
