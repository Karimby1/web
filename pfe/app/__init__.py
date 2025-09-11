import os
from flask import Flask, redirect, url_for
from flask_login import current_user
from .extensions import db, login_manager
from .models.user import User

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # --- Core config ---
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:@127.0.0.1:3306/pfe_db"   # change to 3307 if needed
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", False)

    # --- Init extensions ---
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # --- Blueprints ---
    from .blueprints.auth.routes import auth_bp
    from .blueprints.admin.routes import admin_bp
    from .blueprints.dashboards.routes import dashboards_bp
    from .blueprints.user.routes import user_bp

    app.register_blueprint(auth_bp)                                  # /login, /register, /logout
    app.register_blueprint(admin_bp, url_prefix="/admin")            # /admin/...
    app.register_blueprint(dashboards_bp, url_prefix="/dashboards")  # /dashboards/...
    app.register_blueprint(user_bp, url_prefix="/user")              # /user/...

    # --- Root redirect ---
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboards.view"))
        return redirect(url_for("auth.login"))

    # --- Template helpers used by base.html ---
    @app.context_processor
    def inject_helpers():
        from flask import request

        def is_admin():
            return (
                getattr(current_user, "is_authenticated", False)
                and any(getattr(r, "name", "") == "admin" for r in getattr(current_user, "roles", []))
            )

        def is_active(prefix: str):
            # Return 'active' if current URL starts with prefix (for nav highlighting)
            return "active" if request.path.startswith(prefix) else ""

        return dict(is_admin=is_admin, is_active=is_active)

    return app
