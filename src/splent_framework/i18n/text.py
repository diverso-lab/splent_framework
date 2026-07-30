# splent_framework/i18n/text.py
#
# Product-supplied text that still has to speak the reader's language.
#
# A feature translates its own strings: they are known when it is written,
# they go through gettext, and a catalog ships with the package. A string
# the *product* supplies cannot work that way. SEARCH_PLACEHOLDER, a site
# tagline, the label on a custom nav entry: these are chosen per product,
# after the feature was released, so no catalog can contain them and a
# product cannot add entries to a feature's catalog.
#
# The result was a wiki that switched to English and went on saying
# "Buscar en esta wiki" in the one control a reader uses most.
#
# So a product may write such a value in two forms:
#
#     SEARCH_PLACEHOLDER=Buscar en esta wiki
#     SEARCH_PLACEHOLDER=es:Buscar en esta wiki|en:Search this wiki
#
# The first is one string for every language, which is right for a name and
# wrong for a sentence. The second names a language per variant. Resolution
# falls back rather than failing: the exact locale, then the base language
# (es-ES finds es), then the first variant written, so a product that adds
# a language before translating its labels shows something rather than
# nothing.

from flask import current_app, has_request_context

#: Separates one language's variant from the next.
VARIANT_SEPARATOR = "|"
#: Separates a language tag from its text.
TAG_SEPARATOR = ":"


def parse_localized(raw: str) -> dict:
    """The variants in a value, as ``{language: text}``.

    An empty dict means the value carries no language tags at all, which is
    the ordinary single-string case and is answered by the caller.

    A value is only treated as tagged when *every* variant carries a tag.
    Anything else is one string that happens to contain a colon or a pipe,
    and a URL or a time of day must not be sliced into nonsense.
    """
    text = (raw or "").strip()
    if not text or TAG_SEPARATOR not in text:
        return {}

    variants = {}
    for chunk in text.split(VARIANT_SEPARATOR):
        tag, separator, value = chunk.partition(TAG_SEPARATOR)
        tag = tag.strip().lower().replace("_", "-")
        if not separator or not tag or not value.strip():
            return {}
        # A language tag, not a scheme or an hour: letters, and at most one
        # hyphenated region. "https" would pass the letters test on its own,
        # which is why the length is bounded too.
        head = tag.split("-")[0]
        if not head.isalpha() or not 2 <= len(head) <= 3:
            return {}
        variants[tag] = value.strip()
    return variants


def localized(raw: str, default: str = "") -> str:
    """One product-supplied string, in the language being served.

    Returns ``default`` for an empty value, so a caller can pass its own
    translated fallback and let the product override it only when it wants
    to.
    """
    text = (raw or "").strip()
    if not text:
        return default

    variants = parse_localized(text)
    if not variants:
        # One string for every language. The product said the same thing
        # everywhere, which is what a proper noun wants.
        return text

    locale = _current_locale().lower().replace("_", "-")
    if locale in variants:
        return variants[locale]
    base = locale.split("-")[0]
    if base in variants:
        return variants[base]
    for tag, value in variants.items():
        if tag.split("-")[0] == base:
            return value
    # Nothing matches. The first variant written is the product's own idea
    # of its main language, and showing it beats showing a language tag.
    return next(iter(variants.values()))


def _current_locale() -> str:
    if not has_request_context():
        return current_app.config.get("BABEL_DEFAULT_LOCALE", "en")
    try:
        from splent_framework.managers.locale_manager import current_locale

        return current_locale()
    except Exception:
        return current_app.config.get("BABEL_DEFAULT_LOCALE", "en")
