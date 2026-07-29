from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def pass_or_abort(condition):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not condition(**kwargs):
                abort(404)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def role_required(*roles):
    """Require an authenticated, active user whose ``role`` is in ``roles``.

    The shared authorization vocabulary for all features: auth contributes the
    ``role`` column on User and every feature gates its screens with this
    decorator. Deny by default: a user without a ``role`` attribute (older auth
    versions) or with a role outside ``roles`` gets 403.

    Usage::

        @bp.route("/admin/courses")
        @role_required("staff", "admin")
        def admin_courses():
            ...
    """

    def decorator(f):
        @login_required
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not getattr(current_user, "active", False):
                abort(403)
            if getattr(current_user, "role", None) not in roles:
                abort(403)
            return f(*args, **kwargs)

        return wrapper

    return decorator
