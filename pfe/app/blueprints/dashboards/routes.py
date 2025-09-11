from flask import Blueprint, render_template
from flask_login import login_required

dashboards_bp = Blueprint("dashboards", __name__, template_folder="../../templates")

# ➜ accepte /dashboards et /dashboards/
@dashboards_bp.route("", strict_slashes=False)
@dashboards_bp.route("/", strict_slashes=False)
@login_required
def view():
    return render_template("dashboards.html")

@dashboards_bp.route("/powerbi", strict_slashes=False)
@login_required
def powerbi():
    powerbi_url = "https://app.powerbi.com/view?r=REPLACE_WITH_YOUR_PUBLIC_LINK"
    return render_template("powerbi.html", powerbi_url=powerbi_url)
