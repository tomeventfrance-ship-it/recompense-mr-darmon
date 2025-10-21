# --- Historique 150k ------------------------------------
def extract_150k_users(df: pd.DataFrame) -> set:
    """Retourne l’ensemble des utilisateurs ayant déjà atteint >=150k diamants dans ce df."""
    roles = _colmap(df)
    c_diam = roles.get("diamonds")
    c_user = roles.get("user")
    if not c_diam or not c_user:
        return set()
    s = pd.to_numeric(df[c_diam], errors="coerce").fillna(0)
    return set(df.loc[s >= 150000, c_user].astype(str).str.strip())

def merge_history(*dfs: pd.DataFrame) -> set:
    """Union des utilisateurs >=150k sur plusieurs mois."""
    users = set()
    for d in dfs:
        users |= extract_150k_users(d)
    return users

import re
import pandas as pd
from typing import Dict, Optional

# ---------- helpers ----------

def _colmap(df: pd.DataFrame) -> Dict[str, str]:
    """
    Essaie d'identifier les colonnes par motifs (insensible à la casse/accents).
    Retourne un dict: rôle -> nom_de_colonne_df
    Rôles utilisés plus bas: user, diamonds, hours, days, agent, manager, beginner90, already150k
    """
    def norm(s: str) -> str:
        s = s.lower()
        s = s.replace("é","e").replace("è","e").replace("ê","e").replace("à","a").replace("â","a").replace("ù","u").replace("û","u").replace("ï","i").replace("î","i").replace("ô","o").replace("ç","c")
        s = re.sub(r"[^a-z0-9 ]+"," ", s)
        return s

    cols = {norm(c): c for c in df.columns}
    roles: Dict[str,str] = {}

    def pick(patterns, role):
        for p in patterns:
            for n, orig in cols.items():
                if re.search(p, n):
                    roles[role] = orig
                    return

    # user name / username
    pick([r"\bnom.*utilisateur\b", r"\busername\b", r"\buser\b", r"\bpseudo\b", r"\bnom\b"], "user")

    # diamonds
    pick([r"\bdiam", r"\btotal.*diam", r"\bmontant.*diam"], "diamonds")

    # hours (durée de live)
    pick([r"\bduree.*(heure|h)\b", r"\bheures?\b", r"\bduree\b"], "hours")

    # days (jours de passage en live)
    pick([r"\bjours?.*passage.*live\b", r"\bjours?.*actif", r"\bjours?\b"], "days")

    # agent (col. E)
    pick([r"\bagent\b", r"\bmail.*agent\b", r"\bemail.*agent\b"], "agent")

    # manager / group (col. D)
    pick([r"\bmanager\b", r"\bgroupe\b", r"\bgroup\b"], "manager")

    # beginner flag (AL: débutant non diplômé en 90 jours)
    pick([r"\bdebutant.*90\b", r"\bnon.*diplome.*90\b", r"\bdebutant\b"], "beginner90")

    # optional flag: already did 150k historically
    pick([r"\bdeja.*150 ?000\b", r"\bhistorique.*150 ?000\b", r"\bancien.*150 ?000\b"], "already150k")

    return roles

def _to_num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)

# Barèmes paliers
def _palier_amount(d: float, palier: int) -> float:
    tiers_p1 = [
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
    ]
    tiers_p2 = [
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
    ]
    if d >= 2_000_000:
        return round(d * 0.04)
    tiers = tiers_p2 if palier == 2 else tiers_p1
    for lo, hi, val in tiers:
        if lo <= d <= hi:
            return float(val)
    return 0.0

def _bonus_debutant(d: float) -> float:
    if 75000 <= d <= 149999:
        return 500.0
    if 150000 <= d <= 499999:
        return 1088.0
    if 500000 <= d <= 2_000_000:
        return 3000.0
    return 0.0

# ---------- main compute ----------

def compute_creators_table(df_source: pd.DataFrame) -> pd.DataFrame:
    df = df_source.copy()
    roles = _colmap(df)

    # Colonnes indispensables
    needed = ["diamonds", "hours", "days"]
    missing = [r for r in needed if r not in roles]
    if missing:
        raise ValueError("Colonnes manquantes : " + ", ".join(missing) + " (diamants / heures / jours)")

    c_diam = roles["diamonds"]
    c_hours = roles["hours"]
    c_days  = roles["days"]
    c_user  = roles.get("user")
    c_agent = roles.get("agent")
    c_mgr   = roles.get("manager")
    c_beg   = roles.get("beginner90")
    c_alr   = roles.get("already150k")

    # Normalisation numériques
    df[c_diam] = _to_num(df[c_diam])
    df[c_hours] = _to_num(df[c_hours])
    df[c_days]  = _to_num(df[c_days])

    # Flags
    beginner_90 = df[c_beg].astype(str).str.lower().isin(["1","true","vrai","oui","yes"]) if c_beg in df else pd.Series([False]*len(df), index=df.index)
    # "Déjà 150k" historique : si non fourni, on approxime par (diamants du mois >= 150k)
    deja_150k = (df[c_alr].astype(str).str.lower().isin(["1","true","vrai","oui","yes"]) if c_alr in df else (df[c_diam] >= 150000))

    # Règle d'activité (définitive si déjà150k ou non-débutant)
    # - jamais 150k ET débutant => 15h & 7j, sinon 25h & 12j
    cond_hours = (df[c_hours] >= 15) & (df[c_hours] >= 25).where(deja_150k | (~beginner_90), other=False)
    cond_days  = (df[c_days]  >= 7)  & (df[c_days]  >= 12).where(deja_150k | (~beginner_90), other=False)
    actif = cond_hours & cond_days

    # Palier 2 (second palier d’activité)
    palier2_ok = (df[c_hours] >= 80) & (df[c_days] >= 20)

    # Récompenses paliers
    df["Récompense palier 1"] = df[c_diam].apply(lambda d: _palier_amount(d, 1)) * actif.astype(int)
    df["Palier 2"] = palier2_ok.map({True: "Validé", False: "Non validé"})
    df["Récompense palier 2"] = df[c_diam].apply(lambda d: _palier_amount(d, 2)) * palier2_ok.astype(int)

    # Bonus débutant (uniquement si flag AL vrai) et si actif (au moins palier de base validé heures/jours)
    bonus_val = df[c_diam].apply(_bonus_debutant)
    bonus_ok = beginner_90 & actif & (bonus_val > 0)
    df["Bonus débutant"] = bonus_ok.map({True: "Validé", False: "Non validé"})

    # Récompense totale = (Palier2 si validé sinon Palier1) + bonus (si validé)
    base_reward = df["Récompense palier 2"].where(palier2_ok, df["Récompense palier 1"])
    df["Récompense totale"] = base_reward + bonus_val.where(bonus_ok, 0)

    # Statut actif lisible
    df["Créateur actif"] = actif.map({True: "Actif", False: "Inactif"})

    # Colonnes finales (dans l’esprit A,C,D,E,F,H,I,J,AL + sorties)
    out_cols = []
    if c_user:  out_cols.append((c_user, "Nom d’utilisateur"))
    if c_mgr:   out_cols.append((c_mgr, "Manager"))
    if c_agent: out_cols.append((c_agent, "Agent"))
    out_cols += [
        (c_diam, "Diamants"),
        (c_hours, "Durée de live (h)"),
        (c_days, "Jours de passage en live"),
    ]
    if c_beg:   out_cols.append((c_beg, "Débutant non diplômé 90j"))

    # Construire la table finale propre
    final = pd.DataFrame({ new: df[old] for (old,new) in out_cols })
    final["Créateur actif"]      = df["Créateur actif"]
    final["Récompense palier 1"] = df["Récompense palier 1"].round(0).astype(int)
    final["Palier 2"]            = df["Palier 2"]
    final["Récompense palier 2"] = df["Récompense palier 2"].round(0).astype(int)
    final["Bonus débutant"]      = df["Bonus débutant"]
    final["Récompense totale"]   = df["Récompense totale"].round(0).astype(int)

    # Tri décroissant sur diamants
    final = final.sort_values(by=["Diamants"], ascending=False, kind="stable").reset_index(drop=True)
    return final
