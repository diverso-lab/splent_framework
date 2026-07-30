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
    get_current_scope,
    get_search_scopes,
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

    def test_a_source_that_declares_no_narrowing_still_works(self, flask_app):
        """Most features have one flat pile of material and nothing to
        narrow to. Saying nothing about scopes must cost them nothing."""
        _source()
        assert get_search_source("pages")["scopes"] is None
        assert get_search_source("pages")["current_scope"] is None
        assert get_search_scopes(None) == []
        assert get_current_scope() is None


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


class TestWhereASearchCanBeNarrowedTo:
    """The selector's contents, which are still the owner's answer.

    A course wiki holding fourteen years is one site as far as an index is
    concerned and fourteen places as far as a reader is concerned. Which
    places exist, and which of them this reader is allowed to be told about,
    is a question only the feature holding the courses can answer.
    """

    def test_a_source_says_where_it_can_be_narrowed_to(self, flask_app):
        _source(scopes=lambda user: [{"key": "egc-20252026", "label": "EGC 2025/2026"}])
        assert get_search_scopes(None) == [
            {"key": "egc-20252026", "label": "EGC 2025/2026"}
        ]

    def test_scopes_are_merged_in_source_order(self, flask_app):
        _source(key="late", order=200, scopes=lambda user: [{"key": "b", "label": "B"}])
        _source(key="early", order=10, scopes=lambda user: [{"key": "a", "label": "A"}])
        assert [scope["key"] for scope in get_search_scopes(None)] == ["a", "b"]

    def test_the_same_place_offered_twice_is_listed_once(self, flask_app):
        """Pages and attachments of one course are one narrowing."""
        _source(
            key="pages", order=10, scopes=lambda user: [{"key": "egc", "label": "EGC"}]
        )
        _source(
            key="files", order=20, scopes=lambda user: [{"key": "egc", "label": "EGC"}]
        )
        assert get_search_scopes(None) == [{"key": "egc", "label": "EGC"}]

    def test_the_reader_reaches_the_source(self, flask_app):
        """Staff may narrow to a course students cannot be shown exists."""
        seen = {}

        def scopes(user):
            seen["user"] = user
            return []

        _source(scopes=scopes)
        get_search_scopes("a-user")
        assert seen["user"] == "a-user"

    def test_a_source_may_not_claim_the_everything_option(self, flask_app):
        """The empty key means "do not narrow", and belongs to whoever draws
        the selector rather than to any one feature."""
        _source(scopes=lambda user: [{"key": "", "label": "All of my material"}])
        assert get_search_scopes(None) == []

    def test_a_source_that_raises_is_left_out_of_the_selector(self, flask_app):
        def explode(user):
            raise RuntimeError("the database is down")

        _source(key="broken", order=10, scopes=explode)
        _source(key="fine", order=20, scopes=lambda user: [{"key": "a", "label": "A"}])

        assert get_search_scopes(None) == [{"key": "a", "label": "A"}]


class TestWhereTheReaderIs:
    """Reading the request is the owner's job too.

    The search feature owns /search and nothing else, so it cannot know that
    a reader sitting on /courses/egc-20252026/pages/lab-5 is inside a course.
    The feature that built that URL can.
    """

    def test_the_first_source_that_recognises_the_request_answers(self, flask_app):
        _source(key="pages", order=10, current_scope=lambda: None)
        _source(key="posts", order=20, current_scope=lambda: "egc-20252026")
        assert get_current_scope() == "egc-20252026"

    def test_a_later_source_does_not_override_an_earlier_answer(self, flask_app):
        _source(key="pages", order=10, current_scope=lambda: "first")
        _source(key="posts", order=20, current_scope=lambda: "second")
        assert get_current_scope() == "first"

    def test_nobody_recognising_the_request_means_everywhere(self, flask_app):
        _source(current_scope=lambda: None)
        assert get_current_scope() is None

    def test_a_source_that_raises_does_not_narrow_the_search(self, flask_app):
        """The safe direction here is the opposite of the usual one: a
        broken reading of the request must show too much rather than hide
        what the reader asked for. Nothing is disclosed either way, because
        every hit is still resolved by its owner."""

        def explode():
            raise RuntimeError("the request went missing")

        _source(key="broken", order=10, current_scope=explode)
        _source(key="fine", order=20, current_scope=lambda: "egc")

        assert get_current_scope() == "egc"


class TestClearing:
    def test_clearing_removes_everything(self):
        """A product's sources must not answer another product's search when
        two create_app() calls share one interpreter."""
        _source()
        clear_search_sources()
        assert get_search_sources() == []
