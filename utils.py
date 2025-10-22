import re
import pandas as pd
import numpy as np

# --- Colonnes attendues (et mapping tolérant) ---
CANON = {
    "period": "Période des données",
    "username": "Nom d'utilisateur",
    "group": "Groupe/Manager",
    "agent": "Agent",
    "relation_date": "Date d'établissement de la relation",
    "diamonds": "Diamants",
    "live_hours": "Durée de live (heures)",
    "live_days": "Jours de passage en live",
    "al_status": "AL statut diplôme",
}

# correspondances souples par mots-clés (on matche en minuscules sans accents)
FLEX_MAP = {
    "period":       ["période", "periode", "period"],
    "username":     ["nom d'utilisateur", "username", "user name", "creator", "créateur"],
    "group":        ["groupe", "manager", "groupe/manager"],
    "agent":        ["agent"],
    "relation_date":["date d'établissement", "etablissement", "relation"],
    "diamonds":     ["diamant", "diamonds"],
    "live_hours":   ["durée de live", "duree de live", "heures de live", "live (heures)"],
    "live_days":    ["jours de passage", "jours de live", "passage en live", "jours valides"],
    "al_status":    ["statut du diplôme", "al", "diplome", "débutant"],
}

REQUIRED_KEYS = ["period","username","group","agent","relation_date","diamonds","live_hours","live_days","al_status"]


# ---------- Utils de lecture ----------
def _normalize(s: str) -> str:
    s = str(s).lower()
    s = re.sub(r"[àâä]", "a", s)
    s = re.sub(r"[éèêë]", "e", s)
    s = re.sub(r"[îï]", "i", s)
    s = re.sub(r"[ôö]", "o", s)
    s = re.sub(r"[ùûü]", "u", s)
    return s

def load_df(file_like, filename: str) -> pd.DataFrame:
    if filename.lower().endswith(".csv"):
        return pd.read_csv(file_like)
    return pd.read_excel(file_like)

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = list(df.columns)
    norm = {_normalize(c): c for c in cols}

    picked = {}
    for key, patterns in FLEX_MAP.items():
        found = None
        for p in patterns:
            # cherche une colonne contenant le mot clé
            for nn, orig in norm.items():
                if p in nn:
                    found = orig
                    break
            if found:
                break
        if found:
            picked[key] = found

    # Vérifie manquants
    missing = [k for k in REQUIRED_KEYS if k not in picked]
    if missing:
        raise ValueError(f"Colonnes manquantes dans le fichier importé : {missing}")

    # Renomme en colonnes canoniques
    out = df.rename(columns={
        picked["period"]: CANON["period"],
        picked["username"]: CANON["username"],
        picked["group"]: CANON["group"],
        picked["agent"]: CANON["agent"],
        picked["relation_date"]: CANON["relation_date"],
        picked["diamonds"]: CANON["diamonds"],
        picked["live_hours"]: CANON["live_hours"],
        picked["live_days"]: CANON["live_days"],
        picked["al_status"]: CANON["al_status"],
    }).copy()

    # Types
    for c in [CANON["diamonds"], CANON["live_hours"], CANON["live_days"]]:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype(int)

    # trim strings
    for c in [CANON["period"], CANON["username"], CANON["group"], CANON["agent"], CANON["al_status"]]:
        out[c] = out[c].astype(str).str.strip()

    return out


# ---------- Règles métier Créateurs ----------
BONUS_CREATOR = {1: 500, 2: 1088, 3: 3000}      # bonus créateur
# Bonus Agents / Managers (non cumulés par créateur) :
BONUS_AGENT   = {2: 1000, 3: 15000}
BONUS_MANAGER = {2: 1000, 3: 5000}

def _palier_from_diamonds(d: int) -> int:
    if d >= 500_000: return 3
    if d >= 150_000: return 2
    if d >= 75_000:  return 1
    return 0

def _is_active(days: int) -> bool:
    # règle minimale : actif si au moins 1 jour de live valide
    return days >= 1

def _is_beginner(al_text: str) -> bool:
    # On considère débutant si l’info AL dit non diplômé / en cours (90j)
    t = _normalize(al_text)
    # adaptez au besoin selon vos libellés exacts
    return ("debut" in t or "debutant" in t or "non dipl" in t or "90" in t)

def compute_creators_table(src_df: pd.DataFrame) -> pd.DataFrame:
    """Construit la table Créateurs complète avec :
       - Actif/Non validé (selon jours de live)
       - Palier bonus (max) et Montant bonus créateur (non cumulés)
       - Colonnes sources utiles uniquement (celles convenues)
    """
    df = src_df.copy()

    # Actif
    df["Actif"] = np.where(df[CANON["live_days"]].apply(_is_active), "Validé", "Non validé")

    # Palier max
    df["Palier bonus (1/2/3)"] = df[CANON["diamonds"]].apply(_palier_from_diamonds).astype(int)

    # Eligibilité débutant (info AL)
    df["Débutant ?"] = df[CANON["al_status"]].apply(_is_beginner)

    # Montant bonus créateur (un seul, le plus haut du mois)
    df["Montant bonus"] = df["Palier bonus (1/2/3)"].map(BONUS_CREATOR).fillna(0).astype(int)

    # Garde uniquement les colonnes convenues + calculs
    out = df[[
        CANON["period"],
        CANON["username"],
        CANON["group"],
        CANON["agent"],
        CANON["relation_date"],
        CANON["diamonds"],
        CANON["live_hours"],
        CANON["live_days"],
        CANON["al_status"],
        "Actif",
        "Palier bonus (1/2/3)",
        "Débutant ?",
        "Montant bonus",
    ]].copy()

    # tri lisible
    out = out.sort_values([CANON["diamonds"]], ascending=False).reset_index(drop=True)
    return out


# ---------- Agrégations Agents / Managers ----------
def compute_agents_table_from_creators(crea_table: pd.DataFrame) -> pd.DataFrame:
    """Agrège par Agent : diamants actifs/totaux, pertes, commission et bonus agent.
       Bonus agent : +1000 si un créateur atteint palier 2 ce mois, +15000 si palier 3 (pas cumulés).
    """
    active_mask = crea_table["Actif"].eq("Validé")
    g = crea_table.groupby(CANON["agent"], dropna=False)

    actives = g.apply(lambda x: x.loc[active_mask.reindex(x.index, fill_value=False), CANON["diamonds"]].sum()) \
               .rename("Diamants actifs")
    totals  = g[CANON["diamonds"]].sum().rename("Diamants totaux")
    perte   = (totals - actives).astype(int)

    def _agent_comm(sum_active: int) -> int:
        if sum_active < 200_000:
            return 0
        if sum_active < 4_000_000:
            return round(sum_active * 0.02)
        return round(sum_active * 0.03)

    commission = actives.apply(_agent_comm).astype(int)

    def _agent_bonus_block(df: pd.DataFrame) -> int:
        tiers = df["Palier bonus (1/2/3)"].fillna(0).astype(int)
        return int((tiers == 2).sum() * BONUS_AGENT[2] + (tiers == 3).sum() * BONUS_AGENT[3])

    bonus_agent = g.apply(_agent_bonus_block).rename("Bonus agent").astype(int)

    out = pd.concat(
        [actives.astype(int), totals.astype(int), perte,
         commission.rename("Commission").astype(int),
         bonus_agent],
        axis=1
    ).fillna(0)

    out["Récompense totale agent"] = (out["Commission"] + out["Bonus agent"]).astype(int)
    out = out.reset_index().rename(columns={CANON["agent"]: "Agent"}) \
             .sort_values(["Diamants actifs", "Diamants totaux"], ascending=False) \
             .reset_index(drop=True)
    return out


def compute_managers_table_from_creators(crea_table: pd.DataFrame) -> pd.DataFrame:
    """Agrège par Manager/Groupe : diamants actifs/totaux, pertes, commission et bonus manager.
       Bonus manager : +1000 si palier 2, +5000 si palier 3 (pas cumulés).
    """
    active_mask = crea_table["Actif"].eq("Validé")
    g = crea_table.groupby(CANON["group"], dropna=False)

    actives = g.apply(lambda x: x.loc[active_mask.reindex(x.index, fill_value=False), CANON["diamonds"]].sum()) \
               .rename("Diamants actifs")
    totals  = g[CANON["diamonds"]].sum().rename("Diamants totaux")
    perte   = (totals - actives).astype(int)

    def _mgr_comm(sum_active: int) -> int:
        if sum_active < 200_000:
            return 0
        if sum_active < 4_000_000:
            return round(sum_active * 0.02)
        return round(sum_active * 0.03)

    commission = actives.apply(_mgr_comm).astype(int)

    def _mgr_bonus_block(df: pd.DataFrame) -> int:
        tiers = df["Palier bonus (1/2/3)"].fillna(0).astype(int)
        return int((tiers == 2).sum() * BONUS_MANAGER[2] + (tiers == 3).sum() * BONUS_MANAGER[3])

    bonus_mgr = g.apply(_mgr_bonus_block).rename("Bonus manager").astype(int)

    out = pd.concat(
        [actives.astype(int), totals.astype(int), perte,
         commission.rename("Commission").astype(int),
         bonus_mgr],
        axis=1
    ).fillna(0)

    out["Récompense totale manager"] = (out["Commission"] + out["Bonus manager"]).astype(int)
    out = out.reset_index().rename(columns={CANON["group"]: "Manager/Groupe"}) \
             .sort_values(["Diamants actifs", "Diamants totaux"], ascending=False) \
             .reset_index(drop=True)
    return out
