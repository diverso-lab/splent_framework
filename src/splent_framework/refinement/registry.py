"""
RefinementRegistry — in-memory store for all declared refinement overrides.

Populated during startup validation (before feature loading).
Read during the integrate phase to apply overrides.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RefinementEntry:
    """A single override or extension declared by a refining feature."""

    refiner: str  # e.g. "splent_feature_auth_2fa"
    base: str  # e.g. "splent_feature_auth"
    category: str  # "service", "template", "model", "route", "hook"
    target: str  # e.g. "AuthenticationService", "auth/login_form.html"
    replacement: str = ""  # e.g. "AuthenticationService2FA", "" for hooks
    action: str = "override"  # "override", "extend", "replace", "add"


class RefinementRegistry:
    """Module-level singleton (same pattern as template_hooks.py)."""

    def __init__(self) -> None:
        self._entries: list[RefinementEntry] = []
        # base_feature -> {category -> [entries]}
        self._index: dict[str, dict[str, list[RefinementEntry]]] = {}

    def register(self, entry: RefinementEntry) -> None:
        self._entries.append(entry)
        self._index.setdefault(entry.base, {}).setdefault(entry.category, []).append(
            entry
        )

    def get_overrides(
        self, base_feature: str, category: str
    ) -> list[RefinementEntry]:
        return self._index.get(base_feature, {}).get(category, [])

    def get_all_for_base(self, base_feature: str) -> dict[str, list[RefinementEntry]]:
        return self._index.get(base_feature, {})

    def get_refiners(self) -> set[str]:
        """Return the set of feature names that act as refiners."""
        return {e.refiner for e in self._entries}

    def get_bases(self) -> set[str]:
        """Return the set of feature names that are being refined."""
        return set(self._index.keys())

    def is_refiner(self, feature_name: str) -> bool:
        return feature_name in self.get_refiners()

    def all_entries(self) -> list[RefinementEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()
        self._index.clear()


# Module-level singleton
_registry = RefinementRegistry()


def get_registry() -> RefinementRegistry:
    return _registry


def clear_registry() -> None:
    _registry.clear()
