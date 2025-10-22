import pandas as pd
from io import BytesIO

# --- utils.py : chargement + mapping colonnes robustes ---

from unidecode import unidecode
import pandas as pd

def _norm(s: str) -> str:
    return (
        unidecode(str(s)).replace("\xa0"," ").replace("’","'").strip().lower()
    )

def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_norm(c) for c in df.columns]
    return df

def _pick(df: pd.DataFrame, aliases) -> str:
    """Retourne le nom de colonne normalisé présent dans df parmi les alias."""
    cols = set(df.columns)
    for a in aliases:
        n = _norm(a)
        if n in cols:
            return n
    raise KeyError(f"Colonne manquante (attendues parmi: {aliases})")

def load_df(uploaded_file) -> pd.DataFrame:
    # lit xlsx/csv puis normalise les en-têtes
    if hasattr(uploaded_file, "name") and str(uploaded_file.name).lower().endswith(".csv"):
        raw = pd.read_csv(uploaded_file)
    else:
        raw = pd.read_excel(uploaded_file, engine="openpyxl")
    df = _normalize_cols(raw)

    # aliases tolérés (tous les accents/espaces/apostrophes)
    col_periode   = _pick(df, ["periode des donnees"])
    col_user      = _pick(df, ["nom d'utilisateur du/de la createur(trice)", "nom d'utilisateur", "username"])
    col_groupe    = _pick(df, ["groupe/manager", "groupe"])
    col_agent     = _pick(df, ["agent (col.e)", "agent"])
    col_date_rel  = _pick(df, [
        "date d'etablissement de la relation",   # Colonne F (exacte)
        "date d’etablissement de la relation",   # apostrophe typographique
        "date etablissement relation"
    ])
    col_diamants  = _pick(df, ["diamants"])
    col_duree     = _pick(df, [
        "duree de live (heures)", "duree de live", "duree live (heures)", "duree live"
    ])
    col_jours     = _pick(df, [
        "jours de passage en live valides", "jours de passage en live", "jours live"
    ])
    col_al        = _pick(df, ["al = debutant non diplome 90j", "al", "statut du diplome"])

    # sélection + renommage propre
    df = df[[col_periode, col_user, col_groupe, col_agent,
             col_date_rel, col_diamants, col_duree, col_jours, col_al]].rename(columns={
        col_periode: "periode",
        col_user: "username",
        col_groupe: "groupe",
        col_agent: "agent",
        col_date_rel: "date_relation",
        col_diamants: "diamants",
        col_duree: "heures_live",
        col_jours: "jours_live",
        col_al: "al"
    })

    # types
    df["date_relation"] = pd.to_datetime(df["date_relation"], errors="coerce", dayfirst=True, utc=False)
    for c in ["diamants","heures_live","jours_live"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # al → bool (débutant non diplômé 90j)
    df["al"] = df["al"].astype(str).str.lower().isin(["1","true","oui","yes","o","vrai","debutant","non diplome","non diplome 90j","debutant non diplome 90j"])

    return df

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

