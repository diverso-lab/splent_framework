# splent_framework/markdown/render.py
#
# One markdown renderer for every feature that stores prose.
#
# It lived inside a content feature, privately, which meant the next
# feature to hold written material would either copy it or do without.
# Copying is the part that matters: what is being copied is not a
# convenience but a security decision, the allowlist a stored body is cut
# down to, and a second copy of that is a second thing to remember to fix.
#
# The three steps are deliberately in this order:
#
#   parse       markdown, GitHub-flavoured, raw HTML allowed
#   highlight   code blocks, by Pygments, into spans
#   sanitise    the whole result, against one allowlist
#
# Sanitising last is what makes highlighting safe to add: the spans go
# through the same cleaning as everything else rather than being trusted
# because we produced them.

import logging

import nh3
from markdown_it import MarkdownIt
from markupsafe import Markup
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

logger = logging.getLogger(__name__)


# ── Code highlighting ────────────────────────────────────────────────────

# Pygments' own class names are one or two letters (k, nb, s1). A stored
# body carries whatever classes the wiki it was migrated from used, so a
# bare "c" from a highlighter and a "c" from some old layout would style
# each other. The prefix makes every token class this renderer emits
# recognisably ours.
TOKEN_PREFIX = "tok-"

# Languages that mean "do not highlight this". Pygments has a lexer for
# them that produces no spans anyway, so this only avoids the work, but it
# also documents that 11% of the code blocks in a wiki are output pasted
# from a terminal rather than source.
PLAIN = {"text", "txt", "plaintext", "plain", "none", ""}


def _formatter():
    from pygments.formatters import HtmlFormatter

    # nowrap: Pygments emits only the spans, and markdown-it keeps its own
    # <pre><code class="language-x"> around them. That class is what a
    # reader's browser, a copy button and any future client-side tool go
    # by, and a formatter that wrapped the block in its own <div> would
    # take it away.
    return HtmlFormatter(nowrap=True, classprefix=TOKEN_PREFIX)


def highlight_code(code: str, language: str | None, _attrs=None) -> str:
    """One code block as HTML, or "" to let markdown-it escape it itself.

    Never raises. A page is not worth losing over a language nobody has a
    lexer for, and "unknown language" is the ordinary case: a body written
    by a person may say ``sh``, ``Bash``, ``console`` or a typo, and only
    the first two of those have ever been the same thing.
    """
    name = (language or "").strip().lower()
    if name in PLAIN:
        return ""

    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name
        from pygments.util import ClassNotFound
    except ImportError:
        # Pygments is a declared dependency, so this is a broken install
        # rather than a configuration. Say so once and render plainly.
        logger.warning("Pygments is not installed; code blocks render unhighlighted")
        return ""

    try:
        lexer = get_lexer_by_name(name)
    except ClassNotFound:
        return ""
    except Exception:
        logger.exception("could not load a lexer for %r; rendering it plainly", name)
        return ""

    try:
        return highlight(code, lexer, _formatter())
    except Exception:
        logger.exception("highlighting a %r block failed; rendering it plainly", name)
        return ""


# ── The dialect ──────────────────────────────────────────────────────────


def build_renderer() -> MarkdownIt:
    """The markdown dialect stored bodies are written in.

    markdown-it-py with the GFM preset, because the material is
    GitHub-flavoured markdown: tables, strikethrough and bare URLs already
    appear in it and a stricter CommonMark reader would show them as
    literal text. Raw HTML is enabled for the same reason, wikis migrated
    from elsewhere contain it, and is made safe afterwards rather than
    dropped, which would silently lose content.

    The plugins are the ones written material actually uses: heading
    anchors so a long page can be linked to by section, definition lists,
    footnotes and task lists.
    """
    return (
        MarkdownIt(
            "gfm-like",
            {
                "html": True,
                "linkify": True,
                "typographer": False,
                "highlight": highlight_code,
            },
        )
        .use(anchors_plugin, max_level=4)
        .use(deflist_plugin)
        .use(footnote_plugin)
        .use(tasklists_plugin)
    )


_MARKDOWN = build_renderer()


# ── The allowlist ────────────────────────────────────────────────────────

# Built from nh3's own list rather than from scratch, so the day an
# element turns out to be dangerous the library takes it away here too.
ALLOWED_TAGS = set(nh3.ALLOWED_TAGS) | {"input"}

ALLOWED_ATTRIBUTES = {tag: set(attrs) for tag, attrs in nh3.ALLOWED_ATTRIBUTES.items()}
# id carries the heading anchors; class carries the plugins' own markup,
# the highlighter's token names and whatever a migrated body was styled
# with. Neither can execute anything.
ALLOWED_ATTRIBUTES["*"] = ALLOWED_ATTRIBUTES.get("*", set()) | {"id", "class"}
ALLOWED_ATTRIBUTES["input"] = {"checked", "disabled"}

# A task list checkbox is the only input a body may contain; anything else
# would be a form pointing somewhere of the author's choosing.
ALLOWED_INPUT_VALUES = {"input": {"type": {"checkbox"}}}

ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def render_markdown(body_md: str) -> Markup:
    """A stored body as HTML a reader can be shown.

    Rendered here rather than in a template because the sanitising step is
    not optional: a body may be written by staff today and have been
    migrated yesterday from a wiki anyone with an account could edit, and
    marking it safe without cleaning it would run whatever it contains.
    """
    html = _MARKDOWN.render(body_md or "")
    return Markup(
        nh3.clean(
            html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            tag_attribute_values=ALLOWED_INPUT_VALUES,
            url_schemes=ALLOWED_URL_SCHEMES,
        )
    )
