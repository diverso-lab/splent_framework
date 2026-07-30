# splent_framework/search/search_registry.py
#
# What a product can be searched for, declared by the features that own the
# material. A content feature says what it has; a search feature decides how
# to find it. Neither imports the other, so a product can install one, both
# or neither, and a search feature written today works with a content
# feature written next year.
#
# The seam is three callables per source, and the split between them is the
# whole point:
#
#   fetch()                 every document, for building an index
#   resolve(doc_id, user)   may this reader see this, and how is it shown
#   find(term, user)        optional, search without an index
#
# ``resolve`` is where visibility is decided, and it is asked at request
# time, once per candidate, by the feature that owns the material. An index
# is a cache: it is stale between the moment material is withheld and the
# moment it is reindexed, and a search that trusted the index would answer
# with the title of an unreleased exam. Titles leak as much as bodies do, so
# the index is only ever allowed to propose candidates.
#
# Deny by default, exactly like the file access registry: an unknown source,
# a missing resolver, a resolver that raises, all drop the candidate.
#
# NOTE: like the other registries, _sources is populated once at app startup
# (init_feature) and read-only during request handling. Registering the same
# key twice overrides, which is the refinement semantics used everywhere.

from flask import current_app

_sources: dict[str, dict] = {}


def register_search_source(
    key: str,
    label: str,
    fetch,
    resolve,
    find=None,
    order: int = 100,
) -> None:
    """Declare that this feature has material worth searching.

    Args:
        key: stable identifier, normally the feature's short name
            ("courses"). It is the index name a search feature derives and
            the value it stores on every hit, so it must not change once
            anything has been indexed.
        label: human name for the group of results ("Pages"). Translated at
            render time by whoever displays it, so pass the untranslated
            string or a lazy one.
        fetch: ``() -> iterable[dict]`` yielding every document, for a full
            reindex. Each document is ``{"id": str, "title": str, "body":
            str}`` and may carry ``"url"`` and any extra fields the feature
            wants stored. Visibility is NOT part of a document: an index
            that recorded who may read what would be wrong the moment
            somebody withheld a page.
        resolve: ``(doc_id, user) -> dict | None``. The authority. Return a
            presentable result for this reader, or None to drop it. The
            returned dict carries at least ``title`` and ``url``, and
            normally ``snippet``. Called once per candidate, so it should be
            a primary key lookup and not a scan.
        find: optional ``(term, user) -> list[dict]`` for products with no
            search engine installed, or whose engine is down. Same return
            shape as ``resolve``. A source that omits it simply contributes
            nothing when there is no index.
        order: lower sorts first when results are grouped by source.
    """
    _sources[key] = {
        "key": key,
        "label": label,
        "fetch": fetch,
        "resolve": resolve,
        "find": find,
        "order": order,
    }


def get_search_sources() -> list[dict]:
    """Every registered source, in display order."""
    return sorted(_sources.values(), key=lambda s: (s["order"], s["key"]))


def get_search_source(key: str) -> dict | None:
    return _sources.get(key)


def resolve_search_hit(key: str, doc_id, user):
    """Turn one candidate into a result this reader may see, or None.

    Deny by default: a source nobody registered, and a resolver that raises,
    both drop the candidate rather than showing it.
    """
    source = _sources.get(key)
    if source is None:
        return None
    try:
        return source["resolve"](doc_id, user)
    except Exception:
        current_app.logger.exception(
            "search resolver for %r failed on %r; dropping the hit", key, doc_id
        )
        return None


def clear_search_sources() -> None:
    """Remove all registered sources. Intended for use in test teardown."""
    _sources.clear()
