from __future__ import annotations
import io
import math
from typing import Optional, List, Tuple, Dict, Set

import numpy as np
import pandas as pd

# ---------- Helpers de colonnes : on tolère les variantes FR -------------
CANON = {
    "diamonds": ["diamant", "diamants", "diamond", "diamonds"],
    "hours": ["durée de live", "duree de live", "heure de live", "heures de live",
              "time in live", "live hours", "nb heures live"],
    "days": ["jours de passage en live", "jour de live", "jours actifs", "active days",
             "nb jours live", "jours"],
    "agent": ["agent", "e-mail de l’agent", "email agent", "mail agent", "col e"],
    "manager": ["groupe", "manager", "group", "col d"],
    "user": ["nom d’utilisateur", "username", "user", "tiktok name", "creator"],
    "al": ["al", "débutant 90j", "debutant non diplome 90j", "debutant 90", "AL"],
}

def _norm(s: str) -> str:
    return (s or "").strip().lower().replace("\xa0"," ").replace("’","'")

def _best_match(colnames: List[str], candidates: List[str]) -> Optional[str]:
    base = [_norm(c) for c in candidates]
    for c in colnames:
        n = _norm(c)
        if n in base:
            return c
    # contains
    for c in colnames:
        n = _norm(c)
        if any(x in n for x in base):
            return c
    return None

def _colmap(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    cols = list(df.columns)
    out = {}
    for key, candidates in CANON.items():
        out[key] = _best_match(cols, candidates)
    return out

# ------------------------- Lecture fichier -------------------------------
def load_df(uploaded) -> pd.DataFrame:
    """Lit CSV/XLSX depuis Streamlit uploader ou path, garde toutes les colonnes."""
    name = getattr(uploaded, "name", str(uploaded))
    if isinstance(uploaded, (bytes, bytearray)):
        bio = io.BytesIO(uploaded)
        uploaded = bio
    if name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)
    return df

# ---------------------- Historique 150k  ---------------------------------
def extract_150k_users(df: pd.DataFrame) -> Set[str]:
    roles = _colmap(df)
    c_diam = roles.get("diamonds")
    c_user = roles.get("user")
    if not c_diam or not c_user:
        return set()
    s = pd.to_numeric(df[c_diam], errors="coerce").fillna(0)
    return set(df.loc[s >= 150000, c_user].astype(str).str.strip())

def merge_history(*dfs: pd.DataFrame) -> Set[str]:
    users: Set[str] = set()
    for d in dfs:
        users |= extract_150k_users(d)
    return users

# ---------------------- Barèmes de récompenses ---------------------------
# Palier 1
P1 = [
    (35000, 74999, 1000),
    (75000, 149000, 2500),
    (150000, 199999, 5000),
    (200000, 299999, 6000),
    (300000, 399999, 7999),
    (400000, 499999, 12000),
    (500000, 599999, 15000),
    (600000, 699999, 18000),
    (700000, 799999, 21000),
    (800000, 899999, 24000),
    (900000, 999999, 26999),
    (1000000, 1499999, 30000),
    (1500000, 1999999, 44999),
    # >= 2,000,000 => 4%
]
# Palier 2
P2 = [
    (35000, 74999, 1000),
    (75000, 149000, 2500),
    (150000, 199999, 6000),
    (200000, 299999, 7999),
    (300000, 399999, 12000),
    (400000, 499999, 15000),
    (500000, 599999, 20000),
    (600000, 699999, 24000),
    (700000, 799999, 26999),
    (800000, 899999, 30000),
    (900000, 999999, 35000),
    (1000000, 1499999, 39999),
    (1500000, 1999999, 59999),
    # >= 2,000,000 => 4%
]

def montant_palier(diamants: float, table: List[Tuple[int,int,int]]) -> int:
    if diamants >= 2_000_000:
        return int(round(diamants * 0.04))
    for lo, hi, val in table:
        if lo <= diamants <= hi:
            return int(val)
    return 0

# Bonus débutant (une seule fois si AL = débutant non diplômé 90j)
def bonus_debutant(diamants: float, al_value: str) -> Tuple[str, int]:
    al = _norm(str(al_value))
    if "debut" in al or "90" in al:  # très tolérant
        if 75000 <= diamants <= 149999:
            return "Validé", 500
        if 150000 <= diamants <= 499999:
            return "Validé", 1088
        if 500000 <= diamants <= 2000000:
            return "Validé", 3000
    return "Non validé", 0

# ------------------- Calcul table Créateurs ------------------------------
def compute_creators_table(df_source: pd.DataFrame, history_users: Optional[Set[str]] = None) -> pd.DataFrame:
    roles = _colmap(df_source)
    c_diam = roles["diamonds"]
    c_hours = roles["hours"]
    c_days = roles["days"]
    c_agent = roles["agent"]
    c_manager = roles["manager"]
    c_user = roles["user"]
    c_al = roles["al"]

    # Colonnes obligatoires minimales
    needed = [c_diam, c_hours, c_days]
    if any(x is None for x in needed):
        missing = ["Diamants", "Durée de live (heures)", "Jours de passage en live"]
        raise ValueError(f"Colonnes manquantes : {', '.join([m for x,m in zip(needed,missing) if x is None])}")

    df = df_source.copy()

    # Casting
    df[c_diam]  = pd.to_numeric(df[c_diam], errors="coerce").fillna(0).astype(int)
    df[c_hours] = pd.to_numeric(df[c_hours], errors="coerce").fillna(0.0)
    df[c_days]  = pd.to_numeric(df[c_days], errors="coerce").fillna(0.0)

    if c_user and df[c_user].isnull().all():
        c_user = None  # inutilisable

    # Déjà 150k (historique si fourni, sinon sur le mois courant)
    if history_users is not None and c_user:
        deja_150k = df[c_user].astype(str).str.strip().isin(history_users)
    else:
        deja_150k = df[c_diam] >= 150000

    # Conditions d'activité
    # - Jamais 150k : 7 jours & 15 h
    # - Déjà 150k : 12 jours & 25 h
    act_days_req  = np.where(deja_150k, 12, 7)
    act_hours_req = np.where(deja_150k, 25, 15)

    actif = (df[c_days]  >= act_days_req) & (df[c_hours] >= act_hours_req) & (df[c_diam] >= 750)

    # Palier 2 (20 jours & 80 h) – nécessite aussi être actif
    palier2_valide = actif & (df[c_days] >= 20) & (df[c_hours] >= 80)

    # Récompenses paliers
    recomp_p1 = df[c_diam].apply(lambda x: montant_palier(x, P1)).astype(int)
    recomp_p2 = df[c_diam].apply(lambda x: montant_palier(x, P2)).astype(int)

    # Bonus débutant (AL)
    if not c_al:
        bonus_flag = pd.Series(["Non validé"]*len(df))
        bonus_mnt  = pd.Series([0]*len(df), dtype=int)
    else:
        tmp = df[c_al].astype(str)
        res = tmp.combine(df[c_diam], lambda al, d: bonus_debutant(float(d), al))
        bonus_flag = res.apply(lambda x: x[0])
        bonus_mnt  = res.apply(lambda x: x[1]).astype(int)

    # Récompense totale = (palier 2 si validé sinon palier 1) + bonus (si validé)
    recomp_base = np.where(palier2_valide, recomp_p2, recomp_p1).astype(int)
    recomp_tot  = (recomp_base + bonus_mnt).astype(int)

    # Sortie nettoyée (noms FR fixés)
    out = pd.DataFrame({
        "Nom d'utilisateur": df[c_user] if c_user else "",
        "Diamants": df[c_diam],
        "Durée de live (heures)": df[c_hours],
        "Jours de passage en live": df[c_days],
        "Agent": df[c_agent] if c_agent else "",
        "Groupe (Manager)": df[c_manager] if c_manager else "",
        "Créateur actif": np.where(actif, "Actif", "Inactif"),
        "Palier 2": np.where(palier2_valide, "Validé", "Non validé"),
        "Récompense palier 1": recomp_p1.astype(int),
        "Récompense palier 2": recomp_p2.astype(int),
        "Bonus débutant": bonus_flag,
        "Récompense totale": recomp_tot.astype(int),
        "Déjà 150k (historique)": np.where(deja_150k, "Oui", "Non"),
    })

    # Tri décroissant sur Récompense totale (puis Diamants)
    out = out.sort_values(["Récompense totale","Diamants"], ascending=[False, False]).reset_index(drop=True)
    return out

# -------------------- Agrégations Agents / Managers ----------------------
def _active_mask_for_agents(df: pd.DataFrame) -> Tuple[pd.Series, Dict[str,str]]:
    roles = _colmap(df)
    c_diam, c_hours, c_days, c_user = roles["diamonds"], roles["hours"], roles["days"], roles["user"]
    if any(x is None for x in [c_diam, c_hours, c_days]):
        raise ValueError("Colonnes minimales manquantes pour Agents/Managers.")
    # On réutilise la même logique d’activité “créateurs actifs” que ci-dessus
    deja_150k = (pd.to_numeric(df[c_diam], errors="coerce").fillna(0) >= 150000)
    days_req  = np.where(deja_150k, 12, 7)
    hours_req = np.where(deja_150k, 25, 15)
    mask = (
        (pd.to_numeric(df[c_days], errors="coerce").fillna(0)  >= days_req) &
        (pd.to_numeric(df[c_hours], errors="coerce").fillna(0) >= hours_req) &
        (pd.to_numeric(df[c_diam], errors="coerce").fillna(0) >= 750)
    )
    return mask, roles

def compute_agents_table(df_source: pd.DataFrame) -> pd.DataFrame:
    mask, roles = _active_mask_for_agents(df_source)
    c_agent, c_diam = roles["agent"], roles["diamonds"]
    if not c_agent:  # si pas d’agent => rien à calculer
        return pd.DataFrame()
    df = df_source.copy()
    df["Actif"] = np.where(mask, 1, 0)
    df["Diamants actifs"] = np.where(mask, pd.to_numeric(df[c_diam], errors="coerce").fillna(0), 0).astype(int)
    df["Diamants totaux"] = pd.to_numeric(df[c_diam], errors="coerce").fillna(0).astype(int)

    agg = df.groupby(c_agent, dropna=False).agg(
        Creators_actifs=("Actif", "sum"),
        Diamants_actifs=("Diamants actifs", "sum"),
        Diamants_totaux=("Diamants totaux", "sum"),
    ).reset_index().rename(columns={c_agent: "Agent"})

    # Récompense agents : seuil 200k ; 2% de 200k->4M ; 3% au-delà
    base = agg["Diamants_actifs"]
    reward = np.where(base <= 200000, 0,
               np.where(base <= 4000000,
                        (base) * 0.02,
                        (4000000 * 0.02) + (base - 4000000) * 0.03))
    agg["Récompense agent"] = reward.astype(int)

    # Tri
    agg = agg.sort_values(["Diamants_actifs","Diamants_totaux"], ascending=[False, False]).reset_index(drop=True)
    return agg

def compute_managers_table(df_source: pd.DataFrame) -> pd.DataFrame:
    mask, roles = _active_mask_for_agents(df_source)
    c_mgr, c_diam = roles["manager"], roles["diamonds"]
    if not c_mgr:
        return pd.DataFrame()
    df = df_source.copy()
    df["Actif"] = np.where(mask, 1, 0)
    df["Diamants actifs"] = np.where(mask, pd.to_numeric(df[c_diam], errors="coerce").fillna(0), 0).astype(int)
    df["Diamants totaux"] = pd.to_numeric(df[c_diam], errors="coerce").fillna(0).astype(int)

    agg = df.groupby(c_mgr, dropna=False).agg(
        Creators_actifs=("Actif", "sum"),
        Diamants_actifs=("Diamants actifs", "sum"),
        Diamants_totaux=("Diamants totaux", "sum"),
    ).reset_index().rename(columns={c_mgr: "Manager"})

    # Récompense managers : même barème bonus 3 = 5000 (déjà pris côté créateurs)
    base = agg["Diamants_actifs"]
    reward = np.where(base <= 200000, 0,
               np.where(base <= 4000000,
                        (base) * 0.02,
                        (4000000 * 0.02) + (base - 4000000) * 0.03))
    agg["Récompense manager"] = reward.astype(int)

    agg = agg.sort_values(["Diamants_actifs","Diamants_totaux"], ascending=[False, False]).reset_index(drop=True)
    return agg
