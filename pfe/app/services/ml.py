# app/services/ml.py
from __future__ import annotations
from typing import Dict, Any, Optional, Iterable
import os
import pandas as pd

# ---------- Réglages ----------
DEFAULT_MODEL_PATH = os.getenv("ML_MODEL_PATH", os.path.join("instance", "models", "price_xgb.joblib"))
CHANNELS: Iterable[str] = ("retail", "corporate", "wholesale")
# Facteurs appliqués si le modèle n'a pas de feature "segment" / "channel"
CHANNEL_FACTORS = {"retail": 1.00, "corporate": 0.95, "wholesale": 0.90}


def _mock_three_tables(product: str, month: int, year: int) -> Dict[str, pd.DataFrame]:
    """Génère 3 DataFrames 'mock' en format large (product + colonnes d'années)."""
    years = [int(year), int(year) + 1, int(year) + 2]
    base_seed = sum(ord(c) for c in product.lower()) + int(month) * 7 + int(year) * 3
    base_price = 80 + (base_seed % 40) + (int(month) * 0.5)

    out: Dict[str, pd.DataFrame] = {}
    for ch, mult in CHANNEL_FACTORS.items():
        start = base_price * mult
        vals = [round(float(start * (1 + 0.03 * i)), 2) for i in range(len(years))]
        row = {"product": product, **{str(y): v for y, v in zip(years, vals)}}
        out[ch] = pd.DataFrame([row], columns=["product", *(str(y) for y in years)])
    return out


def _safe_load_artifact(path: str) -> Optional[Any]:
    """Charge un artefact joblib sans faire planter l'appli."""
    try:
        import joblib  # lazy import
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        if not os.path.exists(path):
            return None
        return joblib.load(path)
    except Exception:
        return None


def _artifact_parts(artifact: Any) -> tuple[Optional[Any], Optional[list[str]]]:
    """
    Essaie d'extraire (pipeline_or_model, features) depuis l'artefact.
    - Idéal : un Pipeline entraîné (encodages + modèle).
    - À défaut : un dict {"pipe": ..., "features": [...] } ou {"model": ..., "xgb_model": ...}.
    """
    pipe = None
    feat = None

    if artifact is None:
        return None, None

    if isinstance(artifact, dict):
        pipe = artifact.get("pipe") or artifact.get("pipeline") or artifact.get("model") or artifact.get("xgb_model")
        feat = artifact.get("features")
    else:
        pipe = artifact
        # essaye d'inférer les noms de features si dispo
        feat = getattr(artifact, "feature_names_in_", None)
        if feat is not None:
            feat = list(map(str, feat))

    return pipe, feat


def _predict_with_artifact(artifact: Any, product: str, month: int, year: int) -> Optional[Dict[str, pd.DataFrame]]:
    """
    Utilise l'artefact si possible. Retourne None si on ne peut pas prédire (on tombera alors en mock).
    On construit 3 tableaux 'format large' (product + colonnes d'années) pour les canaux retail/corporate/wholesale.
    """
    pipe, features = _artifact_parts(artifact)
    if pipe is None:
        return None

    years = [int(year), int(year) + 1, int(year) + 2]

    # Devine si le modèle attend une feature de type segment
    # noms possibles : "segment", "channel", "type_client", etc.
    seg_col_candidates = {"segment", "channel", "type_client", "client_type", "category"}
    seg_col = None
    if isinstance(features, list):
        norm = {str(c).strip().lower(): c for c in features}
        for k in seg_col_candidates:
            if k in norm:
                seg_col = norm[k]
                break

    # Devine les colonnes de base
    prod_col = None
    month_col = None
    year_col = None
    if isinstance(features, list):
        fset = {str(c).strip().lower(): c for c in features}
        prod_col = fset.get("product") or fset.get("produit") or fset.get("name") or fset.get("designation")
        month_col = fset.get("month") or fset.get("mois")
        year_col = fset.get("year") or fset.get("annee") or fset.get("année")

    # Fallbacks si pas trouvés
    prod_col = prod_col or "product"
    month_col = month_col or "month"
    year_col = year_col or "year"

    out: Dict[str, pd.DataFrame] = {}

    for ch in CHANNELS:
        values = []
        for y in years:
            row = {
                prod_col: product,
                month_col: int(month),
                year_col: int(y),
            }
            if seg_col:
                row[seg_col] = ch  # on fournit le segment au modèle si attendu

            X = pd.DataFrame([row])

            try:
                # Prédiction via pipeline (transformations incluses)
                pred = float(pipe.predict(X)[0])
            except Exception:
                # Si ça échoue (features non concordantes, encodage manquant…), on abandonne l’artefact.
                return None

            values.append(round(pred, 2))

        # Si le modèle n'utilise PAS de segment, on applique quand même un petit facteur par canal
        if not seg_col:
            factor = CHANNEL_FACTORS.get(ch, 1.0)
            values = [round(v * factor, 2) for v in values]

        row_wide = {"product": product, **{str(y): v for y, v in zip(years, values)}}
        out[ch] = pd.DataFrame([row_wide], columns=["product", *(str(y) for y in years)])

    return out


def run_prediction(product: str, month: int, year: int) -> Dict[str, pd.DataFrame]:
    """
    Retourne 3 DataFrames (retail/corporate/wholesale) au *format large*.
    - Si un modèle joblib est disponible et exploitable → on s’en sert.
    - Sinon → fallback sur des valeurs *mock* stables.
    """
    product = (product or "").strip()
    if not product:
        raise ValueError("product is required")
    month = int(month)
    year = int(year)
    if not (1 <= month <= 12):
        raise ValueError("month must be between 1 and 12")

    # 1) Tente d'utiliser un modèle exporté
    artifact = _safe_load_artifact(DEFAULT_MODEL_PATH)
    tables = _predict_with_artifact(artifact, product, month, year)
    if tables is not None:
        return tables

    # 2) Sinon, valeurs mock
    return _mock_three_tables(product, month, year)


# --- Exécution locale ---
if __name__ == "__main__":
    dfs = run_prediction("Example Product", month=1, year=2025)
    for k, df in dfs.items():
        print(f"\n[{k}]")
        print(df)
