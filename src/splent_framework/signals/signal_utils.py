"""
Helpers for defining and connecting feature signals.

Producers use ``define_signal()`` to create and register a signal.
Consumers use ``connect_signal()`` to listen safely (no crash if producer absent).
"""

import logging

from blinker import Namespace, NamedSignal

from splent_framework.signals.registry import (
    register_signal,
    register_listener,
    get_signal,
)

logger = logging.getLogger(__name__)

# Shared blinker namespace for all SPLENT feature signals
_splent_ns = Namespace()

# Handlers that connected before their producer defined the signal, keyed by
# signal name. Flushed by define_signal(), so feature load order doesn't matter
# (a captcha provider can connect to "comment-submitting" before comments loads).
_pending: dict = {}


def define_signal(name: str, provider: str) -> NamedSignal:
    """Define a feature signal and register it in the signal registry.

    Call this in the producer feature's ``signals.py``::

        from splent_framework.signals.signal_utils import define_signal

        user_registered = define_signal("user-registered", "splent_feature_auth")

    Args:
        name: Signal name (e.g. "user-registered").
        provider: Feature package name that emits this signal.

    Returns:
        A blinker NamedSignal ready to ``.send()``.
    """
    signal = _splent_ns.signal(name)
    register_signal(name, signal, provider)
    # Flush handlers that connected before this signal was defined (a listener
    # feature that loaded before its producer). Load order is now irrelevant.
    for fn in _pending.pop(name, []):
        signal.connect(fn)
    return signal


def connect_signal(signal_name: str, listener_feature: str):
    """Decorator to safely connect a handler to a feature signal.

    If the signal hasn't been defined yet (producer feature not installed),
    the handler is silently skipped instead of crashing.

    Call this in the consumer feature's ``signals.py``::

        from splent_framework.signals.signal_utils import connect_signal

        @connect_signal("user-registered", "splent_feature_profile")
        def on_user_registered(sender, user, **kwargs):
            ...

    Args:
        signal_name: Name of the signal to listen to.
        listener_feature: Feature package name of the listener.
    """

    def decorator(fn):
        register_listener(signal_name, listener_feature)
        signal = get_signal(signal_name)
        if signal is not None:
            signal.connect(fn)
        else:
            # Producer not loaded yet (or absent). Defer the connection: if the
            # producer's define_signal() runs later it flushes this handler. If
            # the producer is never installed, the handler simply never fires.
            _pending.setdefault(signal_name, []).append(fn)
            logger.debug(
                "Signal '%s' not defined yet — deferring handler %s.%s.",
                signal_name,
                fn.__module__,
                fn.__name__,
            )
        return fn

    return decorator
