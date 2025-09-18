from flask import Blueprint, render_template, jsonify, request
from app.extensions import db
from app.models.user import User, Role
from .. import roles_required
from app.decorators import roles_required

admin_bp = Blueprint("admin", __name__, template_folder="../../templates")

# --- Page Admin ---
@admin_bp.route("/")
@roles_required("admin")
def panel():
    return render_template("admin.html")

# --- Placeholder prédiction ---
@admin_bp.route("/predict", methods=["POST"])
@roles_required("admin")
def predict():
    return jsonify({"status": "ok", "message": "Prediction placeholder"})

# --- API: List Users ---
@admin_bp.route("/users", methods=["GET"])
@roles_required("admin")
def list_users():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])

# --- API: Create User ---
@admin_bp.route("/users", methods=["POST"])
@roles_required("admin")
def create_user():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    role_name = (data.get("role") or "staff").strip()

    if not email or not password or not role_name:
        return jsonify({"error": "email, password et role requis"}), 400
    if len(password) < 6:
        return jsonify({"error": "mot de passe trop court (min 6)"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email existe déjà"}), 409

    role = Role.query.filter_by(name=role_name).first()
    if not role:
        role = Role(name=role_name)
        db.session.add(role)

    user = User(email=email)
    user.set_password(password)
    user.roles = [role]

    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


# --- API: Update User ---
@admin_bp.route("/users/<int:user_id>", methods=["PUT"])
@roles_required("admin")
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json() or {}

    new_email = (data.get("email") or "").strip()
    new_role  = (data.get("role") or "").strip()
    new_pwd   = (data.get("password") or "").strip()  # optionnel

    # email
    if new_email:
        if new_email != user.email and User.query.filter_by(email=new_email).first():
            return jsonify({"error": "email existe déjà"}), 409
        user.email = new_email

    # role
    if new_role:
        role = Role.query.filter_by(name=new_role).first()
        if not role:
            role = Role(name=new_role)
            db.session.add(role)
        user.roles = [role]

    # password (optionnel)
    if new_pwd:
        if len(new_pwd) < 6:
            return jsonify({"error": "mot de passe trop court (min 6)"}), 400
        user.set_password(new_pwd)

    db.session.commit()
    return jsonify(user.to_dict())


# --- API: Delete User ---
@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@roles_required("admin")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return ("", 204)
