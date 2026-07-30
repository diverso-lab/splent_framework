"""What a product can be searched for, and who is allowed to see a hit.

The registry exists so a content feature and a search feature never have to
know about each other. These tests pin the one property that makes that
arrangement safe: the feature that owns the material decides, per reader,
per request, whether a candidate becomes a result. An index is a cache and
is stale by definition, so it may only ever propose.
"""

import pytest

from splent_framework.search.search_registry import (
    clear_search_sources,
    get_search_source,
    get_search_sources,
    register_search_source,
    resolve_search_hit,
)


@pytest.fixture(autouse=True)
def clean_registry():
    clear_search_sources()
    yield
    clear_search_sources()


def _source(key="pages", resolve=None, **extra):
    register_search_source(
        key=key,
        label=extra.pop("label", "Pages"),
        fetch=extra.pop("fetch", lambda: []),
        resolve=resolve or (lambda doc_id, user: {"title": doc_id, "url": "/x"}),
        **extra,
    )


class TestDeclaring:
    def test_a_source_is_readable_by_key(self):
        _source()
        assert get_search_source("pages")["label"] == "Pages"

    def test_sources_come_back_in_display_order(self):
        _source(key="late", order=200)
        _source(key="early", order=10)
        assert [s["key"] for s in get_search_sources()] == ["early", "late"]

    def test_registering_twice_overrides(self):
        """Refinement semantics, the same as every other registry here."""
        _source(label="First")
        _source(label="Second")
        assert len(get_search_sources()) == 1
        assert get_search_source("pages")["label"] == "Second"

    def test_find_is_optional(self):
        _source()
        assert get_search_source("pages")["find"] is None


class TestTheOwnerDecides:
    def test_a_hit_the_owner_rejects_never_becomes_a_result(self, flask_app):
        """The index still holds a page withheld a minute ago. It proposes;
        the owner refuses; the reader sees nothing."""
        _source(resolve=lambda doc_id, user: None)
        assert resolve_search_hit("pages", "42", None) is None

    def test_a_hit_the_owner_allows_comes_back_as_given(self, flask_app):
        _source(resolve=lambda doc_id, user: {"title": "Lab 5", "url": "/lab-5"})
        assert resolve_search_hit("pages", "42", None) == {
            "title": "Lab 5",
            "url": "/lab-5",
        }

    def test_the_reader_reaches_the_resolver(self, flask_app):
        """Staff see what students do not, so who is asking has to arrive."""
        seen = {}

        def resolve(doc_id, user):
            seen["user"] = user
            return None

        _source(resolve=resolve)
        resolve_search_hit("pages", "42", "a-user")
        assert seen["user"] == "a-user"


class TestDenyByDefault:
    def test_an_unknown_source_resolves_to_nothing(self, flask_app):
        """A stale index naming a feature this product does not install must
        not be treated as permission to show whatever it holds."""
        assert resolve_search_hit("gone", "42", None) is None

    def test_a_resolver_that_raises_drops_its_hit(self, flask_app):
        def explode(doc_id, user):
            raise RuntimeError("the database is down")

        _source(resolve=explode)
        assert resolve_search_hit("pages", "42", None) is None

    def test_one_broken_resolver_does_not_silence_the_others(self, flask_app):
        def explode(doc_id, user):
            raise RuntimeError("boom")

        _source(key="broken", resolve=explode)
        _source(key="fine", resolve=lambda doc_id, user: {"title": "ok", "url": "/"})

        assert resolve_search_hit("broken", "1", None) is None
        assert resolve_search_hit("fine", "1", None)["title"] == "ok"


class TestClearing:
    def test_clearing_removes_everything(self):
        """A product's sources must not answer another product's search when
        two create_app() calls share one interpreter."""
        _source()
        clear_search_sources()
        assert get_search_sources() == []
