"""Cross-site request forgery protection, for the whole product.

Until now there was none. Nothing registered CSRFProtect, so the only
forms that checked a token were the ones whose feature happened to build a
FlaskForm and call ``validate_on_submit``. Every other write in the back
office, and there were forty of them across sixteen features, accepted a
POST from anywhere: the media library's delete, the generic admin CRUD,
the appearance and settings editors.

What that means in practice: a page on another site, opened in a tab by a
logged-in member of staff, can delete a product's whole media library. No
token to guess, no cross-origin read needed, an ordinary auto-submitting
form is enough.

It is registered here, in the framework, rather than in each feature. A
protection each feature has to remember is a protection sixteen features
forgot, and the evidence is that they did.

Turning it on is a breaking change for any form that omits the token,
which is the intent: a form that cannot prove where it came from should
not be honoured. ``WTF_CSRF_ENABLED`` still switches it off, which is what
the testing configuration uses.
"""

import logging

from flask_wtf.csrf import CSRFProtect

logger = logging.getLogger(__name__)

_csrf: CSRFProtect | None = None


class CSRFManager:
    def __init__(self, app):
        global _csrf

        # The cookie the session rides in. SameSite=Lax means a browser
        # will not attach it to a cross-site POST at all, which stops the
        # attack one step earlier than the token does; the token stays
        # because Lax is a browser's promise and not ours.
        # Not setdefault: Flask ships both keys already present, SameSite
        # as None, so setdefault sees a key that exists and leaves the
        # protection off while looking like it turned it on.
        if app.config.get("SESSION_COOKIE_SAMESITE") is None:
            app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        if app.config.get("SESSION_COOKIE_HTTPONLY") is None:
            app.config["SESSION_COOKIE_HTTPONLY"] = True

        if not app.config.get("WTF_CSRF_ENABLED", True):
            # Templates still call csrf_token() in their forms; without the
            # extension the global does not exist and every form page would
            # crash under the testing configuration. An empty token keeps
            # them rendering while the check itself stays off.
            app.jinja_env.globals.setdefault("csrf_token", lambda: "")
            logger.debug("CSRF protection is off for this configuration")
            return

        _csrf = CSRFProtect(app)
        app.extensions["splent_csrf"] = _csrf
        logger.debug("CSRF protection registered")


def exempt(view):
    """Take one view out of the check.

    For an endpoint that is authenticated by something other than a session
    cookie, a token-authenticated API, where a CSRF token means nothing and
    a browser's ambient credentials are not what admits the caller. Nothing
    that a session can reach should use this.
    """
    if _csrf is None:
        return view
    return _csrf.exempt(view)
