"""Tell the application how many reverse proxies it sits behind.

``request.remote_addr`` is the address of whoever opened the TCP connection.
Behind a reverse proxy that is the proxy, for every caller in the world, so
anything keyed on it collapses into a single bucket: a per caller rate limit
becomes a global one that any stranger can hold against everybody else. Exposed
directly, the peer address is correct and ``X-Forwarded-For`` is a header the
caller writes themselves, so trusting it there hands the attacker an infinite
supply of identities.

Both mistakes are the same mistake, which is why this is one switch and not
two. ``SPLENT_TRUSTED_PROXIES`` is the NUMBER of proxies in front of this app:

    0   (default) nothing is in front. remote_addr is the peer and no
        forwarding header is believed. Correct for `splent product:up` and for
        any container published straight onto a port.

    1   one reverse proxy (nginx, Traefik, Caddy, a single load balancer).
        remote_addr becomes the last address the proxy appended, which is the
        real client.

    2+  that many hops, for a CDN in front of a load balancer.

It is a count rather than a boolean because ProxyFix reads the Nth entry from
the right of ``X-Forwarded-For``. Setting it higher than the real number of
proxies lets a caller inject entries that get read as the client address, so
the value has to match the deployment rather than be turned "on".
"""

import logging
import os

logger = logging.getLogger(__name__)

CONFIG_KEY = "SPLENT_TRUSTED_PROXIES"


class ProxyManager:
    """Install Werkzeug's ProxyFix when the deployment says to."""

    @staticmethod
    def init_app(app) -> None:
        hops = ProxyManager._hops(app)
        if hops <= 0:
            return
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=hops,
            x_proto=hops,
            x_host=hops,
            x_port=hops,
            x_prefix=hops,
        )
        logger.info("Trusting %s reverse prox(y/ies) in front of this app.", hops)

    @staticmethod
    def _hops(app) -> int:
        # A product may pin it in its config.py; otherwise it is a deployment
        # detail and belongs in the environment beside the proxy that created
        # it. Config wins so a product can refuse to believe the environment.
        raw = app.config.get(CONFIG_KEY)
        if raw is None:
            raw = os.getenv(CONFIG_KEY, "0")
        if raw == "":
            return 0
        try:
            hops = int(raw)
        except (TypeError, ValueError):
            logger.warning(
                "%s is %r, which is not a number of proxies. Reading it as 0, "
                "so client addresses are taken from the connection itself.",
                CONFIG_KEY,
                raw,
            )
            return 0
        return max(0, hops)
