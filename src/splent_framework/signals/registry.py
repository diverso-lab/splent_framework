"""
Signal registry for SPLENT features.

Tracks which features define and connect to blinker signals,
enabling introspection via CLI commands.
"""

from blinker import NamedSignal


_signal_registry: dict[str, dict] = {}
# {
#   "user-registered": {
#       "signal": <NamedSignal>,
#       "provider": "splent_feature_auth",
#       "listeners": ["splent_feature_profile", ...],
#   }
# }


def register_signal(name: str, signal: NamedSignal, provider: str) -> None:
    """Register a signal as provided by a feature."""
    _signal_registry[name] = {
        "signal": signal,
        "provider": provider,
        "listeners": [],
    }


def register_listener(signal_name: str, listener_feature: str) -> None:
    """Record that a feature listens to a signal."""
    if signal_name in _signal_registry:
        listeners = _signal_registry[signal_name]["listeners"]
        if listener_feature not in listeners:
            listeners.append(listener_feature)


def get_signal(name: str) -> NamedSignal | None:
    """Get a registered signal by name."""
    entry = _signal_registry.get(name)
    return entry["signal"] if entry else None


def get_registry() -> dict[str, dict]:
    """Return the full signal registry (read-only view)."""
    return dict(_signal_registry)


def clear_registry() -> None:
    """Clear all registered signals. Intended for test teardown."""
    _signal_registry.clear()
