# utils.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import io
import math
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

import numpy as np
import pandas as pd

# -------------------- Colonnes & mapping tolérant --------------------
CANON = {
    "period": "Période des données",
    "username": "Nom d’utilisateur",
    "group": "Groupe",
    "agent": "Agent",
    "relation_date": "Date d’établissement de la relation",
    "diamonds": "Diamants",
    "live_hours": "Durée de LIVE (heures)",
    "live_days": "Jours de passage en LIVE valides",
    "al_status": "Statut du diplôme",
}
REQUIRED = list(CANON.values())

ALIASES = {
    "period": [
        "période des données", "periode des donnees", "période", "period"
    ],
    "username": [
        "nom d’utilisateur", "nom d'utilisateur", "créateur", "createur",
        "nom", "username", "user", "id créateur", "id createur"
    ],
    "group": [
        "groupe", "manager", "groupe/manager", "group"
    ],
    "agent": [
        "agent", "agence", "agent(e)"
    ],
    "relation_date": [
        "date d’établissement de la relation", "date d'etablissement de la relation",
        "date relation", "date relation tiktok", "date debut gestion", "date de début de gestion"
    ],
    "diamonds": [
        "diamants", "diamonds", "total diamants"
    ],
    "live_hours": [
        "durée de live (heures)", "duree de live (heures)", "heures de live",
        "duree live", "durée live", "heures"
    ],
    "live_days": [
        "jours de passage en live valides", "jours de passage en live", "jours live",
        "jours actifs", "nb jours live"
    ],
    "al_status": [
        "statut du diplôme", "statut diplome", "al"
    ],
}

def _normalize_colname(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("’", "'")
    s = re.sub(r"\s+", " ", s)
    return s

def _auto_map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Essaie de renommer les colonnes du fichier source vers les noms français attendus dans CANON."""
    cols = list(df.columns)
    norm = {_normalize_colname(c): c for c in cols}
    rename: Dict[str, str] = {}

    # pour chaque clé canonique, tenter de trouver une colonne source
    for key, fr_name in CANON.items():
        # correspondance exacte FR ?
        if fr_name in cols:
            continue  # déjà bon
        # alias ?
        candidates = ALIASES.get(key, [])
        found_src = None
        for cand in candidates:
            cand_norm = _normalize_colname(cand)
            if cand_norm in norm:
                found_src = norm[cand_norm]
                break
        if found_src is not None:
            rename[found_src] = fr_name

    if rename:
        df = df.rename(columns=rename)
    return df

def ensure_df(obj) -> Optional[pd.DataFrame]:
    """Sécurise la conversion vers DataFrame ; renvoie None si vide/inexploitable."""
    if obj is None:
        return None
    if isinstance(obj, pd.DataFrame):
        return obj.copy()
    # streamlit uploaded file (SpooledTemporaryFile) -> lire via pandas
    try:
        return pd.read_excel(obj)  # essayer xlsx
    except Exception:
        try:
            if hasattr(obj, "read"):
                obj.seek(0)
                return pd.read_csv(obj)
        except Exception:
            pass
    return None

def normalize_source(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise colonnes, types et filtre aux colonnes requises utiles aux calculs."""
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED)

    df = _auto_map_columns(df)

    # forcer la présence des colonnes requises (si manquantes, créer vides)
    for fr_col in REQUIRED:
        if fr_col not in df.columns:
            df[fr_col] = np.nan

    # typer
    # dates
    for col in ["Période des données", "Date d’établissement de la relation"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # numériques
    for col in ["Diamants", "Durée de LIVE (heures)", "Jours de passage en LIVE valides"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # strings
    for col in ["Nom d’utilisateur", "Groupe", "Agent", "Statut du diplôme"]:
        if col in df.columns:
            df[col] = df[col].astype(str).fillna("").replace("nan", "")

    # ne garder QUE les colonnes utiles
    df = df[REQUIRED].copy()
    return df

# -------------------- Règles & helpers calcul --------------------

BONUS_TIERS = [
    # (seuil_diamants, bonus_diamants, code)
    (500_000, 3000, "B3"),
    (150_000, 1088, "B2"),
    (75_000, 500, "B1"),
]

def _already_hit_threshold(history: Optional[pd.DataFrame], username: str, threshold: int) -> bool:
    """Vrai si, dans l'historique, ce créateur a déjà atteint >= threshold diamants un mois."""
    if history is None or history.empty:
        return False
    h = history
    h = h[h["Nom d’utilisateur"].astype(str) == str(username)]
    if h.empty:
        return False
    return bool((h["Diamants"] >= threshold).any())

def _is_confirmed(history: Optional[pd.DataFrame], username: str) -> bool:
    """Confirmé s'il a déjà fait >= 150k un mois dans l'historique."""
    return _already_hit_threshold(history, username, 150_000)

def _within_90_days(relation_date: Optional[pd.Timestamp], period: Optional[pd.Timestamp]) -> bool:
    """Vrai si la fin de période est dans les 90 jours suivant la relation_date."""
    if pd.isna(relation_date) or pd.isna(period):
        return False
    end_month = pd.Timestamp(year=period.year, month=period.month, day=1) + pd.offsets.MonthEnd(0)
    return (end_month - relation_date) <= pd.Timedelta(days=90)

def _activity_ok(diamonds: float,
                 live_days: float,
                 live_hours: float,
                 confirmed: bool) -> Tuple[bool, str, str]:
    """
    Renvoie (actif, raison, palier_activite)
      - palier_activite in {"1er", "1er confirmé", "2nd requis"} selon le cas atteint
    Règles:
      Débutant: >= 7 jours & >= 15 h
      Confirmé: >= 12 jours & >= 25 h
      Si diamants >= 150k => il faut en plus >= 20 jours & >= 80 h (second palier)
    """
    lack = []
    if confirmed:
        base_days, base_hours = 12, 25
        tag = "1er confirmé"
    else:
        base_days, base_hours = 7, 15
        tag = "1er"

    if live_days < base_days:
        lack.append(f"jours<{base_days}")
    if live_hours < base_hours:
        lack.append(f"heures<{base_hours}")

    # second palier conditionné aux récompenses >=150k
    if diamonds >= 150_000:
        if not (live_days >= 20 and live_hours >= 80):
            # plus précis sur ce qui manque
            missing = []
            if live_days < 20:
                missing.append("jours<20")
            if live_hours < 80:
                missing.append("heures<80")
            lack.append("2nd palier (" + ", ".join(missing) + ")")
        else:
            tag = "2nd"

    actif = len(lack) == 0
    reason = "" if actif else "; ".join(lack)
    return actif, reason, tag

def _beginner_bonus(diamonds: float,
                    is_beginner: bool,
                    in_90_days: bool,
                    history: Optional[pd.DataFrame],
                    username: str) -> Tuple[int, str]:
    """
    Calcule le BONUS débutant (diamants) pour le mois courant.
    - Un seul bonus : le PLUS HAUT atteint ce mois.
    - Seulement si débutant ET dans les 90 jours depuis la date de relation.
    - Jamais déjà obtenu (on considère 'déjà obtenu' si l'historique montre qu'il a déjà atteint ce seuil de diamants).
    Retourne (montant_bonus, code)
    """
    if not (is_beginner and in_90_days):
        return 0, ""

    for thr, bonus, code in BONUS_TIERS:  # trié du plus haut au plus bas
        if diamonds >= thr:
            if not _already_hit_threshold(history, username, thr):
                return int(bonus), code
            else:
                # seuil déjà atteint dans le passé -> bonus déjà consommé
                return 0, ""
    return 0, ""

# -------------------- Calculs principaux --------------------

def compute_creators_table(df_current: pd.DataFrame,
                           df_history: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Retourne le tableau créateurs avec statut, activité, palier et bonus débutant.
    On suppose df_current / df_history déjà normalisés avec normalize_source().
    """
    cur = normalize_source(df_current)
    hist = normalize_source(df_history) if df_history is not None else None

    rows = []
    for _, r in cur.iterrows():
        user = str(r["Nom d’utilisateur"])
        grp = r["Groupe"]
        agt = r["Agent"]
        period = r["Période des données"]
        relation = r["Date d’établissement de la relation"]
        d = float(r["Diamants"])
        h = float(r["Durée de LIVE (heures)"])
        j = float(r["Jours de passage en LIVE valides"])

        confirmed = _is_confirmed(hist, user)
        is_beginner = not confirmed
        actif, reason, palier_act = _activity_ok(d, j, h, confirmed)
        b_ok, b_code = _beginner_bonus(d, is_beginner, _within_90_days(relation, period), hist, user)

        # état d’affichage des paliers (palier 2 affiché seulement si validé ; sinon palier 1)
        palier_affiche = ""
        if d >= 150_000 and palier_act == "2nd":
            palier_affiche = "Palier 2"
        elif d >= 1:  # a minima palier 1 si actif au bon niveau jours/heures
            palier_affiche = "Palier 1"

        rows.append({
            "Période": period.date() if pd.notna(period) else "",
            "Nom d’utilisateur": user,
            "Groupe/Manager": grp,
            "Agent": agt,
            "Diamants": int(d),
            "Jours actifs": int(j),
            "Heures de live": int(h),
            "Type de créateur": "Confirmé" if confirmed else "Débutant",
            "Palier d’activité": palier_act,
            "Actif": "✅" if actif else "⚠️",
            "Raison d’inéligibilité": reason,
            "Palier affiché": palier_affiche,
            "Bonus débutant (diamants)": int(b_ok),
            "Code bonus": b_code,
        })

    out = pd.DataFrame(rows)

    # ordre de colonnes
    want_cols = [
        "Période", "Nom d’utilisateur", "Groupe/Manager", "Agent",
        "Diamants", "Jours actifs", "Heures de live",
        "Type de créateur", "Palier d’activité", "Actif", "Raison d’inéligibilité",
        "Palier affiché", "Bonus débutant (diamants)", "Code bonus",
    ]
    out = out[want_cols]
    return out

def _agent_manager_bonus_row(d: int, palier_act: str, target: str) -> int:
    """
    Bonus Agent/Manager selon palier atteint (UN SEUL, le plus haut):
      - si palier 3 (diamants >= 500k) -> Agent:15000 / Manager:5000
      - sinon si palier 2 (diamants >= 150k ET palier activité = '2nd') -> Agent:1000 / Manager:1000
      - sinon 0
    """
    if d >= 500_000 and palier_act == "2nd":
        return 15000 if target == "agent" else 5000
    if d >= 150_000 and palier_act == "2nd":
        return 1000
    return 0

def compute_agents_table(creators_df: pd.DataFrame) -> pd.DataFrame:
    """Agrège les bonus Agents (un seul bonus par créateur, le plus haut)."""
    if creators_df is None or creators_df.empty:
        return pd.DataFrame(columns=["Agent", "Créateurs suivis", "Bonus total (diamants)"])

    tmp = creators_df.copy()
    tmp["bonus_agent"] = tmp.apply(
        lambda r: _agent_manager_bonus_row(int(r["Diamants"]), r["Palier d’activité"], "agent"),
        axis=1,
    )
    agg = tmp.groupby("Agent", dropna=False).agg(
        **{
            "Créateurs suivis": ("Nom d’utilisateur", "nunique"),
            "Bonus total (diamants)": ("bonus_agent", "sum"),
        }
    ).reset_index()
    return agg.sort_values("Bonus total (diamants)", ascending=False)

def compute_managers_table(creators_df: pd.DataFrame) -> pd.DataFrame:
    """Agrège les bonus Managers (un seul bonus par créateur, le plus haut)."""
    if creators_df is None or creators_df.empty:
        return pd.DataFrame(columns=["Groupe/Manager", "Créateurs actifs", "Bonus total (diamants)"])

    tmp = creators_df.copy()
    tmp["bonus_mgr"] = tmp.apply(
        lambda r: _agent_manager_bonus_row(int(r["Diamants"]), r["Palier d’activité"], "manager"),
        axis=1,
    )
    agg = tmp.groupby("Groupe/Manager", dropna=False).agg(
        **{
            "Créateurs actifs": ("Nom d’utilisateur", "nunique"),
            "Bonus total (diamants)": ("bonus_mgr", "sum"),
        }
    ).reset_index()
    return agg.sort_values("Bonus total (diamants)", ascending=False)
