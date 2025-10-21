import io
import re
import pandas as pd
import numpy as np

# --------- MAPPING STRICT : on ne lit que ce qui sert ------------
CANDIDATES = {
    "diamants": ["Diamants","Total diamants","Nombre de diamants","Diamonds"],
    "heures": ["Durée de live (heures)","Durée de live","Heures de live","Temps de live (h)"],
    "jours": ["Jours de passage en live","Jours de live","Nombre de jours de live"],
    "agent": ["Agent","Agent (col.E)","Agent(e)"],
    "manager": ["Groupe/Manager","Manager","Groupe","Groupe (col.D)"],
    "user": ["Nom d’utilisateur","Nom d'utilisateur","Username","Utilisateur","Pseudo"],
    "al": ["AL","Débutant non diplômé 90j","Debutant non diplome 90j"],
    "deja150": ["déjà 150k","deja 150k","a deja fait 150k"],
    "bonus_used": ["bonus_deja_utilise","bonus déjà utilisé","bonus utilise","bonus_used"]
}

CANON = ["user","manager","agent","diamants","heures","jours","al","deja150","bonus_used"]

def _norm(s: str) -> str:
    s = str(s).lower()
    s = s.encode("ascii","ignore").decode()
    s = re.sub(r"[^a-z0-9 ]+"," ",s)
    s = re.sub(r"\s+"," ",s).strip()
    return s

def _pick(df: pd.DataFrame, keys) -> str|None:
    norm = {_norm(c): c for c in df.columns}
    for k in keys:
        n = _norm(k)
        if n in norm:
            return norm[n]
    for k in keys:
        nk = _norm(k)
        for c in df.columns:
            if nk in _norm(c):
                return c
    return None

def load_df(file_like) -> pd.DataFrame:
    """Lit CSV/XLSX, ne garde QUE les colonnes utiles, les renomme de façon canonique."""
    name = getattr(file_like, "name", "")
    if isinstance(file_like, (bytes, bytearray)):
        bio = io.BytesIO(file_like); bio.name = name; file_like = bio

    if str(name).lower().endswith(".csv"):
        raw = pd.read_csv(file_like)
    else:
        raw = pd.read_excel(file_like)

    found = {}
    for canon, cand in CANDIDATES.items():
        col = _pick(raw, cand)
        if col is not None:
            found[canon] = col

    missing_core = [k for k in ["diamants","heures","jours"] if k not in found]
    if missing_core:
        pretty = {"diamants":"Diamants","heures":"Durée de live (heures)","jours":"Jours de passage en live"}
        raise ValueError("Colonnes manquantes: " + ", ".join(pretty[k] for k in missing_core))

    use_cols = [found[k] for k in CANON if k in found]
    df = raw.loc[:, use_cols].rename(columns={found[k]: k for k in found})

    for opt in CANON:
        if opt not in df.columns:
            df[opt] = ""

    # types numériques
    for num in ["diamants","heures","jours"]:
        df[num] = pd.to_numeric(df[num], errors="coerce").fillna(0)

    # conversion texte SÉCURISÉE
    for s in ["user","agent","manager","al","deja150","bonus_used"]:
        if s in df.columns and not isinstance(df[s], pd.DataFrame):
            df[s] = df[s].astype(str).replace({"nan":""}).str.strip()
        else:
            df[s] = ""

    return df[CANON]

# -------------- reste du script identique à la version précédente --------------
# (palier, bonus, compute_creators_table, compute_agents_table, etc.)
