# utils.py  — version autonome
# ---------------------------------------------
# Prend en charge :
# - Colonnes source attendues (et alias tolérants)
# - Calcul bonus créateurs (débutant ≤90j) : 75k/150k/500k -> +500/+1088/+3000
# - Non-cumul de bonus (on garde UNIQUEMENT le plus haut atteint)
# - Bonus Agents : palier2 -> +1000, palier3 -> +15000 (non cumulés)
# - Bonus Managers : palier2 -> +1000, palier3 -> +5000 (non cumulés)
# - Historique facultatif pour bloquer les bonus déjà utilisés et marquer les “confirmé 150k”
# - Tables créateurs / agents / managers

from __future__ import annotations
import re
import math
from typing import Optional, Dict, List
import pandas as pd
import numpy as np

# -------------------- Colonnes & mapping tolérant --------------------
CANON = {
    "period":        "Période des données",
    "username":      "Nom d’utilisateur",
    "group":         "Groupe",
    "agent":         "Agent",
    "relation_date": "Date d’établissement de la relation",
    "diamonds":      "Diamants",
    "live_hours":    "Durée de LIVE (heures)",
    "live_days":     "Jours de passage en LIVE valides",
    "al_status":     "Statut du diplôme",
}
REQUIRED = list(CANON.values())

ALIASES = {
    "period": [
        "Période des données", "periode des données", "période", "periode"
    ],
    "username": [
        "Nom d’utilisateur", "Nom d'utilisateur", "username", "utilisateur"
    ],
    "group": [
        "Groupe", "manager", "groupe/manager"
    ],
    "agent": [
        "Agent", "agent(e)"
    ],
    "relation_date": [
        "Date d’établissement de la relation", "date d'etablissement de la relation",
        "date relation"
    ],
    "diamonds": [
        "Diamants", "diamant", "diamonds"
    ],
    "live_hours": [
        "Durée de LIVE (heures)", "duree de live (heures)", "heures live", "durée live (heures)"
    ],
    "live_days": [
        "Jours de passage en LIVE valides", "jours de passage en live valides",
        "jours live", "jours de live"
    ],
    "al_status": [
        "Statut du diplôme", "al", "statut du diplome"
    ],
}

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Essaie de retrouver les colonnes canoniques (tolérance d’intitulés)."""
    colmap: Dict[str, str] = {}
    low = {c.strip().lower(): c for c in df.columns}
    for key, names in ALIASES.items():
        found = None
        for name in names:
            k = name.strip().lower()
            if k in low:
                found = low[k]
                break
        if found is not None:
            colmap[CANON[key]] = found

    # Conserve seulement les colonnes utiles; renomme en canonique
    keep = []
    for canon in CANON.values():
        if canon in colmap:
            keep.append(colmap[canon])
        else:
            # colonne manquante -> on la créera vide
            pass
    out = df.copy()
    for canon_key, canon_name in CANON.items():
        src = colmap.get(canon_name)
        if src is None:
            out[canon_name] = np.nan
        else:
            out[canon_name] = out[src]
    return out[REQUIRED].copy()

def _to_datetime(s):
    try:
        return pd.to_datetime(s, errors="coerce", utc=True).dt.tz_localize(None)
    except Exception:
        return pd.to_datetime(s, errors="coerce")

# -------------------- Règles de bonus --------------------
BONUS_THRESHOLDS = [
    (500_000, 3, 3000),  # palier 3
    (150_000, 2, 1088),  # palier 2
    (75_000,  1, 500),   # palier 1
]
AGENT_BONUS_BY_LEVEL   = {2: 1000, 3: 15000}
MANAGER_BONUS_BY_LEVEL = {2: 1000, 3: 5000}

def _beginner_eligible(al_status_val: str, relation_date_val: pd.Timestamp, ref_period: pd.Timestamp) -> bool:
    """
    Débutant si AL indique 'débutant' (ou vide) ET relation_date <= 90 jours à la fin de la période.
    On prend comme référence la fin de période détectée dans la colonne 'Période des données' si possible,
    sinon la date du jour (moins strict).
    """
    is_debutant = True
    if isinstance(al_status_val, str):
        txt = al_status_val.strip().lower()
        # S'il contient 'débutant' -> ok; s'il contient 'diplôm' -> pas débutant
        if "diplôm" in txt or "diplom" in txt:
            is_debutant = False
    # date relation
    if pd.isna(relation_date_val):
        return False if is_debutant else False
    try:
        delta = (ref_period.normalize() - relation_date_val.normalize()).days
    except Exception:
        return False
    return is_debutant and (delta <= 90) and (delta >= 0)

def _highest_bonus_level(diamonds: float) -> int:
    for th, level, _ in BONUS_THRESHOLDS:
        if pd.notna(diamonds) and float(diamonds) >= th:
            return level
    return 0

def _bonus_amount_for_level(level: int) -> int:
    for _, lev, amt in BONUS_THRESHOLDS:
        if level == lev:
            return amt
    return 0

# -------------------- Lecture historique (facultatif) --------------------
# Attendu (tolérant) : username, already_used_level (1/2/3), confirmed_150k (bool)
H_ALIASES = {
    "username": ["Nom d’utilisateur", "Nom d'utilisateur", "username"],
    "already_used_level": ["already_used_level", "bonus_deja_utilise_niveau", "bonus_used_level"],
    "confirmed_150k": ["confirmed_150k", "deja_150k", "a_deja_fait_150k"],
}
def _normalize_history(history_df: pd.DataFrame) -> pd.DataFrame:
    if history_df is None or len(history_df) == 0:
        return pd.DataFrame(columns=["username", "already_used_level", "confirmed_150k"])
    low = {c.strip().lower(): c for c in history_df.columns}
    out = pd.DataFrame()
    for key, alias_list in H_ALIASES.items():
        col = None
        for a in alias_list:
            if a.strip().lower() in low:
                col = low[a.strip().lower()]
                break
        if col is None:
            out[key] = np.nan
        else:
            out[key] = history_df[col]
    # types
    out["username"] = out["username"].astype(str).str.strip()
    out["already_used_level"] = pd.to_numeric(out["already_used_level"], errors="coerce").fillna(0).astype(int)
    out["confirmed_150k"] = out["confirmed_150k"].astype(str).str.strip().str.lower().isin(["1","true","vrai","yes","oui"])
    return out

# -------------------- Calcul principal : Créateurs --------------------
def compute_creators_table(df: pd.DataFrame, history_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    # 1) Normalisation colonnes
    src = _normalize_columns(df)

    # 2) Nettoyage types
    src[CANON["diamonds"]]   = pd.to_numeric(src[CANON["diamonds"]], errors="coerce").fillna(0)
    src[CANON["live_hours"]] = pd.to_numeric(src[CANON["live_hours"]], errors="coerce").fillna(0)
    src[CANON["live_days"]]  = pd.to_numeric(src[CANON["live_days"]], errors="coerce").fillna(0)
    src[CANON["relation_date"]] = _to_datetime(src[CANON["relation_date"]])

    # Période (référence pour les 90j)
    # On prend la dernière date trouvée dans "Période des données" si possible
    period_ref = pd.to_datetime(src[CANON["period"]], errors="coerce")
    if period_ref.notna().any():
        ref_date = period_ref.dropna().iloc[-1]
        try:
            ref_date = ref_date.tz_localize(None)
        except Exception:
            pass
    else:
        ref_date = pd.Timestamp.utcnow().tz_localize(None)

    # 3) Historique
    hist = _normalize_history(history_df)

    # 4) Lignes par créateur (agrégation au besoin, par 'username')
    #    On garde les max (diamants, heures, jours) si doublons. Agent & Groupe : premier non-null
    key_user = CANON["username"]
    agg = {
        CANON["diamonds"]:   "sum",
        CANON["live_hours"]: "sum",
        CANON["live_days"]:  "sum",
        CANON["relation_date"]: "min",
        CANON["period"]: "max",
        CANON["agent"]:  lambda s: s.dropna().iloc[0] if s.dropna().size else np.nan,
        CANON["group"]:  lambda s: s.dropna().iloc[0] if s.dropna().size else np.nan,
        CANON["al_status"]: lambda s: s.dropna().iloc[0] if s.dropna().size else np.nan,
    }
    g = src.groupby(key_user, dropna=False).agg(agg).reset_index()

    # 5) Statuts & bonus
    #   - confirmed_150k si historique, sinon si diamants >=150k
    hist_map_used = hist.set_index("username")["already_used_level"] if not hist.empty else pd.Series(dtype=int)
    hist_map_150k = hist.set_index("username")["confirmed_150k"]      if not hist.empty else pd.Series(dtype=bool)

    usernames = g[key_user].astype(str).str.strip()
    already_used_level = usernames.map(hist_map_used).fillna(0).astype(int)
    confirmed_150k = usernames.map(hist_map_150k).fillna(False)

    # Débutant éligible ce mois
    beginner_elig = g.apply(
        lambda r: _beginner_eligible(r[CANON["al_status"]], r[CANON["relation_date"]], ref_date),
        axis=1
    )

    # Niveau bonus atteint ce mois (diamants)
    levels = g[CANON["diamonds"]].apply(_highest_bonus_level).astype(int)

    # On interdit les bonus déjà consommés : on ne paie que si level > already_used_level ET débutant éligible
    payable_level = np.where((beginner_elig) & (levels > already_used_level), levels, 0).astype(int)
    bonus_amount = pd.Series(payable_level).apply(_bonus_amount_for_level).astype(int)

    # Confirmé 150k : si pas issu de l’historique, on marque automatiquement s’il atteint 150k ce mois
    confirmed_now = (g[CANON["diamonds"]] >= 150_000)
    confirmed_150k = confirmed_150k | confirmed_now

    # Bonus Agents / Managers selon le PLUS HAUT palier atteint (non cumulés)
    agent_bonus   = pd.Series(np.select(
        [payable_level==3, payable_level==2],
        [AGENT_BONUS_BY_LEVEL[3], AGENT_BONUS_BY_LEVEL[2]],
        default=0
    ), index=g.index).astype(int)

    manager_bonus = pd.Series(np.select(
        [payable_level==3, payable_level==2],
        [MANAGER_BONUS_BY_LEVEL[3], MANAGER_BONUS_BY_LEVEL[2]],
        default=0
    ), index=g.index).astype(int)

    # 6) Sortie créateurs
    out = pd.DataFrame({
        CANON["period"]:        g[CANON["period"]],
        CANON["username"]:      g[CANON["username"]],
        CANON["group"]:         g[CANON["group"]],
        CANON["agent"]:         g[CANON["agent"]],
        CANON["relation_date"]: g[CANON["relation_date"]],
        CANON["diamonds"]:      g[CANON["diamonds"]].astype(int),
        CANON["live_hours"]:    g[CANON["live_hours"]].astype(int),
        CANON["live_days"]:     g[CANON["live_days"]].astype(int),
        CANON["al_status"]:     g[CANON["al_status"]],
        "Débutant éligible (≤90j)": beginner_elig.astype(bool),
        "Palier bonus atteint (1/2/3)": levels,
        "Palier bonus payé (1/2/3)": payable_level,
        "Montant bonus (diamants)": bonus_amount,
        "Bonus Agent (diamants)": agent_bonus,
        "Bonus Manager (diamants)": manager_bonus,
        "Confirmé 150k": confirmed_150k.astype(bool),
    })

    return out

# -------------------- Agents : agrégation --------------------
def compute_agents_table(creators_df: pd.DataFrame) -> pd.DataFrame:
    if creators_df is None or creators_df.empty:
        return pd.DataFrame(columns=["Agent", "Créateurs concernés", "Bonus total (diamants)"])
    df = creators_df.copy()
    df["Agent"] = df["Agent"].fillna("—")
    df["Bonus Agent (diamants)"] = pd.to_numeric(df.get("Bonus Agent (diamants)"), errors="coerce").fillna(0).astype(int)
    agg = df.groupby("Agent", dropna=False).agg(
        **{
            "Bonus total (diamants)": ("Bonus Agent (diamants)", "sum"),
            "Créateurs concernés":    ("Nom d’utilisateur", "nunique")
        }
    ).reset_index().sort_values("Bonus total (diamants)", ascending=False)
    return agg

# -------------------- Managers : agrégation --------------------
def compute_managers_table(creators_df: pd.DataFrame) -> pd.DataFrame:
    if creators_df is None or creators_df.empty:
        return pd.DataFrame(columns=["Groupe", "Créateurs concernés", "Bonus total (diamants)"])
    df = creators_df.copy()
    df["Groupe"] = df["Groupe"].fillna("—")
    df["Bonus Manager (diamants)"] = pd.to_numeric(df.get("Bonus Manager (diamants)"), errors="coerce").fillna(0).astype(int)
    agg = df.groupby("Groupe", dropna=False).agg(
        **{
            "Bonus total (diamants)": ("Bonus Manager (diamants)", "sum"),
            "Créateurs concernés":    ("Nom d’utilisateur", "nunique")
        }
    ).reset_index().sort_values("Bonus total (diamants)", ascending=False)
    return agg
