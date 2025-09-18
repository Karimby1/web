# app/blueprints/dashboards/routes.py
"""
Dashboards blueprint
- /dashboards/                -> page d'accueil
- /dashboards/powerbi         -> embed Power BI
- /dashboards/prediction      -> formulaire (admin)
- /dashboards/prediction/run  -> API (admin)
- /dashboards/prediction/download/<run_id>/<filename> -> download (admin)
"""
import os
import uuid
import pandas as pd
from flask import (
    Blueprint, render_template, request, jsonify, current_app,
    send_file, abort, url_for
)
from flask_login import login_required
from app.decorators import roles_required
from app.services.ml import run_prediction  # service ML qui retourne des DataFrames

# Nom interne UNIQUE = "dash" et on met le prefix ici
dash_bp = Blueprint(
    "dash",
    __name__,
    template_folder="../../templates",
    url_prefix="/dashboards",
)

# === PAGE PRINCIPALE ==========================================================
@dash_bp.route("/", strict_slashes=False, endpoint="view")
@login_required
def view():
    """Accueil des dashboards"""
    return render_template("dashboards.html")


# === POWER BI ================================================================
@dash_bp.route("/powerbi", strict_slashes=False, endpoint="powerbi")
@login_required
def powerbi():
    """Affiche un embed Power BI"""
    powerbi_url = current_app.config.get(
        "POWERBI_EMBED_URL",
        # fallback (remplace par ton lien si besoin)
        "https://app.powerbi.com/reportEmbed?reportId=3013134f-5f30-4f7f-81ad-14f4faa1b04e&autoAuth=true&ctid=604f1a96-cbe8-43f8-abbf-f8eaf5d85730",
    )
    return render_template("powerbi.html", powerbi_url=powerbi_url)


# === PREDICTION (ADMIN) ======================================================
@dash_bp.get("/prediction", endpoint="prediction")
@roles_required("admin")
def prediction():
    """Formulaire de prédiction (réservé admin)"""
    return render_template("prediction.html")


@dash_bp.post("/prediction/run", endpoint="prediction_run")
@roles_required("admin")
def prediction_run():
    """Exécute le modèle et renvoie fichiers + tableau mensuel jusqu'au mois sélectionné."""
    import os, uuid
    from datetime import datetime
    import pandas as pd
    from flask import current_app, jsonify, url_for, request
    from app.services.ml import run_prediction

    data = request.get_json(silent=True) or {}
    product = (data.get("product") or "").strip()

    try:
        month_sel = int(data.get("month") or 1)         # <-- mois FIN (1..12)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid month."}), 400
    try:
        year_sel = int(data.get("year"))                # <-- année FIN d’horizon
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid year."}), 400

    if not product:
        return jsonify({"error": "Product name is required."}), 400
    if not 1 <= month_sel <= 12:
        return jsonify({"error": "Month must be between 1 and 12."}), 400

    # --- HORIZON: de l'année courante jusqu'à l'année choisie (bornée à +2) ---
    current_year = datetime.utcnow().year
    year_sel = max(current_year, min(year_sel, current_year + 2))
    target_years = list(range(current_year, year_sel + 1))

    # 1) Générer les prédictions annuelles (mock) à partir de l’année courante.
    try:
        dfs = run_prediction(product=product, month=month_sel, year=current_year)
    except Exception as e:
        return jsonify({"error": f"Model error: {e}"}), 500

    # 2) Sauvegarde des 3 xlsx
    os.makedirs(current_app.instance_path, exist_ok=True)
    root = os.path.join(current_app.instance_path, "predictions")
    os.makedirs(root, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    out_dir = os.path.join(root, run_id)
    os.makedirs(out_dir, exist_ok=True)

    files_meta = []
    mapping = {"retail": "retail.xlsx", "corporate": "corporate.xlsx", "wholesale": "wholesale.xlsx"}
    for key, filename in mapping.items():
        df = dfs.get(key)
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            continue
        path = os.path.join(out_dir, filename)
        df.to_excel(path, index=False)  # nécessite openpyxl
        files_meta.append({
            "label": key,
            "filename": filename,
            "url": url_for("dash.prediction_download", run_id=run_id, filename=filename)
        })

    # --------- utilitaires (inchangés) ----------
    def _norm(s): return (str(s) or "").strip().lower()

    def _guess_product_col(df: pd.DataFrame) -> str:
        cand = [c for c in df.columns if _norm(c) in {"product", "produit", "name", "designation", "item"}]
        if cand: return cand[0]
        for c in df.columns:
            if df[c].dtype == "object":
                return c
        return df.columns[0]

    def _value_from_wide(row: pd.Series, y: int):
        for k in (str(y), y):
            if k in row.index:
                v = pd.to_numeric(row[k], errors="coerce")
                return None if pd.isna(v) else float(v)
        return None

    def _find_value_for_year(df: pd.DataFrame, y: int):
        if df is None or df.empty:
            return None
        prod_col = _guess_product_col(df)
        mask = df[prod_col].astype(str).str.strip().str.lower() == _norm(product)
        if not mask.any():
            return None
        row = df[mask].iloc[0]
        return _value_from_wide(row, y)

    # --------- NOUVEAU : expansion mensuelle 1..month_sel ----------
    # petite saisonnalité douce (≈ -6% -> +6% sur l'année)
    def _seasonality_factor(m: int) -> float:
        # m ∈ [1..12] ; centre sur juin (~6)
        return 1.0 + 0.06 * ((m - 6) / 6.0)

    table_rows = []
    per_year_monthly_avgs = {y: [] for y in target_years}

    for y in target_years:
        # valeurs annuelles issues des 3 dataframes
        yr_retail    = _find_value_for_year(dfs.get("retail"), y)
        yr_corporate = _find_value_for_year(dfs.get("corporate"), y)
        yr_wholesale = _find_value_for_year(dfs.get("wholesale"), y)

        for m in range(1, month_sel + 1):
            f = _seasonality_factor(m)
            r = None if yr_retail    is None else round(yr_retail    * f, 2)
            c = None if yr_corporate is None else round(yr_corporate * f, 2)
            w = None if yr_wholesale is None else round(yr_wholesale * f, 2)
            vals = [v for v in (r, c, w) if v is not None]
            avg = round(sum(vals)/len(vals), 2) if vals else None

            if avg is not None:
                per_year_monthly_avgs[y].append(avg)

            table_rows.append({
                "year": y,
                "month": m,
                "retail": r,
                "corporate": c,
                "wholesale": w,
                "avg": avg,
            })

    # KPI = moyenne des moyennes mensuelles par année dans la fenêtre
    kpi_names = {
        current_year: "current_year",
        current_year + 1: "next_year",
        current_year + 2: "year_plus_2",
    }
    kpis = {}
    for y in target_years:
        arr = per_year_monthly_avgs.get(y) or []
        k = kpi_names.get(y)
        if k and arr:
            kpis[k] = round(sum(arr)/len(arr), 2)

    return jsonify({
        "status": "ok",
        "result": {
            "product": product,
            "month": month_sel,        # mois FIN (utilisé par l’UI)
            "year": year_sel,          # année FIN
            "base_year": current_year, # année de départ
            "table": table_rows,       # <-- maintenant une ligne par (année, mois 1..N)
            "kpis": kpis,
            "files": files_meta
        }
    }), 200



@dash_bp.get("/prediction/download/<run_id>/<path:filename>", endpoint="prediction_download")
@roles_required("admin")
def prediction_download(run_id: str, filename: str):
    """Télécharge un fichier Excel généré pour un run_id (réservé admin)"""
    # Sécurisation basique
    if ".." in filename or filename.startswith("/"):
        abort(400)

    base = os.path.join(current_app.instance_path, "predictions", run_id)
    full_path = os.path.join(base, filename)
    if not os.path.isfile(full_path):
        abort(404)

    return send_file(
        full_path,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        max_age=0,
    )
