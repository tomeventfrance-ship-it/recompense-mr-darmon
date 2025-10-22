import pandas as pd
import numpy as np

# --- PARAMÈTRES GLOBAUX ---

BONUS_CREATOR = {
    1: {"threshold": 75000, "bonus": 500},
    2: {"threshold": 150000, "bonus": 1088},
    3: {"threshold": 500000, "bonus": 3000},
}

BONUS_AGENT = {
    2: {"bonus": 1000},
    3: {"bonus": 15000},
}

BONUS_MANAGER = {
    2: {"bonus": 1000},
    3: {"bonus": 5000},
}

# --- CHARGEMENT SÉCURISÉ ---

def load_df(uploaded_file):
    """Lit proprement CSV ou Excel"""
    if uploaded_file.name.endswith(".csv"):
        try:
            return pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding="latin-1")
    else:
        return pd.read_excel(uploaded_file, engine="openpyxl")

# --- FILTRAGE DES COLONNES ---

def normalize_columns(df):
    mapping = {
        "Période des données": "periode",
        "Nom d'utilisateur du/de la créateur(trice)": "username",
        "Groupe": "groupe",
        "Agent": "agent",
        "Date d'établissement de la relation": "relation_date",
        "Diamants": "diamants",
        "Durée de LIVE": "heures_live",
        "Jours de passage en LIVE valides": "jours_live",
        "Statut du diplôme": "statut",
    }
    df = df.rename(columns=mapping)
    keep = list(mapping.values())
    return df[[c for c in df.columns if c in keep]]
# --- NETTOYAGE & TYPES ---

def _coerce_numeric(s):
    """Convertit en nombre en tolérant les '1 234', '1,234', NaN, etc."""
    if s is None:
        return 0
    return pd.to_numeric(
        pd.Series(s)
          .astype(str)
          .str.replace("\u202f", "", regex=False)  # espace fine insécable
          .str.replace(" ", "", regex=False)
          .str.replace(",", ".", regex=False),
        errors="coerce"
    ).fillna(0).astype(float)

def prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    """Garde uniquement les colonnes utiles et force les types."""
    df = normalize_columns(df).copy()

    # Colonnes obligatoires : si absentes, on les crée vides pour éviter les crashs
    for col, default in [
        ("periode", ""),
        ("username", ""),
        ("groupe", ""),
        ("agent", ""),
        ("relation_date", ""),
        ("diamants", 0),
        ("heures_live", 0),
        ("jours_live", 0),
        ("statut", ""),
    ]:
        if col not in df.columns:
            df[col] = default

    # Numériques
    df["diamants"]   = _coerce_numeric(df["diamants"])
    df["heures_live"]= _coerce_numeric(df["heures_live"])
    df["jours_live"] = _coerce_numeric(df["jours_live"]).astype(int)

    # Texte normalisé
    for col in ["username", "groupe", "agent", "statut"]:
        df[col] = df[col].astype(str).fillna("").str.strip()

    # Statut débutant (90j) => True/False
    df["is_debutant_90j"] = df["statut"].str.lower().str.contains("débutant") & \
                            df["statut"].str.contains("90", case=False)

    # Index stable pour jointures éventuelles
    if "username" in df.columns:
        df["user_key"] = df["username"].str.lower().str.strip()
    else:
        df["user_key"] = ""

    return df

# --- PALIERS & BONUS ---

def palier_from_diamonds(d):
    if d >= BONUS_CREATOR[3]["threshold"]:
        return 3
    if d >= BONUS_CREATOR[2]["threshold"]:
        return 2
    if d >= BONUS_CREATOR[1]["threshold"]:
        return 1
    return 0

def highest_creator_bonus(d):
    """Retourne (palier, montant_bonus) non cumulable (uniquement le plus haut atteint)."""
    p = palier_from_diamonds(d)
    if p == 0:
        return 0, 0
    return p, BONUS_CREATOR[p]["bonus"]

def agent_manager_bonus(palier):
    """
    Renvoie (bonus_agent, bonus_manager) en appliquant la règle non-cumulable :
    - Agent  : palier 2 -> 1000 ; palier 3 -> 15000 ; sinon 0
    - Manager: palier 2 -> 1000 ; palier 3 -> 5000 ; sinon 0
    """
    bonus_agent = BONUS_AGENT.get(palier, {}).get("bonus", 0)
    bonus_manager = BONUS_MANAGER.get(palier, {}).get("bonus", 0)
    return bonus_agent, bonus_manager

# --- BONUS DÉBUTANT À VIE (UNE SEULE FOIS DANS LA FENÊTRE 90J) ---

def debutant_bonus_series(diamants_s: pd.Series,
                          al_s: pd.Series,
                          bonus_used=None):
    """
    Calcule l'éligibilité au bonus débutant pour chaque ligne.
    - al_s : série booléenne 'is_debutant_90j'
    - bonus_used : set de user_key déjà récompensés (optionnel, pour l'historique)
    Retourne (elig_bool_series, montant_bonus_series)
    Rappels montant : palier1=500, palier2=1088, palier3=3000 (non cumulable -> le plus haut)
    """
    if bonus_used is None:
        bonus_used = set()

    # Palier le plus haut atteint pour chaque ligne
    paliers = diamants_s.apply(palier_from_diamonds)
    bonus_amounts = paliers.map({0:0, 1:BONUS_CREATOR[1]["bonus"],
                                     2:BONUS_CREATOR[2]["bonus"],
                                     3:BONUS_CREATOR[3]["bonus"]})

    # éligible si débutant ET pas déjà utilisé dans l'historique
    elig = al_s & (~al_s.index.to_series().map(lambda i: False))  # base True pour les débutants

    # On ne retire ici aucun "déjà utilisé" faute d'historique user_key au niveau ligne.
    # Le filtrage « déjà utilisé » se fera dans compute_creators_table si history est fourni.

    return (elig & (paliers > 0)), bonus_amounts.where(paliers > 0, 0)
def compute_creators_table(data_or_list, history_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    data_or_list : DataFrame unique OU liste de DataFrames (mois courant + historiques).
    history_df   : historique externe optionnel, avec au minimum 'user_key' et 'bonus_debutant_utilise' (bool).
    """
    # 1) Fusionne si liste
    if isinstance(data_or_list, list):
        dfs = [prepare_df(d) for d in data_or_list if d is not None and len(d)]
        if not dfs:
            return pd.DataFrame()
        base = pd.concat(dfs, ignore_index=True)
    elif isinstance(data_or_list, pd.DataFrame):
        base = prepare_df(data_or_list)
    else:
        return pd.DataFrame()

    # 2) Historique des bonus déjà utilisés (optionnel)
    already_used = set()
    if history_df is not None and "user_key" in history_df.columns and "bonus_debutant_utilise" in history_df.columns:
        tmp = history_df.copy()
        tmp["user_key"] = tmp["user_key"].astype(str).str.lower().str.strip()
        already_used = set(tmp.loc[tmp["bonus_debutant_utilise"] == True, "user_key"].unique())

    # 3) Bonus débutant (éligibilité + montant), puis on invalide ceux déjà utilisés via l'historique
    elig_s, debut_bonus_amount_s = debutant_bonus_series(
        base["diamants"], base["is_debutant_90j"]
    )
    # Invalidation par historique
    if len(already_used) > 0:
        mask_used = base["user_key"].isin(already_used)
        elig_s = elig_s & (~mask_used)

    base["bonus_debutant_elig"]   = elig_s
    base["bonus_debutant_montant"] = debut_bonus_amount_s.where(base["bonus_debutant_elig"], 0)

    # 4) Palier atteints & bonus créateur (non cumulable)
    base["palier"] = base["diamants"].apply(palier_from_diamonds)
    base["bonus_createur_montant"] = base["palier"].map({
        0: 0,
        1: BONUS_CREATOR[1]["bonus"],
        2: BONUS_CREATOR[2]["bonus"],
        3: BONUS_CREATOR[3]["bonus"],
    })

    # 5) Bonus Agent / Manager (non cumulables et dépendants du palier)
    agent_bonus, manager_bonus = [], []
    for p in base["palier"].tolist():
        a, m = agent_manager_bonus(p)
        agent_bonus.append(a)
        manager_bonus.append(m)
    base["bonus_agent"] = agent_bonus
    base["bonus_manager"] = manager_bonus

    # 6) Colonnes d’affichage / libellés
    base["bonus_libelle"] = np.select(
        [
            base["palier"].eq(3),
            base["palier"].eq(2),
            base["palier"].eq(1),
        ],
        ["Bonus 3 (500k)", "Bonus 2 (150k)", "Bonus 1 (75k)"],
        default="Aucun"
    )

    # 7) Total créateur (palier non cumulable + bonus débutant si éligible)
    base["recompense_totale"] = base["bonus_createur_montant"] + base["bonus_debutant_montant"]

    # 8) Sélection et ordre final des colonnes (uniquement celles validées + résultats)
    final_cols = [
        "periode", "username", "groupe", "agent", "relation_date",
        "diamants", "heures_live", "jours_live", "statut",
        "palier", "bonus_libelle",
        "bonus_debutant_elig", "bonus_debutant_montant",
        "bonus_createur_montant",
        "bonus_agent", "bonus_manager",
        "recompense_totale",
    ]
    out = base[final_cols].copy()

    # 9) Tri (optionnel) : par diamants décroissant
    out = out.sort_values(["diamants", "username"], ascending=[False, True]).reset_index(drop=True)
    return out
