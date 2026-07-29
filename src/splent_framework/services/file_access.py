# splent_framework/services/file_access.py
#
# Generic access control for protected files (media items stored outside
# static/). The media feature stores WHO owns a restricted file
# (owner_feature + owner_ref columns); the owning feature registers a
# resolver here that decides WHETHER a given user may read it. Media's
# serving route asks resolve_file_access() before sending a single byte.
#
# The contract is deny by default: a restricted file whose owner feature
# registered no resolver, or whose resolver raises, is never served.
#
# NOTE: like the template-hook registry, _resolvers is populated once at app
# startup (init_feature) and read-only during request handling. Registering
# the same owner_feature twice overrides (refinement semantics).

import os
from urllib.parse import quote

from flask import abort, current_app, send_file
from werkzeug.http import dump_options_header

_resolvers: dict[str, object] = {}


def register_file_access_resolver(owner_feature: str, resolver) -> None:
    """Register the access resolver for files owned by ``owner_feature``.

    ``resolver(item, user) -> bool`` receives the media item (duck-typed:
    ``owner_ref`` carries the feature's own reference, e.g. "document:42")
    and the current user (may be anonymous). Return True to allow reading.
    Later calls for the same owner_feature override earlier ones.
    """
    _resolvers[owner_feature] = resolver


def resolve_file_access(item, user) -> bool:
    """Decide whether ``user`` may read ``item``. Deny by default.

    Public items are always readable. Restricted items are readable only if
    the owning feature registered a resolver and it returns truthy; a missing
    owner, a missing resolver or a resolver error all deny.
    """
    if getattr(item, "access", "public") == "public":
        return True
    owner = getattr(item, "owner_feature", None)
    resolver = _resolvers.get(owner) if owner else None
    if resolver is None:
        return False
    try:
        return bool(resolver(item, user))
    except Exception:
        current_app.logger.exception(
            "file access resolver for %r failed; denying", owner
        )
        return False


def clear_file_access_resolvers() -> None:
    """Remove all registered resolvers. Intended for use in test teardown."""
    _resolvers.clear()


# Types a browser may render in place without turning the product's own
# origin into an XSS vector. Everything else downloads as an attachment with
# a generic type, because the stored mime came from the uploader.
INLINE_SAFE_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}


def safe_content_type(mimetype: str) -> tuple[str, str]:
    """Map a stored mime to (served type, disposition).

    text/html or image/svg+xml uploaded by a user would execute in the
    product's origin against the very staff allowed to read protected files,
    so anything outside the inline-safe set is served as an octet-stream
    attachment.
    """
    mimetype = (mimetype or "").split(";")[0].strip().lower()
    if mimetype in INLINE_SAFE_TYPES:
        return mimetype, "inline"
    return "application/octet-stream", "attachment"


def send_protected_file(
    abs_path: str, base_dir: str, mimetype: str = "", download_name: str = ""
):
    """Send a file that lives OUTSIDE static/, after access was granted.

    Callers must have checked resolve_file_access() first; this helper only
    transports bytes. With PROTECTED_FILES_ACCEL_PREFIX configured (e.g.
    "/_protected") it delegates the transfer to the front nginx via
    X-Accel-Redirect against an internal location that maps that prefix to
    ``base_dir``; otherwise Flask streams the file itself.
    """
    abs_path = os.path.realpath(abs_path)
    base_dir = os.path.realpath(base_dir)
    if not abs_path.startswith(base_dir + os.sep):
        abort(404)
    if not os.path.isfile(abs_path):
        abort(404)

    content_type, disposition = safe_content_type(mimetype)
    accel_prefix = current_app.config.get("PROTECTED_FILES_ACCEL_PREFIX", "")
    if accel_prefix:
        rel = os.path.relpath(abs_path, base_dir)
        response = current_app.response_class(status=200)
        # nginx percent-decodes this value, so the path must be quoted.
        response.headers["X-Accel-Redirect"] = (
            f"{accel_prefix}/{quote(rel.replace(os.sep, '/'))}"
        )
        response.headers["Content-Type"] = content_type
        response.headers["Content-Disposition"] = dump_options_header(
            disposition, {"filename": download_name} if download_name else {}
        )
    else:
        response = send_file(
            abs_path,
            mimetype=content_type,
            download_name=download_name or None,
            as_attachment=disposition == "attachment",
            conditional=True,
        )

    response.headers["X-Content-Type-Options"] = "nosniff"
    # Protected bytes must not be stored by any intermediary.
    response.headers["Cache-Control"] = "private, no-store"
    return response
