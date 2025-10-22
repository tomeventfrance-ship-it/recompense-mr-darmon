import pandas as pd
from io import BytesIO

# Noms attendus (cibles) -> variantes possibles dans tes fichiers
COL_MAP = {
    "Période des données": ["Période des données", "Periode des donnees", "Période", "Période de données"],
    "Nom d’utilisateur": [
        "Nom d’utilisateur du/de la créateur(trice)",
        "Nom d'utilisateur du/de la créateur(trice)",
        "Nom d’utilisateur",
        "Nom d'utilisateur",
        "Nom d’utilisateur (créateur)"
    ],
    "Groupe": ["Groupe", "Groupe/Manager", "Groupe / Manager"],
    "Agent": ["Agent"],
    "Date d’établissement de la relation": [
        "Date d’établissement de la relation",
        "Date d'etablissement de la relation",
        "Date relation"
    ],
    "Diamants": ["Diamants", "Diamonds"],
    "Durée de LIVE (heures)": [
        "Durée de LIVE (heures)", "Duree de LIVE (heures)",
        "Durée de live (heures)", "Durée de LIVE", "Heures de LIVE"
    ],
    "Jours de passage en LIVE valides": [
        "Jours de passage en LIVE valides", "Jours de passage en LIVE", "Jours live", "Jours de live"
    ],
    "AL": ["AL", "Statut du diplôme", "Statut diplome", "Débutant non diplômé 90j"]
}

NEEDED_ORDER = [
    "Période des données",
    "Nom d’utilisateur",
    "Groupe",
    "Agent",
    "Date d’établissement de la relation",
    "Diamants",
    "Durée de LIVE (heures)",
    "Jours de passage en LIVE valides",
    "AL"
]

def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme les colonnes du fichier vers les noms cibles si elles matchent une variante connue."""
    original = list(df.columns)
    rename_map = {}
    for target, variants in COL_MAP.items():
        for col in original:
            if col.strip() in variants:
                rename_map[col] = target
                break
    df = df.rename(columns=rename_map)
    return df

def keep_needed_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = _standardize_columns(df)

    missing = [c for c in NEEDED_ORDER if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes : {', '.join(missing)}")

    # Ne garder que l'ordre demandé
    out = df[NEEDED_ORDER].copy()

    # Sécuriser types de deux colonnes souvent sources d'erreur
    # Durée et Jours -> numériques
    for num_col in ["Durée de LIVE (heures)", "Jours de passage en LIVE valides", "Diamants"]:
        out[num_col] = pd.to_numeric(out[num_col], errors="coerce").fillna(0)

    return out

def load_df(uploaded_file) -> pd.DataFrame:
    """Lit xlsx/xls/csv depuis Streamlit UploadedFile (ou chemin), sans altérer les données."""
    if hasattr(uploaded_file, "name"):  # Streamlit UploadedFile
        name = uploaded_file.name.lower()
        data = uploaded_file.read()
        bio = BytesIO(data)
        if name.endswith(".csv"):
            df = pd.read_csv(bio, sep=None, engine="python")
        elif name.endswith(".xlsx") or name.endswith(".xls"):
            df = pd.read_excel(bio, engine="openpyxl")
        else:
            raise ValueError("Format non supporté (utilisez .xlsx, .xls ou .csv).")
    else:
        # Chemin local éventuel
        path = str(uploaded_file)
        if path.lower().endswith(".csv"):
            df = pd.read_csv(path, sep=None, engine="python")
        elif path.lower().endswith(".xlsx") or path.lower().endswith(".xls"):
            df = pd.read_excel(path, engine="openpyxl")
        else:
            raise ValueError("Format non supporté (utilisez .xlsx, .xls ou .csv).")

    return df
