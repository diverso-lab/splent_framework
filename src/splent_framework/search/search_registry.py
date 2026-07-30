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
#   fetch()                        every document, for building an index
#   resolve(doc_id, user)          may this reader see this, and how is it
#                                  shown
#   find(term, user, scope=None)   optional, search without an index
#
# A source may also say where a search can be narrowed to, which is what
# turns one box into "search this course" without the search feature ever
# learning what a course is:
#
#   scopes(user)            the narrowings this reader may pick
#   current_scope()         the one the reader is already standing in
#
# Both belong to the feature that owns the material, because both are
# answers about its own URLs and its own visibility rules.
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
    resolve_many=None,
    scopes=None,
    current_scope=None,
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
            str}`` and may carry ``"url"``, ``"scope"`` and any extra fields
            the feature wants stored. ``scope`` is the key of the place this
            document belongs to, one of the keys ``scopes`` offers, and it
            is what a narrowed search filters on. Visibility is NOT part of
            a document: an index that recorded who may read what would be
            wrong the moment somebody withheld a page.
        resolve: ``(doc_id, user) -> dict | None``. The authority. Return a
            presentable result for this reader, or None to drop it. The
            returned dict carries at least ``title`` and ``url``, and
            normally ``snippet``. Called once per candidate, so it should be
            a primary key lookup and not a scan.
        find: optional ``(term, user, scope=None) -> list[dict]`` for
            products with no search engine installed, or whose engine is
            down. Same return shape as ``resolve``. A source that omits it
            simply contributes nothing when there is no index. When a scope
            arrives, the answer must be narrowed to it: without an index
            there is nothing else standing between the reader and the whole
            site.
        resolve_many: optional ``(doc_ids, user) -> dict[doc_id, result]``,
            answering a whole page of candidates at once and leaving out
            what this reader may not see. Worth implementing, because a
            search asks about far more candidates than it shows: a
            resolver called in a loop turns one query into hundreds, and
            the time it takes then depends on how much withheld material
            matched, which is a signal a reader should not be able to
            measure. Falls back to ``resolve`` per id when absent.
        scopes: optional ``(user) -> iterable[dict]`` naming the places a
            search may be narrowed to, as ``{"key": str, "label": str}`` in
            display order. Already filtered to what this reader may see,
            because the list is rendered in a selector and a course that
            has not been announced yet is a course whose name the selector
            would announce.
        current_scope: optional ``() -> str | None`` saying where the
            reader is standing right now, read out of the request. It is
            this feature's job and not the search feature's: only the
            feature that owns ``/courses/egc-20252026/pages/lab-5`` knows
            that the second segment names a course, and a search feature
            that took the URL apart itself would be guessing at another
            feature's routing, would guess wrong the day the product serves
            it under a different word, and would have to guess again for
            every content feature ever written. Return None when the reader
            is somewhere this source knows nothing about.
        order: lower sorts first when results are grouped by source.
    """
    _sources[key] = {
        "key": key,
        "label": label,
        "fetch": fetch,
        "resolve": resolve,
        "resolve_many": resolve_many,
        "find": find,
        "scopes": scopes,
        "current_scope": current_scope,
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


def resolve_search_hits(key: str, doc_ids, user) -> dict:
    """Turn a page of candidates into the results this reader may see.

    Returns ``{doc_id: result}`` holding only what survived, so the caller
    can keep the engine's ranking by walking ``doc_ids`` and looking each
    one up. A source that registered ``resolve_many`` answers in one go;
    otherwise this asks ``resolve`` per id, which is correct but costs a
    query per candidate.

    Deny by default all the way through: an unknown source answers nothing,
    a batch resolver that raises answers nothing, and a single resolver
    that raises drops only its own candidate.
    """
    source = _sources.get(key)
    if source is None:
        return {}

    batch = source.get("resolve_many")
    if batch is not None:
        try:
            answered = batch(list(doc_ids), user) or {}
        except Exception:
            current_app.logger.exception(
                "search batch resolver for %r failed; dropping the whole page", key
            )
            return {}
        return {doc_id: result for doc_id, result in answered.items() if result}

    resolved = {}
    for doc_id in doc_ids:
        result = resolve_search_hit(key, doc_id, user)
        if result:
            resolved[doc_id] = result
    return resolved


def get_search_scopes(user) -> list[dict]:
    """Everywhere this reader may narrow a search to, in source order.

    Merged into one flat list rather than kept per source, because a reader
    picks a place to look and does not care which feature holds it. A key
    offered twice is kept once: two features covering the same material, a
    course's pages and a course's attachments, name the same narrowing, and
    a selector listing it twice looks broken.

    The empty key is left to whoever renders the selector, since it means
    "do not narrow at all" and no source owns that.

    Deny by default, as everywhere else here: a source whose scopes() raises
    contributes none rather than taking the whole selector down.
    """
    merged: list[dict] = []
    seen: set[str] = set()
    for source in get_search_sources():
        offer = source.get("scopes")
        if offer is None:
            continue
        try:
            offered = list(offer(user) or ())
        except Exception:
            current_app.logger.exception(
                "search source %r failed to say where it can be narrowed to; "
                "leaving it out of the selector",
                source["key"],
            )
            continue
        for scope in offered:
            if not isinstance(scope, dict):
                continue
            key = str(scope.get("key") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append({"key": key, "label": str(scope.get("label") or key)})
    return merged


def get_current_scope() -> str | None:
    """Where the reader is standing, according to the first source that knows.

    Sources are asked in display order and the first non-None answer wins.
    A source that does not recognise the request says None, which is the
    ordinary answer: on any given page at most one feature owns the URL.

    Deny by default here means answering None: a source whose reading of the
    request raises leaves the search unnarrowed, which shows the reader more
    than they asked for rather than hiding what they wanted.
    """
    for source in get_search_sources():
        report = source.get("current_scope")
        if report is None:
            continue
        try:
            scope = report()
        except Exception:
            current_app.logger.exception(
                "search source %r failed to say where the reader is; "
                "searching everything instead",
                source["key"],
            )
            continue
        if scope is not None:
            return str(scope)
    return None


def clear_search_sources() -> None:
    """Remove all registered sources. Intended for use in test teardown."""
    _sources.clear()
