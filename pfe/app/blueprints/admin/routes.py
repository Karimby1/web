from flask import Blueprint, render_template, jsonify
from .. import roles_required

admin_bp = Blueprint("admin", __name__, template_folder="../../templates")

@admin_bp.route("/")
@roles_required("admin")
def panel():
    return render_template("admin.html")

@admin_bp.route("/predict", methods=["POST"])
@roles_required("admin")
def predict():
    # Placeholder response
    return jsonify({"status": "ok", "message": "Prediction placeholder"})
