# app/decorators.py
from functools import wraps
from flask import abort
from flask_login import current_user, login_required

def roles_required(*roles):
    """
    Protège une route par rôle(s).
    Usage:
        @roles_required("admin")
        @roles_required("admin", "staff")
    """
    def wrapper(fn):
        @wraps(fn)
        @login_required
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)

            # Si le modèle User a has_role(), on l’utilise ; sinon on parcourt current_user.roles
            if hasattr(current_user, "has_role"):
                allowed = any(current_user.has_role(r) for r in roles)
            else:
                allowed = any(getattr(r, "name", "") in roles for r in getattr(current_user, "roles", []))

            if not allowed:
                abort(403)

            return fn(*args, **kwargs)
        return decorated
    return wrapper
