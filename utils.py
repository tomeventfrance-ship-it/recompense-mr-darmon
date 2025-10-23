import pandas as pd
import numpy as np
import re

# ---------------- Colonnes canoniques ----------------
CANON = {
    "period": "Période des données",
    "username": "Nom d’utilisateur du/de la créateur(trice)",
    "group": "Groupe",
    "agent": "Agent",
    "relation_date": "Date d’établissement de la relation",
    "diamonds": "Diamants",
    "live_hours": "Durée de LIVE",
    "live_days": "Jours de passage en LIVE valides",
    "al_status": "Statut du diplôme",
}

# Alias très tolérants (toutes variantes vues)
ALIASES = {
    "Période des données": [
        "période des données","periode des donnees","période","periode","mois","period","période données"
    ],
    "Nom d’utilisateur du/de la créateur(trice)": [
        "nom d’utilisateur","nom utilisateur","username","créateur","createur","nom du créateur",
        "nom du createur","nom du/de la créateur(trice)","nom d'utilisateur","user","creator"
    ],
    "Groupe": ["groupe/manager","groupe manager","manager","groupe","groupe / manager"],
    "Agent": ["agent(e)","nom de l’agent","nom agent","agent","agent / conseiller"],
    "Date d’établissement de la relation": [
        "date etablissement de la relation","date relation","relation date",
        "date d’etablissement de la relation","date d'établissement de la relation","date debut relation"
    ],
    "Diamants": ["diamant","total diamants","total_diamonds","diamonds","nb diamants","diamants (mois)"],
    "Durée de LIVE": [
        "durée de live","duree de live","heures de live","duree_live","live hours","durée de live (heures)",
        "durée live","duree (h)","temps de live","live duration","heures","live (h)"
    ],
    "Jours de passage en LIVE valides": [
        "jours de passage en live","jours live","nb jours live","live_days","jours actifs","jours"
    ],
    "Statut du diplôme": ["statut diplôme","diplome","al","niveau","status diplôme","al status"],
}

# ---------------- Parsing/normalisation ----------------
def _match_target(col, target):
    c = str(col).strip().casefold()
    if c == target.strip().casefold():
        return True
    for alias in ALIASES.get(target, []):
        if c == alias.strip().casefold():
            return True
    return False

def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for col in df.columns:
        chosen = None
        for wanted in CANON.values():
            if _match_target(col, wanted):
                chosen = wanted; break
        mapping[col] = chosen if chosen else col
    return df.rename(columns=mapping)

# Heures : accepte 123, 123.5, 123,5, "HH:MM", "HhMM", "H:MM:SS"
_HHMM = re.compile(r"^\s*(\d{1,3})\s*[:hH]\s*(\d{1,2})(?::(\d{1,2}))?\s*$")
def parse_live_hours(val) -> float:
    if pd.isna(val): return 0.0
    s = str(val).strip()
    if not s: return 0.0
    m = _HHMM.match(s)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2)) if m.group(2) else 0
        se = int(m.group(3)) if m.group(3) else 0
        return h + mi/60 + se/3600
    # nombres avec espaces/virgules
    s2 = s.replace("\u00a0","").replace(" ","")
    # si virgule décimale
    if s2.count(",")==1 and s2.count(".")==0:
        s2 = s2.replace(",",".")
    # si séparateur de milliers + décimal, tente conversion douce
    try:
        return float(s2)
    except:
        # Dernière chance : retirer tout sauf chiffres/., puis float
        s3 = re.sub(r"[^0-9\.]", "", s2)
        try:
            return float(s3) if s3 else 0.0
        except:
            return 0.0

def to_number(x) -> float:
    if pd.isna(x): return 0.0
    s = str(x).replace("\u00a0","").replace(" ","")
    # 1,234 -> 1.234 si pas déjà un décimal point
    if s.count(",")==1 and s.count(".")==0:
        s = s.replace(",",".")
    # retirer tout ce qui n’est pas chiffre/point
    s = re.sub(r"[^0-9\.]", "", s)
    try:
        return float(s) if s else 0.0
    except:
        return 0.0

def normalize_source(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    df = _rename_columns(df)

    keep = list(CANON.values())
    present = [c for c in keep if c in df.columns]
    df = df[present].copy()

    if "Période des données" in df.columns:
        df["Période des données"] = df["Période des données"].astype(str).str.strip()

    if "Date d’établissement de la relation" in df.columns:
        df["Date d’établissement de la relation"] = pd.to_datetime(
            df["Date d’établissement de la relation"], errors="coerce"
        )

    if "Diamants" in df.columns:
        df["Diamants"] = df["Diamants"].apply(to_number).fillna(0).astype(float)

    if "Jours de passage en LIVE valides" in df.columns:
        df["Jours de passage en LIVE valides"] = (
            df["Jours de passage en LIVE valides"].apply(to_number).fillna(0).astype(float)
        )

    if "Durée de LIVE" in df.columns:
        df["Durée de LIVE"] = df["Durée de LIVE"].apply(parse_live_hours).fillna(0).astype(float)

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

# ---------------- Règles d’activité & bonus ----------------
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
        ucol = "Nom d’utilisateur du/de la créateur(trice)"
        if ucol in h.columns and "Diamants" in h.columns:
            mask = h[ucol].astype(str).str.strip() == username.strip()
            if mask.any() and h.loc[mask, "Diamants"].max(skipna=True) >= 150_000:
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

def _beginner_bonus(diamonds, relation_date, is_conf):
    if is_conf: return 0, ""
    if pd.isna(relation_date): return 0, ""
    days_since = (pd.Timestamp.utcnow().normalize() - relation_date.normalize()).days
    if days_since > 90: return 0, ""
    for thr, amount, code in BONUS_RULES:
        if diamonds >= thr:
            return amount, code
    return 0, ""

# ---------------- Tables calculées ----------------
def _base_check(df: pd.DataFrame) -> pd.DataFrame:
    req = list(CANON.values())
    missing = [c for c in req if c not in df.columns]
    if missing:
        raise ValueError("Colonnes manquantes : " + ", ".join(missing))
    return df.copy()

def compute_creators_table(df_current: pd.DataFrame, df_history: pd.DataFrame | None = None) -> pd.DataFrame:
    df = _base_check(df_current).sort_values(
        ["Période des données","Nom d’utilisateur du/de la créateur(trice)"], na_position="last"
    )

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
            recomp_p2 = int(diamonds)
        else:
            palier_affiche = "Palier 1"
            recomp_p1 = int(diamonds) if (actif and diamonds < 150_000) else 0
            recomp_p2 = 0

        bonus_amt, bonus_code = _beginner_bonus(
            diamonds, r["Date d’établissement de la relation"], is_conf
        )

        rows.append({
            "Période": r["Période des données"],
            "Nom d’utilisateur": user,
            "Groupe/Manager": r["Groupe"],
            "Agent": r["Agent"],
            "Date relation": r["Date d’établissement de la relation"],
            "Diamants": int(diamonds),
            "Jours actifs": int(days),
            "Heures de live": round(hours,2),
            "Type de créateur": "Confirmé" if is_conf else "Débutant",
            "Palier d’activité": pal_act,
            "Actif": "✅" if actif else "⚠️",
            "Palier affiché": palier_affiche,
            "Récompense palier 1": recomp_p1,
            "Récompense palier 2": recomp_p2,
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
