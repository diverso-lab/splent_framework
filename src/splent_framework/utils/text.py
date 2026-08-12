import re
import unicodedata


def slugify(value: str | None) -> str:
    """
    Build a URL-safe slug from arbitrary text, folding accents to ASCII.

    The value is NFKD-normalized so accented characters decompose into a
    base letter plus a combining mark, the marks are dropped, everything
    is lowercased, runs of non-alphanumeric characters collapse to a
    single hyphen, and leading/trailing hyphens are stripped. For example,
    "Jesús Moreno León" becomes "jesus-moreno-leon" instead of the
    mangled "jes-s-moreno-le-n" a plain regex would produce.

    Returns "" for None or text with no usable characters.
    """
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
