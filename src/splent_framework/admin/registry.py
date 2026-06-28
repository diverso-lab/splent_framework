# splent_framework/admin/registry.py
#
# Admin resource registry — the analogue of WordPress `register_post_type`.
#
# A content feature registers its model as an *admin resource*, declaring how it
# should appear in the admin panel (label, icon, menu group, list columns,
# per-field widgets). The `admin` feature reads this registry to build a curated,
# grouped, wp-admin-style menu and CRUD screens — instead of dumping every
# `db.Model` subclass in a flat list.
#
# NOTE: _resources is a module-level registry populated once at app startup
# (during feature registration / init_feature) and read-only during request
# handling — same contract as template_hooks.py. Not thread-safe for concurrent
# writes; do not call register_admin_resource() from request handlers.

from dataclasses import dataclass, field

# Widget hints the admin form renderer understands. Features may pass any of
# these per column via `field_widgets`; unknown columns fall back to an
# introspection-derived default chosen by the admin feature.
WIDGETS = (
    "text",  # single-line string
    "textarea",  # multi-line plain text
    "richtext",  # WYSIWYG / HTML body
    "number",
    "bool",
    "date",
    "datetime",
    "select",  # enum / fixed choices
    "fk",  # foreign key -> related record picker
    "image",  # media id / upload
    "url",
    "slug",
    "color",
)


@dataclass
class AdminResource:
    """Metadata describing how a model is administered in the admin panel."""

    model: type
    name: str  # url-safe key, e.g. "project"
    label: str  # singular human label, e.g. "Project"
    label_plural: str  # e.g. "Projects"
    icon: str = "file"  # feather icon name used in the menu
    group: str = "Content"  # menu section this resource is filed under
    order: int = 100  # sort order within the group
    list_columns: list[str] | None = None  # None -> admin auto-picks
    search_fields: list[str] = field(default_factory=list)
    field_widgets: dict[str, str] = field(default_factory=dict)  # column -> WIDGETS
    readonly_fields: list[str] = field(default_factory=list)
    scope: dict = field(default_factory=dict)  # query filter — lets one shared
    #                                                      table back several menu entries
    #                                                      (e.g. {"collection": "event"})
    create_defaults: dict = field(
        default_factory=dict
    )  # column values forced on create
    feature: str | None = None  # owning feature short name (provenance)

    @property
    def model_name(self) -> str:
        """The SQLAlchemy class name — the key the CRUD routes resolve by."""
        return self.model.__name__


# Module-level singleton registry (keyed by resource `name`).
_resources: dict[str, AdminResource] = {}


def register_admin_resource(
    model: type,
    *,
    name: str | None = None,
    label: str | None = None,
    label_plural: str | None = None,
    icon: str = "file",
    group: str = "Content",
    order: int = 100,
    list_columns: list[str] | None = None,
    search_fields: list[str] | None = None,
    field_widgets: dict[str, str] | None = None,
    readonly_fields: list[str] | None = None,
    scope: dict | None = None,
    create_defaults: dict | None = None,
    feature: str | None = None,
) -> AdminResource:
    """Register a model as an administered resource (additive, idempotent by name).

    Call from a feature's ``init_feature(app)``. The owning content feature thus
    declares its admin surface once; the admin panel renders it. Re-registering
    the same ``name`` overrides the previous entry (last registration wins), which
    lets a refinement feature curate another feature's resource.
    """
    key = name or model.__name__.lower()
    resolved_label = label or model.__name__
    res = AdminResource(
        model=model,
        name=key,
        label=resolved_label,
        label_plural=label_plural or f"{resolved_label}s",
        icon=icon,
        group=group,
        order=order,
        list_columns=list_columns,
        search_fields=search_fields or [],
        field_widgets=field_widgets or {},
        readonly_fields=readonly_fields or [],
        scope=scope or {},
        create_defaults=create_defaults or {},
        feature=feature,
    )
    _resources[key] = res
    return res


def get_admin_resource(name: str) -> AdminResource | None:
    """Return a single registered resource by its url-safe name, or None."""
    return _resources.get(name)


def get_admin_resource_for_model(model_name: str) -> AdminResource | None:
    """Return the resource whose model class name matches ``model_name``."""
    for res in _resources.values():
        if res.model_name == model_name:
            return res
    return None


def get_admin_resources() -> dict[str, AdminResource]:
    """Return all registered resources keyed by name (insertion order)."""
    return dict(_resources)


def get_admin_groups() -> dict[str, list[AdminResource]]:
    """Return resources bucketed by menu group, each sorted by (order, label).

    This is what the admin sidebar iterates to render a grouped, wp-admin-style
    menu (a section per group, content types listed underneath).
    """
    groups: dict[str, list[AdminResource]] = {}
    for res in sorted(_resources.values(), key=lambda r: (r.order, r.label)):
        groups.setdefault(res.group, []).append(res)
    return groups


def clear_admin_resources() -> None:
    """Remove all registered resources. Intended for test teardown."""
    _resources.clear()
