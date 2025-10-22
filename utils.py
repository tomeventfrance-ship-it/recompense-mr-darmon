# utils.py — calculs
import io, re, math
import pandas as pd
import numpy as np

# ---------- lecture fichiers ----------
def load_df(file_obj):
    name = getattr(file_obj, "name", "uploaded")
    if isinstance(file_obj, (bytes, bytearray)):
        bio = io.BytesIO(file_obj)
        return pd.read_excel(bio) if name.lower().endswith((".xlsx", ".xls")) else pd.read_csv(bio)
    # Streamlit UploadedFile
    if name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(file_obj)
    return pd.read_csv(file_obj)

# ---------- mapping des colonnes nécessaires ----------
CANON = {
    "period":        "Période des données",
    "username":      "Nom d’utilisateur du/de la créateur(trice)",
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
    "period":        ["période", "periode des donnees", "période des données"],
    "username":      ["nom d'utilisateur", "username"],
    "group":         ["groupe/manager", "manager", "groupe"],
    "agent":         ["agent(e)", "agent "],
    "relation_date": ["date d'etablissement de la relation", "relation"],
    "diamonds":      ["diamants reçus", "nombre de diamants", "diamants"],
    "live_hours":    ["durée de live", "duree de live (heures)","duree de live"],
    "live_days":     ["jours live", "jours de passage en live", "jours de passage en live valides"],
    "al_status":     ["al", "statut du diplome", "debutant non diplome 90j", "statut du diplôme"],
}

def _best_match(col, target):
    c = col.strip().lower()
    if c == target: return True
    return any(c == a for a in ALIASES.get(target, []))

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c: c for c in df.columns}
    new = {}
    for key, wanted in CANON.items():
        # exact
        if wanted in df.columns:
            new[CANON[key]] = wanted
            continue
        # alias
        found = None
        for c in df.columns:
            if _best_match(c, key):
                found = c
                break
        if found:
            new[CANON[key]] = found
    # garder uniquement les colonnes utiles
    keep = {dst: src for dst, src in new.items()}
    df2 = df.rename(columns=keep)[list(keep.keys())].copy()

    # types doux
    num = ["Diamants", "Durée de LIVE (heures)", "Jours de passage en LIVE valides"]
    for n in num:
        if n in df2.columns:
            df2[n] = pd.to_numeric(df2[n], errors="coerce").fillna(0)

    for s in ["Période des données","Nom d’utilisateur du/de la créateur(trice)","Groupe","Agent","Statut du diplôme"]:
        if s in df2.columns:
            df2[s] = df2[s].astype(str).fillna("")

    if "Date d’établissement de la relation" in df2.columns:
        df2["Date d’établissement de la relation"] = pd.to_datetime(df2["Date d’établissement de la relation"], errors="coerce")

    return df2

# ---------- logique Créateurs ----------
def compute_creators_table(df_current: pd.DataFrame, df_history: pd.DataFrame | None = None) -> pd.DataFrame:
    cur = _normalize(df_current)

    # Historique uniquement pour flags bonus + confirmation 150k si fourni
    hist = None
    if df_history is not None and len(df_history):
        hist = _normalize(df_history)

    # Règles bonus débutant — SEULS seuils diamants (tu as confirmé que ce sont bien des diamants)
    # Bonus 1/2/3 : 75k / 150k / 500k (exclusifs : on garde le plus haut)
    d = cur["Diamants"]
    b1 = d >= 75_000
    b2 = d >= 150_000
    b3 = d >= 500_000

    # exclusivité : on garde uniquement le plus haut atteint
    bonus1 = b1 & ~b2 & ~b3
    bonus2 = b2 & ~b3
    bonus3 = b3

    # montant bonus créateur
    bonus_amount = np.select(
        [bonus1, bonus2, bonus3],
        [500, 1088, 3000],
        default=0
    )

    # colonnes de sortie créateurs (uniquement calculs créateurs)
    out = cur.copy()
    out["Bonus 1 éligible"] = bonus1
    out["Bonus 2 éligible"] = bonus2
    out["Bonus 3 éligible"] = bonus3
    out["Montant bonus créateur"] = bonus_amount

    # Paliers (exclusifs) si tu en as besoin côté export créateur
    out["Palier atteint"] = np.select(
        [bonus3, bonus2, bonus1],
        ["Palier 3", "Palier 2", "Palier 1"],
        default="Aucun"
    )

    # Récompense totale (créateurs) = ici juste le bonus (si tu ajoutes d'autres primes d’activité, additionne ici)
    out["Récompense totale"] = bonus_amount

    return out

# ---------- logique Agents & Managers dérivées UNIQUEMENT du tableau créateurs ----------
def compute_agents_table_from_creators(creators_table: pd.DataFrame) -> pd.DataFrame:
    # règles : agent +1000 si créateur atteint bonus 2, +15000 si bonus 3 (exclusif)
    b2 = creators_table["Bonus 2 éligible"]
    b3 = creators_table["Bonus 3 éligible"]
    agent_bonus = np.select([b3, b2], [15_000, 1_000], default=0)

    df = creators_table[["Agent", "Nom d’utilisateur du/de la créateur(trice)", "Diamants"]].copy()
    df["Bonus agent (par créateur)"] = agent_bonus

    # agrégat par agent
    agg = df.groupby("Agent", dropna=False, as_index=False).agg(
        Créateurs=("Nom d’utilisateur du/de la créateur(trice)", "nunique"),
        Diamants_total=("Diamants", "sum"),
        Bonus_total=("Bonus agent (par créateur)", "sum"),
    )
    return agg.sort_values("Bonus_total", ascending=False)

def compute_managers_table_from_creators(creators_table: pd.DataFrame) -> pd.DataFrame:
    # règles : manager +1000 si bonus 2, +5000 si bonus 3 (exclusif)
    b2 = creators_table["Bonus 2 éligible"]
    b3 = creators_table["Bonus 3 éligible"]
    manager_bonus = np.select([b3, b2], [5_000, 1_000], default=0)

    df = creators_table[["Groupe", "Nom d’utilisateur du/de la créateur(trice)", "Diamants"]].copy()
    df["Bonus manager (par créateur)"] = manager_bonus

    agg = df.groupby("Groupe", dropna=False, as_index=False).agg(
        Créateurs=("Nom d’utilisateur du/de la créateur(trice)", "nunique"),
        Diamants_total=("Diamants", "sum"),
        Bonus_total=("Bonus manager (par créateur)", "sum"),
    )
    return agg.sort_values("Bonus_total", ascending=False)

# API compatible avec app.py existant (on redirige vers les fonctions ci-dessus)
def compute_agents_table(df_current: pd.DataFrame, df_history: pd.DataFrame | None = None, creators_table: pd.DataFrame | None = None) -> pd.DataFrame:
    if creators_table is None:
        creators_table = compute_creators_table(df_current, df_history)
    return compute_agents_table_from_creators(creators_table)

def compute_managers_table(df_current: pd.DataFrame, df_history: pd.DataFrame | None = None, creators_table: pd.DataFrame | None = None) -> pd.DataFrame:
    if creators_table is None:
        creators_table = compute_creators_table(df_current, df_history)
    return compute_managers_table_from_creators(creators_table)
