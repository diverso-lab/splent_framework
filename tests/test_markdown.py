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
        """The comment, not the command: `vagrant up` is two ordinary words
        to a shell lexer, and colouring them would be inventing meaning."""
        html = render_markdown("``` bash\nvagrant up  # levanta la maquina\n```")
        assert TOKEN_PREFIX in html

    def test_whitespace_does_not_become_markup(self):
        """Pygments writes a span for every token it produces, whitespace
        included, and whitespace has no colour in any palette. Five lines of
        shell came out carrying eighteen spans that said nothing, on 382
        pages."""
        html = render_markdown("``` bash\nvagrant init ubuntu/trusty32\n```")
        assert "tok-w" not in html

    def test_a_line_of_plain_words_stays_one_string(self):
        """Adjacent plain runs are merged, so an ordinary command line is not
        broken into a dozen fragments by the markup around it."""
        html = render_markdown("``` bash\nvagrant init ubuntu/trusty32  # x\n```")
        assert "vagrant init ubuntu/trusty32" in html

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


class TestLinksThatLeaveTheSite:
    """A wiki is a place a reader keeps their position in.

    Following a reference to a manual is checking something, not leaving,
    and taking the page away loses their place in a document they were
    halfway through. Off by default here: it is a judgement about the
    material, and the feature that owns the material makes it.
    """

    def test_off_by_default(self):
        html = render_markdown("[manual](https://vagrantup.com)")
        assert "target=" not in html

    def test_an_external_link_opens_beside_the_page(self):
        html = render_markdown("[manual](https://vagrantup.com)", True)
        assert 'target="_blank"' in html

    def test_a_link_within_the_wiki_does_not(self):
        """Everything a stored body writes about its own material is a path,
        so having a host is the same question as being somewhere else."""
        html = render_markdown("[lab 5](/cursos/egc/pagina/lab-5)", True)
        assert "target=" not in html

    def test_it_still_carries_the_rel_that_makes_it_safe(self):
        """Without it the page opened in the new tab can reach back through
        window.opener."""
        html = render_markdown("[manual](https://vagrantup.com)", True)
        assert "noopener" in html

    def test_raw_html_links_in_a_migrated_body_are_marked_too(self):
        """Bodies migrated from another wiki write their links as HTML, and
        those never pass through markdown-it's link renderer."""
        html = render_markdown('<a href="https://vagrantup.com">manual</a>', True)
        assert 'target="_blank"' in html

    def test_an_author_cannot_choose_where_their_link_opens(self):
        """target is not on the allowlist, so a stored body saying _self, or
        naming a frame, loses it in the sanitising step. The product decides
        for every link on the page or for none, which is the point of the
        setting: one page behaving differently from the rest reads as a bug
        to the reader and cannot be turned off by whoever runs the site."""
        written = '<a href="https://x.org" target="_self">x</a>'

        assert "target=" not in render_markdown(written)
        assert 'target="_blank"' in render_markdown(written, True)


class TestAutolinkingDoesNotInventHostnames:
    """linkify's fuzzy mode reads any dotted word as a hostname when the
    last part looks like a TLD, and .py, .sh and .md all are.

    On a course wiki that is not a cosmetic problem. Measured on the real
    corpus: 72 pages and 21 invented hostnames, the Vagrant tutorial of the
    current year included. readme.md and provision.sh resolve today to
    somebody else's website, so a wiki students trust was handing them to a
    third party, and every one of those names is registrable by anyone.
    """

    @pytest.mark.parametrize(
        "source",
        [
            "edita provision.sh con tu editor",
            "el fichero views.py del proyecto",
            "mira el README.md",
            "ejecuta locustfile.py",
        ],
    )
    def test_a_filename_stays_a_filename(self, source):
        assert "<a " not in render_markdown(source)

    def test_a_written_out_url_still_becomes_a_link(self):
        html = render_markdown("la documentación en https://vagrantup.com")
        assert 'href="https://vagrantup.com"' in html

    def test_an_explicit_markdown_link_is_untouched(self):
        html = render_markdown("[el manual](https://vagrantup.com)")
        assert 'href="https://vagrantup.com"' in html

    def test_an_email_address_is_not_autolinked_either(self):
        """Same rule, same reason: a dotted word is not an address because
        it has a dot in it."""
        assert "<a " not in render_markdown("escribe a profe@us.es")
