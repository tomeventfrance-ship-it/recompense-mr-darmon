# utils.py
import pandas as pd
import numpy as np

# --------- Helpers ---------
ALIASES = {
    "Diamants": [
        "diamants", "diamant", "diamonds", "nb_diamants", "total diamonds",
        "Nombre de diamants", "Nombre de diamant"
    ],
    "Durée de live (heures)": [
        "durée de live (heures)", "heures de live", "heure de live", "duree de live",
        "temps en live (h)", "live_hours", "durée live"
    ],
    "Jours de passage en live": [
        "jours de passage en live", "jours actifs", "jours de live", "jours en live",
        "nb jours live", "live_days"
    ],
    "Agent": ["agent", "e", "colonne e", "agent (col.e)"],
    "Groupe/Manager": ["groupe", "manager", "colonne d", "groupe (manager)", "groupe/manager"],
    "Nom d’utilisateur": ["nom d’utilisateur", "username", "user", "nom d'utilisateur", "pseudo"],
    "AL": ["al", "débutant non diplômé 90j", "debutant_non_diplome_90j", "debutant"]
}

def _match_col(df: pd.DataFrame, target: str):
    """Trouve la colonne correspondant au 'target' via alias (insensible à la casse/accents approximatifs)."""
    cols_norm = {c: c.lower().strip() for c in df.columns}
    # essai exact
    for c in df.columns:
        if c.lower().strip() == target.lower().strip():
            return c
    # via alias
    for alias in ALIASES.get(target, []):
        for c, low in cols_norm.items():
            if low == alias.lower().strip():
                return c
    # via contains
    key = target.lower().split(" (")[0]
    for c, low in cols_norm.items():
        if key in low:
            return c
    return None

def _int_series(s):
    return pd.to_numeric(s, errors="coerce").fillna(0).astype(int)

# --------- Barèmes ---------
P1_TIERS = [
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
    (2000000,10**12, "PCT_4"),  # 4%
]

P2_TIERS = [
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
    (2000000,10**12, "PCT_4"),  # 4%
]

def _tier_amount(diamonds: int, tiers):
    for low, high, val in tiers:
        if low <= diamonds <= high:
            if val == "PCT_4":
                return int(round(diamonds * 0.04))
            return int(val)
    return 0

def _bonus_debutant(diamonds: int, is_debutant: bool):
    if not is_debutant:
        return 0
    if 75000 <= diamonds <= 149999:
        return 500
    if 150000 <= diamonds <= 499999:
        return 1088
    if 500000 <= diamonds <= 2000000:
        return 3000
    return 0

# --------- Règles principales ---------
def compute_creators_table(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()

    # Mapper les colonnes obligatoires
    col_diam = _match_col(df, "Diamants")
    col_hours = _match_col(df, "Durée de live (heures)")
    col_days = _match_col(df, "Jours de passage en live")
    col_agent = _match_col(df, "Agent")
    col_group = _match_col(df, "Groupe/Manager")
    col_user = _match_col(df, "Nom d’utilisateur")
    col_al = _match_col(df, "AL")

    missing = [name for name, col in [
        ("Diamants", col_diam),
        ("Durée de live (heures)", col_hours),
        ("Jours de passage en live", col_days),
        ("Agent", col_agent),
        ("Groupe/Manager", col_group),
    ] if col is None]

    if missing:
        raise ValueError(f"Colonnes manquantes : {', '.join(missing)}")

    # Convertir types
    df["Diamants"] = _int_series(df[col_diam])
    df["Durée de live (heures)"] = _int_series(df[col_hours])
    df["Jours de passage en live"] = _int_series(df[col_days])
    df["Agent"] = df[col_agent].astype(str).fillna("")
    df["Groupe/Manager"] = df[col_group].astype(str).fillna("")
    if col_user:
        df["Nom d’utilisateur"] = df[col_user].astype(str)
    else:
        df["Nom d’utilisateur"] = ""

    # Débutant ?
    is_debutant = False
    if col_al:
        al_series = df[col_al].astype(str).str.strip().str.lower()
        is_debutant = al_series.isin(["1", "true", "vrai", "oui", "yes", "y", "o", "débutant", "debutant"])
    df["Débutant 90j"] = is_debutant

    # A-t-il déjà fait 150k ? Si pas d'historique fourni, on approxime par diamants courants ≥ 150k
    deja_150k = df.get("Déjà_150k", None)
    if deja_150k is not None:
        df["Déjà_150k"] = df["Déjà_150k"].astype(str).str.lower().isin(
            ["1", "true", "vrai", "oui", "yes", "y"]
        )
    else:
        df["Déjà_150k"] = df["Diamants"] >= 150000

    # Seuils d’activité selon profil
    req_days = np.where((~df["Débutant 90j"]) | (df["Déjà_150k"]), 12, 7)
    req_hours = np.where((~df["Débutant 90j"]) | (df["Déjà_150k"]), 25, 15)

    # Statut actif
    df["Actif"] = np.where(
        (df["Diamants"] >= 750) &
        (df["Jours de passage en live"] >= req_days) &
        (df["Durée de live (heures)"] >= req_hours),
        "Actif", "Inactif"
    )

    # Validations paliers
    p1_ok = (
        (df["Jours de passage en live"] >= req_days) &
        (df["Durée de live (heures)"] >= req_hours) &
        (df["Diamants"] >= 35000)
    )
    p2_ok = (
        (df["Jours de passage en live"] >= 20) &
        (df["Durée de live (heures)"] >= 80) &
        (df["Diamants"] >= 35000)
    )

    df["Palier 2"] = np.where(p2_ok, "Validé", "Non validé")

    # Montants barèmes
    df["_P1_montant"] = df["Diamants"].apply(lambda d: _tier_amount(d, P1_TIERS))
    df["_P2_montant"] = df["Diamants"].apply(lambda d: _tier_amount(d, P2_TIERS))

    # Masquage : si P2 validé => P1 vide ; sinon si P1 validé => garder P1 et P2 vide
    df["Récompense palier 1"] = np.where((~p2_ok) & p1_ok, df["_P1_montant"], 0)
    df["Récompense palier 2"] = np.where(p2_ok, df["_P2_montant"], 0)

    # Bonus débutant (non cumulatif, une seule tranche)
    df["Bonus débutant"] = [
        _bonus_debutant(d, deb)
        for d, deb in zip(df["Diamants"], df["Débutant 90j"])
    ]

    # Récompense totale
    df["Récompense totale"] = (
        df["Récompense palier 1"].astype(int) +
        df["Récompense palier 2"].astype(int) +
        df["Bonus débutant"].astype(int)
    )

    # Format entier
    for c in ["Récompense palier 1", "Récompense palier 2", "Bonus débutant", "Récompense totale"]:
        df[c] = df[c].astype(int)

    # Ordonner & trier
    out_cols = [
        "Nom d’utilisateur",
        "Diamants",
        "Durée de live (heures)",
        "Jours de passage en live",
        "Agent",
        "Groupe/Manager",
        "Actif",
        "Palier 2",
        "Récompense palier 1",
        "Récompense palier 2",
        "Bonus débutant",
        "Récompense totale",
    ]
    df_out = df[out_cols].sort_values("Récompense totale", ascending=False).reset_index(drop=True)

    # Masquer la colonne du palier non utilisé (pour l’affichage)
    # Si P2 validé -> P1 = ""
    df_out.loc[df_out["Récompense palier 2"] > 0, "Récompense palier 1"] = ""
    # Si P2 NON validé -> P2 = ""
    df_out.loc[df_out["Récompense palier 2"] == 0, "Récompense palier 2"] = ""

    return df_out
