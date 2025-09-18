from flask import abort
from flask_login import current_user, login_required
from functools import wraps

def roles_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        @login_required
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not any(current_user.has_role(r) for r in roles):
                abort(403)
            return fn(*args, **kwargs)
        return decorated
    return wrapper

