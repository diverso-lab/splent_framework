"""The one markdown renderer, and the allowlist it cuts every body down to.

This lived privately inside a content feature. What made moving it worth
doing is not tidiness: the sanitising step is a security decision, and a
second feature holding written material would have had to copy it, which
is a second copy to remember when the first one is wrong.

The highlighting tests are the ones that matter most for the order of the
three steps. Pygments output is HTML, and it goes through nh3 with
everything else rather than being trusted because we produced it.
"""

import pytest

from splent_framework.markdown import (
    TOKEN_PREFIX,
    highlight_code,
    render_markdown,
)


class TestTheDialect:
    def test_a_table_is_a_table(self):
        """GFM, because that is what the stored material is written in. A
        stricter CommonMark reader shows the pipes as literal text."""
        html = render_markdown("| a | b |\n|---|---|\n| 1 | 2 |")
        assert "<table>" in html

    def test_a_bare_url_becomes_a_link(self):
        assert 'href="https://example.org"' in render_markdown("https://example.org")

    def test_headings_carry_an_anchor(self):
        """So a long practical can be linked to by section."""
        assert 'id="' in render_markdown("## Instalación")

    def test_a_task_list_keeps_its_checkbox(self):
        html = render_markdown("- [x] done\n- [ ] pending")
        assert "<input" in html
        assert "checkbox" in html


class TestTheAllowlist:
    def test_a_script_never_survives(self):
        assert "<script" not in render_markdown("<script>alert(1)</script>")

    def test_an_event_handler_is_stripped(self):
        assert "onerror" not in render_markdown('<img src=x onerror="alert(1)">')

    def test_a_javascript_url_never_becomes_a_link(self):
        """Written as markdown, markdown-it refuses to make a link of it and
        leaves the literal text, which is harmless. Written as raw HTML,
        which a migrated body may well contain, only the allowlist stops
        it, so that is the one checked here."""
        html = render_markdown('<a href="javascript:alert(1)">click</a>')
        assert "javascript:" not in html
        assert "click" in html

    def test_ordinary_html_in_a_migrated_body_survives(self):
        """Bodies migrated from another wiki contain raw HTML. Dropping it
        rather than cleaning it would silently lose content."""
        assert "<strong>" in render_markdown("<strong>bold</strong>")

    def test_an_input_that_is_not_a_checkbox_is_refused(self):
        html = render_markdown('<input type="text" name="password">')
        assert 'type="text"' not in html


class TestHighlighting:
    def test_a_tagged_block_is_highlighted(self):
        html = render_markdown("``` bash\nvagrant up\n```")
        assert TOKEN_PREFIX in html

    def test_the_language_class_survives_highlighting(self):
        """It is what the markup says the block is, and a formatter that
        wrapped the block in its own element would take it away."""
        html = render_markdown("``` python\nprint(1)\n```")
        assert 'class="language-python"' in html

    def test_a_space_before_the_language_is_understood(self):
        """The migrated corpus writes the fence that way, all 1664 of them."""
        assert TOKEN_PREFIX in render_markdown("``` python\nprint(1)\n```")

    def test_an_alias_is_the_language_it_is_an_alias_of(self):
        """sh is by far the second most common tag in the corpus."""
        assert TOKEN_PREFIX in render_markdown("``` sh\necho hola\n```")

    def test_the_token_classes_are_prefixed(self):
        """Pygments' own names are one or two letters, and a stored body
        carries whatever classes the wiki it came from used. A bare 'c'
        from a highlighter and a 'c' from an old layout would style each
        other."""
        html = render_markdown("``` python\n# comment\n```")
        assert f'class="{TOKEN_PREFIX}' in html

    @pytest.mark.parametrize("plain", ["text", "txt", "plaintext", ""])
    def test_output_pasted_from_a_terminal_is_left_alone(self, plain):
        """Eleven percent of the blocks in a migrated wiki are output, not
        source, and colouring them invents structure that is not there."""
        assert highlight_code("total 12\ndrwxr-xr-x", plain) == ""

    def test_a_language_nobody_has_a_lexer_for_renders_plainly(self):
        """A body is written by a person: it may say console, or a typo."""
        assert highlight_code("x", "not-a-real-language") == ""

    def test_such_a_block_still_reaches_the_reader(self):
        html = render_markdown("``` not-a-real-language\nvagrant up\n```")
        assert "vagrant up" in html

    def test_highlighted_output_is_still_sanitised(self):
        """The spans go through nh3 with everything else. Trusting them
        because we produced them is how a highlighter becomes an injection
        point the day it has a bug."""
        html = render_markdown("``` html\n<script>alert(1)</script>\n```")
        assert "<script" not in html
        # The block is still shown, as text. Pygments breaks it across
        # spans, so what is checked is that the content is there rather
        # than that it survived as one string.
        assert "alert" in html
        assert "&lt;" in html


class TestEmptyBodies:
    @pytest.mark.parametrize("body", ["", None])
    def test_nothing_renders_as_nothing(self, body):
        assert render_markdown(body) == ""
