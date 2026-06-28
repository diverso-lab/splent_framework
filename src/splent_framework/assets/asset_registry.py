# splent_framework/assets/asset_registry.py
#
# SPL asset registry. Features DECLARE their stylesheets/scripts here (from
# init_feature) instead of hand-writing <link>/<script> tags in hooks or
# inlining JS into templates. The public shell renders get_assets("css") in
# <head> and get_assets("js") before </body>, DEDUPLICATED and ORDERED — so the
# cascade is deterministic and asset injection is consistent across features.
# No ad-hoc tags, no inline scripts: a feature ships a file under its blueprint's
# assets/ folder (served by the blueprint asset route) and registers it here.
#
# Cleared per app at feature-load (like the nav registry) so each product only
# emits the assets of ITS installed features. Registration is idempotent.

_assets: list = []


def register_asset(kind: str, endpoint: str, order: int = 100, **params) -> None:
    """Declare a static asset served by a feature blueprint's asset route.

    Args:
        kind: "css" or "js".
        endpoint: the blueprint asset endpoint, e.g. "slider.assets".
        order: load order (lower first) — governs the cascade deterministically.
            Convention: theme base ~0, features ~100, skins ~200 (win last).
        **params: url_for params for the asset route, e.g.
            subfolder="css", filename="slider.css".
    """
    key = (kind, endpoint, tuple(sorted(params.items())))
    for a in _assets:
        if a["key"] == key:
            return
    _assets.append(
        {
            "key": key,
            "kind": kind,
            "endpoint": endpoint,
            "params": params,
            "order": order,
        }
    )


def get_assets(kind: str) -> list:
    """Resolved asset URLs of a kind, ordered by (order, endpoint) and deduped.

    url_for is resolved at call time, so invoke this from the template (request
    context). Assets whose route can't be resolved are skipped, not raised.
    """
    from flask import url_for

    seen = set()
    out = []
    for a in sorted(_assets, key=lambda x: (x["order"], x["endpoint"])):
        if a["kind"] != kind:
            continue
        try:
            href = url_for(a["endpoint"], **a["params"])
        except Exception:
            continue
        if href not in seen:
            seen.add(href)
            out.append(href)
    return out


def clear_assets() -> None:
    """Drop all registered assets. Called per app before feature load."""
    _assets.clear()
