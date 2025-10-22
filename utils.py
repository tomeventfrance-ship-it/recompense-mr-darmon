import io
import re
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
import pandas as pd

# ----------------------- Référentiel colonnes (source) -----------------------

# Variants tolérés (casse/accents ignorés) -> clé canonique
ALIAS = {
    # A
    "periode des donnees": "period",
    "période des données": "period",
    # C
    "nom d'utilisateur du/de la créateur(trice)": "username",
    "nom d'utilisateur": "username",
    "createur": "username",
    "créateur": "username",
    # D
    "groupe": "group",
    "groupe/manager": "group",
    "manager": "group",
    # E
    "agent": "agent",
    # F
    "date d'etablissement de la relation": "relation_date",
    "date d’établissement de la relation": "relation_date",
    # H
    "diamants": "diamonds",
    # I
    "duree de live (heures)": "live_hours",
    "durée de live (heures)": "live_hours",
    "duree de live": "live_hours",
    "durée de live": "live_hours",
    "durée de live (h)": "live_hours",
    # J
    "jours de passage en live valides": "live_days",
    "jours de passage en live": "live_days",
    "jours de passage en live (valides)": "live_days",
    # AL
    "statut du diplome": "al_status",
    "statut du diplôme": "al_status",
    "al": "al_status",
}

# Colonnes canoniques attendues ensuite par le code
CANON = {
    "period": "Période",
    "username": "Nom d’utilisateur",
    "group": "Groupe",
    "agent": "Agent",
    "relation_date": "Date relation",
    "diamonds": "Diamants",
    "live_hours": "Durée live (h)",
    "live_days": "Jours live",
    "al_status": "AL",
}

NEEDED_CANON = list(CANON.keys())

# ----------------------- Paramètres de calcul -----------------------

# Seuils paliers créateurs (diamants du mois)
PALIER_SEUILS = {1: 75_000, 2: 150_000, 3: 500_000}

# Bonus créateurs (débutant) – en diamants – non cumulés (on prend le plus haut atteint)
BONUS_CREATOR = {1: 500, 2: 1088, 3: 3000}

# Bonus Agents / Managers (par créateur, non cumulés)
BONUS_AGENT   = {2: 1000, 3: 15_000}
BONUS_MANAGER = {2: 1000, 3: 5_000}

# Critères "Actif" pour le mois (adapter si besoin)
MIN_LIVE_DAYS  = 1
MIN_LIVE_HOURS = 0


# ----------------------- Utils internes -----------------------

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for col in df.columns:
        key = _slug(col)
        if key in ALIAS:
            mapping[col] = CANON[ALIAS[key]]
    df = df.rename(columns=mapping)
    return df


def _assert_required(df: pd.DataFrame):
    missing = [CANON[k] for k in NEEDED_CANON if CANON[k] not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes: {', '.join(missing)}")


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    # numériques
    for c in [CANON["diamonds"], CANON["live_hours"], CANON["live_days"]]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # textes
    for c in [CANON["username"], CANON["group"], CANON["agent"], CANON["al_status"]]:
        if c in df.columns:
            df[c] = df[c].astype(str).fillna("")

    # période / date relation (laisse tel quel si non parsable)
    if CANON["period"] in df.columns:
        df[CANON["period"]] = df[CANON["period"]].astype(str)

    if CANON["relation_date"] in df.columns:
        df[CANON["relation_date"]] = df[CANON["relation_date"]].astype(str)

    return df


def _is_debutant(al_text: str) -> bool:
    s = _slug(al_text)
    # interprétation souple : mention "debutant", et pas "diplome"
    return ("debutant" in s) and ("diplome" not in s)


# ----------------------- Lecture fichiers upload -----------------------

def load_df(uploaded_files: List[io.BytesIO]) -> pd.DataFrame:
    """Empile plusieurs .xlsx/.csv, ne garde QUE les colonnes utiles, normalise les noms."""
    frames = []
    for up in uploaded_files:
        name = getattr(up, "name", "file")
        name_l = name.lower()
        if name_l.endswith(".xlsx") or name_l.endswith(".xls"):
            df = pd.read_excel(up)
        elif name_l.endswith(".csv"):
            df = pd.read_csv(up)
        else:
            raise ValueError(f"Format non supporté pour {name}")

        df = _map_columns(df)

        # garde uniquement colonnes utiles si présentes
        keep = [v for v in CANON.values() if v in df.columns]
        df = df[keep].copy()

        frames.append(df)

    if not frames:
        raise ValueError("Aucun fichier lisible importé.")

    out = pd.concat(frames, ignore_index=True)
    _assert_required(out)
    out = _coerce_types(out)
    return out


# ----------------------- Calculs CREATOR -----------------------

def _palier_from_diamonds(d: float) -> int:
    if d >= PALIER_SEUILS[3]:
        return 3
    if d >= PALIER_SEUILS[2]:
        return 2
    if d >= PALIER_SEUILS[1]:
        return 1
    return 0


def debutant_bonus_series(diamants: pd.Series,
                          al_col: pd.Series,
                          already_used: Optional[pd.Series] = None) -> Tuple[pd.Series, pd.Series]:
    """
    Calcule le palier bonus créateur (0/1/2/3) si DEBUTANT, non cumulés, et renvoie:
    - palier (int)
    - montant (int)
    already_used: bool série (True si créateur a déjà consommé ses bonus par le passé)
    """
    is_debutant = al_col.fillna("").map(_is_debutant)

    paliers = diamants.fillna(0).map(_palier_from_diamonds)
    paliers = np.where(is_debutant, paliers, 0).astype(int)

    # si déjà consommé (historique), force à 0
    if already_used is not None:
        paliers = np.where(already_used.fillna(False), 0, paliers).astype(int)

    montant = np.select(
        [paliers == 3, paliers == 2, paliers == 1],
        [BONUS_CREATOR[3], BONUS_CREATOR[2], BONUS_CREATOR[1]],
        default=0
    ).astype(int)

    return pd.Series(paliers, index=diamants.index), pd.Series(montant, index=diamants.index)


def compute_creators_table(df_src: pd.DataFrame,
                           history_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    df_src: DataFrame normalisé (load_df)
    history_df: DataFrame optionnel avec colonnes ['username','ever_150k','bonus_used']
    """
    df = df_src.copy()

    # Actif simple (adapter si besoin)
    df["Actif"] = np.where(
        (df[CANON["live_days"]] >= MIN_LIVE_DAYS) & (df[CANON["live_hours"]] >= MIN_LIVE_HOURS),
        "Validé", "Non validé"
    )

    # info historique: déjà consommé bonus ?
    already_used_map = None
    if history_df is not None and not history_df.empty:
        # username unique
        used = history_df.drop_duplicates("username").set_index("username")["bonus_used"].astype(bool)
        already_used_map = df[CANON["username"]].map(used).fillna(False)
    else:
        already_used_map = pd.Series(False, index=df.index)

    palier_bonus, montant_bonus = debutant_bonus_series(
        df[CANON["diamonds"]],
        df[CANON["al_status"]],
        already_used=already_used_map
    )

    df["Palier bonus (1/2/3)"] = palier_bonus
    df["Montant bonus (débutant)"] = montant_bonus

    # Lorsque palier 2 ou 3 atteint, on n'affiche pas 1; et 3 cache 2 => déjà géré par "max" ci-dessus
    # (On affiche juste le palier max et son montant)

    # Récompense totale (ex: ici = Diamants actifs + bonus débutant) -> ajuster selon règle métier finale
    actifs_diam = np.where(df["Actif"].eq("Validé"), df[CANON["diamonds"]], 0)
    df["Récompense totale"] = (actifs_diam + df["Montant bonus (débutant)"]).astype(int)

    # tri & colonnes finales
    final_cols = [
        CANON["period"], CANON["username"], CANON["group"], CANON["agent"],
        CANON["relation_date"], CANON["diamonds"], CANON["live_hours"],
        CANON["live_days"], CANON["al_status"],
        "Actif", "Palier bonus (1/2/3)", "Montant bonus (débutant)", "Récompense totale"
    ]
    df = df[final_cols].sort_values(CANON["diamonds"], ascending=False).reset_index(drop=True)
    return df


# ----------------------- Calculs AGENTS / MANAGERS (non cumulés par créateur) -----------------------

def compute_agents_table_from_creators(crea_table: pd.DataFrame) -> pd.DataFrame:
    active_mask = crea_table["Actif"].eq("Validé")

    # palier max par créateur sur lignes actives
    per_creator = (
        crea_table.loc[active_mask, [CANON["agent"], CANON["username"], "Palier bonus (1/2/3)", CANON["diamonds"]]]
        .groupby([CANON["agent"], CANON["username"]], as_index=False)
        .agg({"Palier bonus (1/2/3)": "max", CANON["diamonds"]: "sum"})
        .rename(columns={CANON["diamonds"]: "Diamants actifs (créa)"})
    )

    # bonus par créateur (non cumulés, 3 > 2)
    per_creator["Bonus agent (créa)"] = np.select(
        [
            per_creator["Palier bonus (1/2/3)"].eq(3),
            per_creator["Palier bonus (1/2/3)"].eq(2),
        ],
        [BONUS_AGENT[3], BONUS_AGENT[2]],
        default=0
    )

    g_all   = crea_table.groupby(CANON["agent"], dropna=False)[CANON["diamonds"]].sum().rename("Diamants totaux")
    g_act   = per_creator.groupby(CANON["agent"], dropna=False)["Diamants actifs (créa)"].sum().rename("Diamants actifs")
    g_bon   = per_creator.groupby(CANON["agent"], dropna=False)["Bonus agent (créa)"].sum().rename("Bonus agent")

    def _agent_comm(x: int) -> int:
        if x < 200_000: return 0
        if x < 4_000_000: return round(x * 0.02)
        return round(x * 0.03)

    commission = g_act.apply(_agent_comm).rename("Commission").astype(int)

    out = pd.concat([g_act.astype(int), g_all.astype(int)], axis=1)
    out["Pertes"] = (out["Diamants totaux"] - out["Diamants actifs"]).astype(int)
    out = pd.concat([out, commission, g_bon.astype(int)], axis=1).fillna(0)
    out["Récompense totale agent"] = (out["Commission"] + out["Bonus agent"]).astype(int)

    out = out.reset_index().rename(columns={CANON["agent"]: "Agent"}) \
             .sort_values(["Diamants actifs", "Diamants totaux"], ascending=False) \
             .reset_index(drop=True)
    return out


def compute_managers_table_from_creators(crea_table: pd.DataFrame) -> pd.DataFrame:
    active_mask = crea_table["Actif"].eq("Validé")

    per_creator = (
        crea_table.loc[active_mask, [CANON["group"], CANON["username"], "Palier bonus (1/2/3)", CANON["diamonds"]]]
        .groupby([CANON["group"], CANON["username"]], as_index=False)
        .agg({"Palier bonus (1/2/3)": "max", CANON["diamonds"]: "sum"})
        .rename(columns={CANON["diamonds"]: "Diamants actifs (créa)"})
    )

    per_creator["Bonus manager (créa)"] = np.select(
        [
            per_creator["Palier bonus (1/2/3)"].eq(3),
            per_creator["Palier bonus (1/2/3)"].eq(2),
        ],
        [BONUS_MANAGER[3], BONUS_MANAGER[2]],
        default=0
    )

    g_all = crea_table.groupby(CANON["group"], dropna=False)[CANON["diamonds"]].sum().rename("Diamants totaux")
    g_act = per_creator.groupby(CANON["group"], dropna=False)["Diamants actifs (créa)"].sum().rename("Diamants actifs")
    g_bon = per_creator.groupby(CANON["group"], dropna=False)["Bonus manager (créa)"].sum().rename("Bonus manager")

    def _mgr_comm(x: int) -> int:
        if x < 200_000: return 0
        if x < 4_000_000: return round(x * 0.02)
        return round(x * 0.03)

    commission = g_act.apply(_mgr_comm).rename("Commission").astype(int)

    out = pd.concat([g_act.astype(int), g_all.astype(int)], axis=1)
    out["Pertes"] = (out["Diamants totaux"] - out["Diamants actifs"]).astype(int)
    out = pd.concat([out, commission, g_bon.astype(int)], axis=1).fillna(0)
    out["Récompense totale manager"] = (out["Commission"] + out["Bonus manager"]).astype(int)

    out = out.reset_index().rename(columns={CANON["group"]: "Manager/Groupe"}) \
             .sort_values(["Diamants actifs", "Diamants totaux"], ascending=False) \
             .reset_index(drop=True)
    return out
