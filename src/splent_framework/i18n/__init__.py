"""Text that has to speak the reader's language.

``localized`` resolves a product-supplied string against the active locale.
Available in templates as a global of the same name::

    placeholder="{{ localized(config.SEARCH_PLACEHOLDER, _('Search this site')) }}"
"""

from splent_framework.i18n.text import localized, parse_localized

__all__ = ["localized", "parse_localized"]
