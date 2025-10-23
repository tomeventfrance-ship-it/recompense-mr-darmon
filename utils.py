# utils.py
import pandas as pd
import numpy as np
from datetime import datetime

# ============== CONFIG COLONNES (mapping strict + alias souple) ==============
CANON = {
    "period": "Période des données",                          # A
    "username": "Nom d’utilisateur du/de la créateur(trice)", # C
    "group": "Groupe",                                        # D
    "agent": "Agent",                                         # E
    "relation_date": "Date d’établissement de la relation",   # F
    "diamonds": "Diamants",                                   # H
    "live_hours": "Durée de LIVE",                            # I
    "live_days": "Jours de passage en LIVE valides",          # J
    "al_status": "Statut du diplôme",                         # AL
}

ALIASES = {
    "Période des données": [
        "période des données","periode des donnees","période","periode","période données","période data"
    ],
    "Nom d’utilisateur du/de la créateur(trice)": [
        "nom d’utilisateur","nom utilisateur","username","créateur","createur",
        "nom du createur","nom du créateur","nom d'utilisateur du/de la créateur(trice)"
    ],
    "Groupe": ["groupe/manager","groupe manager","manager","groupe"],
    "Agent": ["agent(e)","nom de l’agent","nom agent","agent"],
    "Date d’établissement de la relation": [
        "date etablissement de la relation","date relation","relation date",
        "date d’etablissement de la relation","date d'établissement de la relation"
    ],
    "Diamants": ["diamant","total diamants","total_diamonds","diamonds"],
    "Durée de LIVE": [
        "durée de live","duree de live","heures de live","duree_live","live hours",
        "durée de live (heures)","durée live","durée"
    ],
    "Jours de passage en LIVE valides": [
        "jours de passage en live","jours live","nb jours live","live_days","jours actifs"
    ],
    "Statut du diplôme": ["statut diplôme","diplome","al","niveau","status diplôme"],
}
NUMERIC_COLS = {"Diamants","Durée de LIVE","Jours de passage en LIVE valides"}

# ======================= NORMALISATION DES COLONNES ==========================
def _match_target(col, target):
    if str(col).strip().casefold() == target.strip().casefold():
        return True
    for alias in ALIASES.get(target, []):
        if str(col).strip().casefold() == alias.strip().casefold():
            return True
    return False

def normalize_source(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    # rename souple -> noms finaux FR
    new_cols = {}
    for col in df.columns:
        matched = None
        for wanted in CANON.values():
            if _match_target(col, wanted):
                matched = wanted; break
        new_cols[col] = matched if matched else col
    df = df.rename(columns=new_cols)

    # ne garder QUE A,C,D,E,F,H,I,J,AL
    keep = list(CANON.values())
    present = [c for c in keep if c in df.columns]
    df = df[present].copy()

    # types
    if "Période des données" in df.columns:
        df["Période des données"] = df["Période des données"].astype(str)

    if "Date d’établissement de la relation" in df.columns:
        df["Date d’établissement de la relation"] = pd.to_datetime(
            df["Date d’établissement de la relation"], errors="coerce"
        )

    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = (
                df[c].astype(str)
                .str.replace("\u00a0","",regex=False)
                .str.replace(" ","",regex=False)
                .str.replace(",",".",regex=False)
            )
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    if "Nom d’utilisateur du/de la créateur(trice)" in df.columns:
        df["Nom d’utilisateur du/de la créateur(trice)"] = (
            df["Nom d’utilisateur du/de la créateur(trice)"].astype(str).str.strip()
        )
    return df

def ensure_df(obj) -> pd.DataFrame:
    if obj is None: return pd.DataFrame()
    if isinstance(obj, tuple): obj = obj[0]
    if isinstance(obj, pd.DataFrame): return obj
    try: return pd.DataFrame(obj)
    except: return pd.DataFrame()

# ====================== REGLES D’ACTIVITE & BONUS ============================
THRESH_BEGINNER = (7, 15)     # jours, heures
THRESH_CONFIRMED = (12, 25)
THRESH_SECOND = (20, 80)      # requis si ≥150k

BONUS_RULES = [
    (500_000, 3000, "B3_500k"),
    (150_000, 1088, "B2_150k"),
    (75_000,   500, "B1_75k"),
]

def _is_confirmed(username: str, df_hist: pd.DataFrame, cur_diamonds: float) -> bool:
    if df_hist is not None and not df_hist.empty:
        h = df_hist
        if "Nom d’utilisateur du/de la créateur(trice)" in h.columns and "Diamants" in h.columns:
            mask = h["Nom d’utilisateur du/de la créateur(trice)"].astype(str).str.strip() == username.strip()
            if mask.any():
                if h.loc[mask, "Diamants"].max(skipna=True) >= 150_000:
                    return True
    return cur_diamonds >= 150_000

def _active_flags(is_conf: bool, days: float, hours: float, diamonds: float):
    if is_conf:
        j, h = THRESH_CONFIRMED; pal = "1er confirmé"
    else:
        j, h = THRESH_BEGINNER;  pal = "1er"
    actif = (days >= j) and (hours >= h)
    second_ok = (days >= THRESH_SECOND[0]) and (hours >= THRESH_SECOND[1]) and (diamonds >= 150_000)
    return pal, actif, second_ok

def _beginner_bonus(username, diamonds, relation_date, is_conf, df_hist):
    if is_conf: return 0, ""
    if pd.isna(relation_date): return 0, ""
    days_since = (pd.Timestamp.utcnow().normalize() - relation_date.normalize()).days
    if days_since > 90: return 0, ""
    for thr, amount, code in BONUS_RULES:
        if diamonds >= thr:
            return amount, code
    return 0, ""

# ============================ TABLES CALCULEES ===============================
def _base_check(df: pd.DataFrame) -> pd.DataFrame:
    req = [
        "Période des données",
        "Nom d’utilisateur du/de la créateur(trice)",
        "Groupe",
        "Agent",
        "Date d’établissement de la relation",
        "Diamants",
        "Durée de LIVE",
        "Jours de passage en LIVE valides",
        "Statut du diplôme",
    ]
    missing = [c for c in req if c not in df.columns]
    if missing:
        raise ValueError("Colonnes manquantes : " + ", ".join(missing))
    return df.copy()

def compute_creators_table(df_current: pd.DataFrame, df_history: pd.DataFrame | None = None) -> pd.DataFrame:
    df = _base_check(df_current)
    df = df.sort_values(["Période des données","Nom d’utilisateur du/de la créateur(trice)"], na_position="last")

    rows = []
    for _, r in df.iterrows():
        user = str(r["Nom d’utilisateur du/de la créateur(trice)"]).strip()
        diamonds = float(r["Diamants"])
        days = float(r["Jours de passage en LIVE valides"])
        hours = float(r["Durée de LIVE"])

        is_conf = _is_confirmed(user, df_history, diamonds)
        pal_act, actif, second_ok = _active_flags(is_conf, days, hours, diamonds)

        if diamonds >= 150_000 and second_ok:
            palier_affiche = "Palier 2"
            recomp_p1 = 0
            recomp_p2 = diamonds
        else:
            palier_affiche = "Palier 1"
            recomp_p1 = diamonds if (actif and diamonds < 150_000) else 0
            recomp_p2 = 0

        bonus_amt, bonus_code = _beginner_bonus(
            user, diamonds, r["Date d’établissement de la relation"], is_conf, df_history
        )

        rows.append({
            "Période": r["Période des données"],
            "Nom d’utilisateur": user,
            "Groupe/Manager": r["Groupe"],
            "Agent": r["Agent"],
            "Date relation": r["Date d’établissement de la relation"],
            "Diamants": int(diamonds),
            "Jours actifs": int(days),
            "Heures de live": float(hours),
            "Type de créateur": "Confirmé" if is_conf else "Débutant",
            "Palier d’activité": pal_act,
            "Actif": "✅" if actif else "⚠️",
            "Palier affiché": palier_affiche,
            "Récompense palier 1": int(recomp_p1),
            "Récompense palier 2": int(recomp_p2),
            "Bonus débutant (diamants)": int(bonus_amt),
            "Code bonus": bonus_code,
        })
    out = pd.DataFrame(rows)
    order = [
        "Période","Nom d’utilisateur","Groupe/Manager","Agent","Date relation",
        "Diamants","Jours actifs","Heures de live",
        "Type de créateur","Palier d’activité","Actif",
        "Palier affiché","Récompense palier 1","Récompense palier 2",
        "Bonus débutant (diamants)","Code bonus",
    ]
    return out[order]

def compute_agents_table(df_current: pd.DataFrame, df_history: pd.DataFrame | None = None) -> pd.DataFrame:
    crea = compute_creators_table(df_current, df_history)
    if crea.empty: return pd.DataFrame()
    bonus_agent = np.where(crea["Diamants"] >= 500_000, 15000,
                      np.where(crea["Diamants"] >= 150_000, 1000, 0))
    tmp = crea.copy()
    tmp["Bonus agent (diamants)"] = bonus_agent.astype(int)
    agg = tmp.groupby(["Agent"], dropna=False, as_index=False).agg(
        Créateurs_actifs=("Actif", lambda s: int((s=="✅").sum())),
        Total_diamants=("Diamants","sum"),
        Total_récompense_p1=("Récompense palier 1","sum"),
        Total_récompense_p2=("Récompense palier 2","sum"),
        Total_bonus_agent=("Bonus agent (diamants)","sum"),
    )
    return agg.sort_values("Total_diamants", ascending=False, na_position="last")

def compute_managers_table(df_current: pd.DataFrame, df_history: pd.DataFrame | None = None) -> pd.DataFrame:
    crea = compute_creators_table(df_current, df_history)
    if crea.empty: return pd.DataFrame()
    bonus_mgr = np.where(crea["Diamants"] >= 500_000, 5000,
                    np.where(crea["Diamants"] >= 150_000, 1000, 0))
    tmp = crea.copy()
    tmp["Bonus manager (diamants)"] = bonus_mgr.astype(int)
    agg = tmp.groupby(["Groupe/Manager"], dropna=False, as_index=False).agg(
        Créateurs_actifs=("Actif", lambda s: int((s=="✅").sum())),
        Total_diamants=("Diamants","sum"),
        Total_récompense_p1=("Récompense palier 1","sum"),
        Total_récompense_p2=("Récompense palier 2","sum"),
        Total_bonus_manager=("Bonus manager (diamants)","sum"),
    )
    return agg.sort_values("Total_diamants", ascending=False, na_position="last")
