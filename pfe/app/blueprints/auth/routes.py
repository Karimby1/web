from urllib.parse import urlparse, urljoin

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    current_app,
)
from flask_login import login_user, logout_user, current_user
from sqlalchemy import func  # <-- add this
from ...extensions import db
from ...models.user import User, Role
from wtforms import Form, StringField, PasswordField
from wtforms.validators import InputRequired, Email, Length

auth_bp = Blueprint("auth", __name__)

# --- Helpers ---
def _is_safe_url(target: str) -> bool:
    """Allow redirects only to same-origin URLs (prevents open redirects)."""
    if not target:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return (test.scheme in ("http", "https")) and (ref.netloc == test.netloc)

# --- Forms ---
class LoginForm(Form):
    email = StringField(
        "Email",
        [InputRequired(), Email(message="Invalid email", check_deliverability=False)],
    )
    password = PasswordField("Password", [InputRequired(), Length(min=1)])

class RegisterForm(Form):
    email = StringField(
        "Email",
        [InputRequired(), Email(message="Invalid email", check_deliverability=False), Length(max=120)],
    )
    password = PasswordField(
        "Password",
        [
            InputRequired(),
            Length(min=6, message="Password must be at least 6 characters"),
        ],
    )
    confirm = PasswordField("Confirm Password")

# --- Routes ---
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Already logged in → route by role
    if current_user.is_authenticated:
        return redirect(
            url_for("admin.panel") if current_user.has_role("admin") else url_for("dashboards.view")
        )

    form = LoginForm(request.form)

    if request.method == "POST":
        # Debug logging
        try:
            current_app.logger.debug("POST /login data=%s", dict(request.form))
        except Exception:
            pass

        ok = form.validate()
        try:
            current_app.logger.debug("form.validate()=%s errors=%s", ok, getattr(form, "errors", {}))
        except Exception:
            pass

        if ok:
            email = (form.email.data or "").strip().lower()
            # case-insensitive lookup
            user = User.query.filter(func.lower(User.email) == email).first()
            pwd_ok = bool(user and user.check_password(form.password.data))

            try:
                current_app.logger.debug("user_found=%s pwd_ok=%s", bool(user), pwd_ok)
            except Exception:
                pass

            if pwd_ok:
                login_user(user, remember=True)

                # Honor ?next= if safe; else role-based landing
                next_url = request.args.get("next")
                if next_url and _is_safe_url(next_url):
                    target = next_url
                else:
                    target = url_for("admin.panel") if user.has_role("admin") else url_for("dashboards.view")

                try:
                    current_app.logger.debug("redirect -> %s", target)
                except Exception:
                    pass

                return redirect(target)

            flash("Invalid credentials", "danger")
        else:
            current_app.logger.debug("FORM ERRORS = %s", getattr(form, "errors", {}))
            flash("Invalid form data", "danger")

    return render_template("login.html", form=form)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboards.view"))

    form = RegisterForm(request.form)
    if request.method == "POST" and form.validate():
        email = (form.email.data or "").strip().lower()

        # Check if email already used
        if User.query.filter(func.lower(User.email) == email).first():
            flash("An account with this email already exists.", "danger")
            return render_template("register.html", form=form)

        # Create user
        user = User(email=email)
        user.set_password(form.password.data)

        # Ensure default 'user' role exists and assign it
        role_user = Role.query.filter_by(name="user").first()
        if not role_user:
            role_user = Role(name="user")
            db.session.add(role_user)
            db.session.flush()

        user.roles = [role_user]
        db.session.add(user)
        db.session.commit()

        flash("Registration successful. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", form=form)

@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
