"""Admin resource registry — declare how models surface in the admin panel.

A content feature registers its model with :func:`register_admin_resource`
(typically from ``init_feature``); the ``admin`` feature reads the registry to
build a grouped, wp-admin-style menu and CRUD screens. Mirrors the singleton
pattern of ``splent_framework.hooks.template_hooks``.
"""

from splent_framework.admin.registry import (
    WIDGETS,
    AdminResource,
    clear_admin_resources,
    get_admin_groups,
    get_admin_resource,
    get_admin_resource_for_model,
    get_admin_resources,
    register_admin_resource,
)

__all__ = [
    "WIDGETS",
    "AdminResource",
    "register_admin_resource",
    "get_admin_resource",
    "get_admin_resource_for_model",
    "get_admin_resources",
    "get_admin_groups",
    "clear_admin_resources",
]
