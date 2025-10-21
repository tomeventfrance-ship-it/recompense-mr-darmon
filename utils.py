# utils.py
from __future__ import annotations
import io
from typing import Optional, Dict, List, Tuple, Set

import numpy as np
import pandas as pd

# =========================
#   Détection des colonnes
# =========================
CANON = {
    "diamonds": [
        "diamants", "diamant", "diamonds", "nombre de diamants", "nb_diamants", "total diamonds"
    ],
    "hours": [
        "durée de live (heures)", "duree de live (heures)", "heures de live", "heure de live",
        "duree de live", "durée live", "temps en live (h)", "live hours", "nb heures live"
    ],
    "days": [
        "jours de passage en live", "jour de passage en live", "jours actifs", "jours de live",
        "jours en live", "nb jours live", "live days", "jours"
    ],
    "agent": ["agent", "email agent", "mail agent", "e-mail agent", "colonne e", "col e"],
    "manager": ["groupe", "manager", "group", "groupe (manager)", "colonne d", "col d"],
    "user": ["nom d’utilisateur", "nom d'utilisateur", "username", "user", "pseudo", "tiktok name", "creator"],
    "al": ["al", "débutant non diplômé 90j", "debutant non diplome 90j", "debutant 90j", "debutant"]
}

def _norm(s: str) -> str:
    return (s or "").strip().lower().replace("\xa0"," ").replace("’","'")

def _best_match(colnames: List[str], candidates: List[str]) -> Optional[str]:
    base = [_norm(c) for c in candidates]
    # match exact
    for c in colnames:
        if _norm(c) in base:
            return c
    # contains
    for c in colnames:
        n = _norm(c)
        if any(x in n for x in base):
            return c
    return None

def _colmap(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    cols = list(df.columns)
    out: Dict[str, Optional[str]] = {}
    for key, cand in CANON.items():
        out[key] = _best_match(cols, cand)
    return out

# =========================
#       IO helpers
# =========================
def load_df(uploaded) -> pd.DataFrame:
    """Lit CSV/XLSX depuis uploader Streamlit ou path/bytes, conserve toutes les colonnes."""
    name = getattr(uploaded, "name", str(uploaded))
    if isinstance(uploaded, (bytes, bytearray)):
        uploaded = io.BytesIO(uploaded)
        name = "upload.bin"
    if name.lower().endswith(".csv"):
        return pd.read_csv(uploaded)
    return pd.read_excel(uploaded)

# =========================
#   Historique – >=150k
# =========================
def extract_150k_users(df: pd.DataFrame) -> Set[str]:
    roles = _colmap(df)
    c_diam, c_user = roles.get("diamonds"), roles.get("user")
    if not c_diam or not c_user:
        return set()
    s = pd.to_numeric(df[c_diam], errors="coerce").fillna(0)
    return set(df.loc[s >= 150000, c_user].astype(str).str.strip())

def merge_history(*dfs: pd.DataFrame) -> Set[str]:
    users: Set[str] = set()
    for d in dfs:
        users |= extract_150k_users(d)
    return users

# =========================
# Historique – bonus débutant (one-shot à vie)
# =========================
def extract_bonus_users(df: pd.DataFrame) -> Set[str]:
    # essaie de trouver le nom d'utilisateur
    name_col = None
    for c in df.columns:
        cl = _norm(str(c))
        if ("nom d'utilisateur" in cl) or ("nom d’utilisateur" in cl) or ("username" in cl) or (cl == "user") or ("pseudo" in cl):
            name_col = c; break
    if not name_col:
        return set()

    # heuristique: colonne(s) contenant "bonus" et "débutant"
    def _row_has_bonus(row) -> bool:
        for k, v in row.items():
            kl = _norm(str(k))
            if ("bonus" in kl) and ("debutant" in kl or "débutant" in kl):
                try:
                    return int(v) > 0
                except:
                    return str(v).strip().lower() in {"validé","valide","true","1","oui","yes","y","o"}
        return False

    mask = df.apply(_row_has_bonus, axis=1)
    return set(df.loc[mask, name_col].astype(str).str.strip())

def merge_bonus_history(*dfs: pd.DataFrame) -> Set[str]:
    s: Set[str] = set()
    for d in dfs:
        s |= extract_bonus_users(d)
    return s

# =========================
#     Barèmes / Bonus
# =========================
P1 = [
    (35000,   74999,   1000),
    (75000,  149999,   2500),
    (150000, 199999,   5000),
    (200000, 299999,   6000),
    (300000, 399999,   7999),
    (400000, 499999,  12000),
    (500000, 599999,  15000),
    (600000, 699999,  18000),
    (700000, 799999,  21000),
    (800000, 899999,  24000),
    (900000, 999999,  26999),
    (1000000,1499999, 30000),
    (1500000,1999999, 44999),
    # >= 2,000,000 -> 4%
]
P2 = [
    (35000,   74999,   1000),
    (75000,  149999,   2500),
    (150000, 199999,   6000),
    (200000, 299999,   7999),
    (300000, 399999,  12000),
    (400000, 499999,  15000),
    (500000, 599999,  20000),
    (600000, 699999,  24000),
    (700000, 799999,  26999),
    (800000, 899999,  30000),
    (900000, 999999,  35000),
    (1000000,1499999, 39999),
    (1500000,1999999, 59999),
    # >= 2,000,000 -> 4%
]

def montant_palier(d: float, table) -> int:
    if d >= 2_000_000:
        return int(round(d * 0.04))
    for lo, hi, val in table:
        if lo <= d <= hi:
            return int(val)
    return 0

def bonus_debutant_montant(d: float) -> int:
    if 75000 <= d <= 149999:
        return 500
    if 150000 <= d <= 499999:
        return 1088
    if 500000 <= d <= 2000000:
        return 3000
    return 0

# =========================
#     Créateurs
# =========================
def compute_creators_table(
    df_raw: pd.DataFrame,
    history_users_150k: Optional[Set[str]] = None,
    prior_bonus_users: Optional[Set[str]] = None
) -> pd.DataFrame:
    roles = _colmap(df_raw)
    c_diam, c_hours, c_days = roles["diamonds"], roles["hours"], roles["days"]
    c_agent, c_mgr, c_user, c_al = roles["agent"], roles["manager"], roles["user"], roles["al"]

    needed = [("Diamants", c_diam), ("Durée de live (heures)", c_hours), ("Jours de passage en live", c_days)]
    missing = [name for name, col in needed if col is None]
    if missing:
        raise ValueError("Colonnes manquantes : " + ", ".join(missing))

    df = df_raw.copy()
    df_diam  = pd.to_numeric(df[c_diam], errors="coerce").fillna(0).astype(int)
    df_hours = pd.to_numeric(df[c_hours], errors="coerce").fillna(0.0)
    df_days  = pd.to_numeric(df[c_days],  errors="coerce").fillna(0.0)

    # User/Agent/Manager
    user = df[c_user].astype(str) if c_user else pd.Series([""]*len(df))
    agent = df[c_agent].astype(str) if c_agent else pd.Series([""]*len(df))
    mgr   = df[c_mgr].astype(str)   if c_mgr   else pd.Series([""]*len(df))

    # Débutant (AL flag, très tolérant)
    if c_al:
        al = df[c_al].astype(str).str.strip().str.lower()
        is_debutant = al.isin({"1","true","vrai","oui","yes","y","o","débutant","debutant"})
    else:
        is_debutant = pd.Series([False]*len(df))

    # Déjà 150k (à vie) via historique si fourni, sinon approximation (diamants du mois)
    if history_users_150k is not None and c_user:
        deja_150k = user.astype(str).str.strip().isin(history_users_150k)
    else:
        deja_150k = df_diam >= 150000

    # Seuils d'activité
    req_days  = np.where(deja_150k | (~is_debutant), 12, 7)
    req_hours = np.where(deja_150k | (~is_debutant), 25, 15)
    actif = (df_diam >= 750) & (df_days >= req_days) & (df_hours >= req_hours)

    # Palier 2 (20j & 80h)
    p2_ok = actif & (df_days >= 20) & (df_hours >= 80)

    # Récompenses paliers (montants)
    p1_amt = df_diam.apply(lambda x: montant_palier(x, P1)).astype(int)
    p2_amt = df_diam.apply(lambda x: montant_palier(x, P2)).astype(int)

    # Application visibilité P1/P2 : P2 remplace P1 s’il est validé
    r_p1 = np.where(~p2_ok, p1_amt, 0).astype(int)
    r_p2 = np.where(p2_ok,  p2_amt, 0).astype(int)

    # Bonus débutant (one-shot à vie, seulement si AL et actif)
    bonus_now = np.array([bonus_debutant_montant(x) for x in df_diam], dtype=int)
    # Autorisé seulement si "débutant" et actif
    bonus_now = np.where(is_debutant & actif, bonus_now, 0)
    # Bloquer si déjà perçu historiquement
    if prior_bonus_users is not None and c_user:
        already = user.astype(str).str.strip().isin(prior_bonus_users).values
        bonus_now[already] = 0

    # Récompense totale
    total = (r_p1 + r_p2 + bonus_now).astype(int)

    out = pd.DataFrame({
        "Nom d’utilisateur": user,
        "Diamants": df_diam,
        "Durée de live (heures)": df_hours.astype(int),
        "Jours de passage en live": df_days.astype(int),
        "Agent": agent,
        "Groupe (Manager)": mgr,
        "Créateur actif": np.where(actif, "Actif", "Inactif"),
        "Palier 2": np.where(p2_ok, "Validé", "Non validé"),
        "Récompense palier 1": r_p1,
        "Récompense palier 2": r_p2,
        "Bonus débutant": bonus_now,
        "Récompense totale": total,
        "Déjà 150k (historique)": np.where(deja_150k, "Oui", "Non"),
    })

    # Masquer la colonne de palier non utilisée (affichage propre)
    out.loc[out["Récompense palier 2"] > 0, "Récompense palier 1"] = ""
    out.loc[out["Récompense palier 2"] == 0, "Récompense palier 2"] = ""

    out = out.sort_values(["Récompense totale","Diamants"], ascending=[False, False]).reset_index(drop=True)
    return out

# =========================
#     Agrégations
# =========================
def _active_mask(df: pd.DataFrame) -> Tuple[pd.Series, Dict[str, Optional[str]]]:
    roles = _colmap(df)
    c_diam, c_hours, c_days = roles["diamonds"], roles["hours"], roles["days"]
    if any(x is None for x in [c_diam, c_hours, c_days]):
        raise ValueError("Colonnes minimales manquantes (diamants/heures/jours).")
    d = pd.to_numeric(df[c_diam], errors="coerce").fillna(0)
    h = pd.to_numeric(df[c_hours], errors="coerce").fillna(0.0)
    j = pd.to_numeric(df[c_days],  errors="coerce").fillna(0.0)
    deja_150k = d >= 150000
    req_j = np.where(deja_150k, 12, 7)
    req_h = np.where(deja_150k, 25, 15)
    mask = (d >= 750) & (j >= req_j) & (h >= req_h)
    return mask, roles

def _reward_pct(base: pd.Series) -> np.ndarray:
    b = base.values.astype(float)
    return np.where(
        b <= 200000, 0,
        np.where(b <= 4000000, b*0.02, 4000000*0.02 + (b-4000000)*0.03)
    ).astype(int)

def compute_agents_table(df_source: pd.DataFrame) -> pd.DataFrame:
    mask, roles = _active_mask(df_source)
    c_agent, c_diam = roles["agent"], roles["diamonds"]
    if not c_agent:  # pas d'agent -> rien à agréger
        return pd.DataFrame()
    df = df_source.copy()
    d = pd.to_numeric(df[c_diam], errors="coerce").fillna(0).astype(int)
    df["Diamants_actifs"] = np.where(mask, d, 0)
    df["Diamants_totaux"] = d

    agg = df.groupby(df[c_agent].astype(str), dropna=False).agg(
        Creators_actifs  =("Diamants_actifs", lambda s: int((s>0).sum())),
        Diamants_actifs  =("Diamants_actifs", "sum"),
        Diamants_totaux  =("Diamants_totaux", "sum"),
    ).reset_index().rename(columns={c_agent: "Agent"})

    agg["Récompense agent"] = _reward_pct(agg["Diamants_actifs"])
    agg = agg.sort_values(["Diamants_actifs","Diamants_totaux"], ascending=[False, False]).reset_index(drop=True)
    return agg

def compute_managers_table(df_source: pd.DataFrame) -> pd.DataFrame:
    mask, roles = _active_mask(df_source)
    c_mgr, c_diam = roles["manager"], roles["diamonds"]
    if not c_mgr:
        return pd.DataFrame()
    df = df_source.copy()
    d = pd.to_numeric(df[c_diam], errors="coerce").fillna(0).astype(int)
    df["Diamants_actifs"] = np.where(mask, d, 0)
    df["Diamants_totaux"] = d

    agg = df.groupby(df[c_mgr].astype(str), dropna=False).agg(
        Creators_actifs  =("Diamants_actifs", lambda s: int((s>0).sum())),
        Diamants_actifs  =("Diamants_actifs", "sum"),
        Diamants_totaux  =("Diamants_totaux", "sum"),
    ).reset_index().rename(columns={c_mgr: "Manager"})

    agg["Récompense manager"] = _reward_pct(agg["Diamants_actifs"])
    agg = agg.sort_values(["Diamants_actifs","Diamants_totaux"], ascending=[False, False]).reset_index(drop=True)
    return agg
