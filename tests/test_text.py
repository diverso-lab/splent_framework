"""
Tests for splent_framework.utils.text.slugify

Covers:
- Accented names fold to clean ASCII slugs
- Lowercasing and collapsing of non-alphanumeric runs
- Leading/trailing separators are stripped
- Empty, None and mark-only input are safe
"""

from splent_framework.utils.text import slugify


class TestSlugify:
    def test_folds_accents_to_ascii(self):
        assert slugify("Jesús Moreno León") == "jesus-moreno-leon"

    def test_lowercases_and_collapses_separators(self):
        assert slugify("Former Members & Collaborators") == (
            "former-members-collaborators"
        )

    def test_strips_leading_and_trailing_separators(self):
        assert slugify("  ¡Hola, mundo!  ") == "hola-mundo"

    def test_keeps_digits(self):
        assert slugify("Version 2.0") == "version-2-0"

    def test_empty_string_returns_empty(self):
        assert slugify("") == ""

    def test_none_returns_empty(self):
        assert slugify(None) == ""

    def test_non_ascii_only_returns_empty(self):
        assert slugify("¿¡·—") == ""
