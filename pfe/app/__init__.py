# app/__init__.py
import os
from flask import Flask, redirect, url_for
from flask_login import current_user

from .extensions import db, login_manager
from .models.user import User   # Role sera importé dans app_context plus bas

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # --- Core config ---
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:@127.0.0.1:3306/pfe_db"  # adapte user/mdp/port si besoin
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", False)

    # (optionnel) URL Power BI depuis env
    app.config.setdefault(
        "POWERBI_EMBED_URL",
        "https://app.powerbi.com/reportEmbed?reportId=3013134f-5f30-4f7f-81ad-14f4faa1b04e&autoAuth=true&ctid=604f1a96-cbe8-43f8-abbf-f8eaf5d85730"
    )
    app.config.setdefault(
    "MODEL_PATH",
    os.path.join(app.instance_path, "models", "price_xgb.joblib")
    )

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

    # --- Blueprints (IMPORTS ICI SEULEMENT) ---
    from .blueprints.auth.routes import auth_bp
    from .blueprints.admin.routes import admin_bp
    from .blueprints.dashboards.routes import dash_bp   # ← le nouveau nom
    from .blueprints.user.routes import user_bp

    app.register_blueprint(auth_bp)                        # /login, /register, /logout
    app.register_blueprint(admin_bp, url_prefix="/admin")  # /admin/...
    app.register_blueprint(dash_bp)                        # /dashboards/... (prefix dans le blueprint)
    app.register_blueprint(user_bp, url_prefix="/user")    # /user/...
    
    # --- Create tables & seed roles on first run ---
    with app.app_context():
        from .models.user import Role  # importer le modèle avant create_all

        db.create_all()

        # Seed rôles si absents
        if not Role.query.filter_by(name="admin").first():
            db.session.add(Role(name="admin"))
        if not Role.query.filter_by(name="user").first():
            db.session.add(Role(name="user"))
        db.session.commit()

    # --- Root redirect ---
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dash.view"))   # ← MAJ du nom d’endpoint
        return redirect(url_for("auth.login"))

    # --- Template helpers for base.html ---
    @app.context_processor
    def inject_helpers():
        from flask import request

        def is_admin():
            return (
                getattr(current_user, "is_authenticated", False)
                and any(getattr(r, "name", "") == "admin" for r in getattr(current_user, "roles", []))
            )

        def is_active(prefix: str):
            return "active" if request.path.startswith(prefix) else ""

        return dict(is_admin=is_admin, is_active=is_active)

    # --- Security headers / allow Power BI iframe ---
    @app.after_request
    def add_csp_headers(resp):
        # Autoriser l’embed Power BI
        resp.headers["Content-Security-Policy"] = (
            "frame-ancestors 'self' https://app.powerbi.com https://*.powerbi.com"
        )
        # Éviter que X-Frame-Options bloque l'iframe
        resp.headers.pop("X-Frame-Options", None)
        return resp


    return app
