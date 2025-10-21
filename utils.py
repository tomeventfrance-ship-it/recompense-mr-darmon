import io
import re
import pandas as pd
import numpy as np

# --------- MAPPING STRICT : on ne lit que ce qui sert ------------
CANDIDATES = {
    "diamants": [
        "Diamants","Total diamants","Nombre de diamants","Diamonds"
    ],
    "heures": [
        "Durée de live (heures)","Durée de live","Heures de live",
        "Temps de live (h)","Durée (heures)","Durée du live (h)"
    ],
    "jours": [
        "Jours de passage en live","Jours de live","Nombre de jours de live",
        "Jours passes en live","Jours (live)"
    ],
    "agent": ["Agent","Agent (col.E)","Agent(e)"],
    "manager": ["Groupe/Manager","Manager","Groupe","Groupe (col.D)"],
    "user": ["Nom d’utilisateur","Nom d'utilisateur","Username","Utilisateur","Pseudo","Nom d’utilisateur (si dispo)"],
    "al": ["AL","Débutant non diplômé 90j","Debutant non diplome 90j","Debutant 90j"],
    # indicateur historique "a déjà fait 150k" (optionnel)
    "deja150": ["déjà 150k","deja 150k","a deja fait 150k","historique 150k"],
    # indicateur bonus déjà utilisé (optionnel)
    "bonus_used": ["bonus_deja_utilise","bonus déjà utilisé","bonus utilise","bonus_used"]
}

CANON = ["user","manager","agent","diamants","heures","jours","al","deja150","bonus_used"]

def _norm(s: str) -> str:
    s = s.lower()
    s = s.encode("ascii","ignore").decode()
    s = re.sub(r"[^a-z0-9 ]+"," ",s)
    s = re.sub(r"\s+"," ",s).strip()
    return s

def _pick(df: pd.DataFrame, keys) -> str|None:
    norm = {_norm(c): c for c in df.columns}
    # match exact normalisé
    for k in keys:
        n = _norm(k)
        if n in norm:
            return norm[n]
    # match partiel tolérant
    for k in keys:
        nk = _norm(k)
        for c in df.columns:
            if nk in _norm(c):
                return c
    return None

def load_df(file_like) -> pd.DataFrame:
    """Lit CSV/XLSX, ne garde QUE les colonnes utiles, les renomme de façon canonique."""
    name = getattr(file_like, "name", "")
    if isinstance(file_like, (bytes, bytearray)):
        bio = io.BytesIO(file_like); bio.name = name; file_like = bio

    if str(name).lower().endswith(".csv"):
        raw = pd.read_csv(file_like)
    else:
        raw = pd.read_excel(file_like)

    found = {}
    for canon, cand in CANDIDATES.items():
        col = _pick(raw, cand)
        if col is not None:
            found[canon] = col

    # 3 colonnes indispensables
    missing_core = [k for k in ["diamants","heures","jours"] if k not in found]
    if missing_core:
        pretty = {"diamants":"Diamants","heures":"Durée de live (heures)","jours":"Jours de passage en live"}
        raise ValueError("Colonnes manquantes: " + ", ".join(pretty[k] for k in missing_core))

    use_cols = [found[k] for k in CANON if k in found]
    df = raw.loc[:, use_cols].rename(columns={found[k]: k for k in found})

    # ajoute les optionnelles vides si absentes
    for opt in CANON:
        if opt not in df.columns:
            df[opt] = None

    # types
    for num in ["diamants","heures","jours"]:
        df[num] = pd.to_numeric(df[num], errors="coerce").fillna(0)

    # string tidy
    for s in ["user","agent","manager","al","deja150","bonus_used"]:
        df[s] = df[s].astype(str).replace({"nan":""}).str.strip()

    return df[CANON]


# ---------------------- RÈGLES METIER ---------------------------

def deja_150k_flag(row: pd.Series) -> bool:
    """Si la colonne historique n’existe pas/est vide => on considère 150k atteint si diamants courants >=150k."""
    txt = str(row.get("deja150","")).strip().lower()
    if txt in ["1","true","vrai","oui","yes","y"]:
        return True
    if txt in ["0","false","faux","non","no","n",""]:
        # fallback via diamants du fichier en cours
        return float(row["diamants"]) >= 150_000
    return float(row["diamants"]) >= 150_000

def beginner_bonus_used(row: pd.Series) -> bool:
    txt = str(row.get("bonus_used","")).strip().lower()
    return txt in ["1","true","vrai","oui","yes","y"]

def is_active(row: pd.Series) -> bool:
    """Validation activité selon statuts :
       - Jamais 150k : 15h & 7j
       - Déjà 150k (ou non-débutant) : 25h & 12j
       Seuil minimum diamants pour considérer “actif” global: 750 (défini par toi)."""
    if row["diamants"] < 750:
        return False
    if deja_150k_flag(row):
        return (row["heures"] >= 25) and (row["jours"] >= 12)
    else:
        return (row["heures"] >= 15) and (row["jours"] >= 7)

def palier2_valid(row: pd.Series) -> bool:
    """Second palier: 20 jours & 80 heures."""
    return (row["jours"] >= 20) and (row["heures"] >= 80)

# Tables Palier 1 & 2
P1 = [
    (35_000, 74_999, 1_000),
    (75_000, 149_000, 2_500),
    (150_000, 199_999, 5_000),
    (200_000, 299_999, 6_000),
    (300_000, 399_999, 7_999),
    (400_000, 499_999, 12_000),
    (500_000, 599_999, 15_000),
    (600_000, 699_999, 18_000),
    (700_000, 799_999, 21_000),
    (800_000, 899_999, 24_000),
    (900_000, 999_999, 26_999),
    (1_000_000, 1_499_999, 30_000),
    (1_500_000, 1_999_999, 44_999),
    ("GE2M", None, 0.04),  # 4% au-delà de 2M
]
P2 = [
    (35_000, 74_999, 1_000),
    (75_000, 149_000, 2_500),
    (150_000, 199_999, 6_000),
    (200_000, 299_999, 7_999),
    (300_000, 399_999, 12_000),
    (400_000, 499_999, 15_000),
    (500_000, 599_999, 20_000),
    (600_000, 699_999, 24_000),
    (700_000, 799_999, 26_999),
    (800_000, 899_999, 30_000),
    (900_000, 999_999, 35_000),
    (1_000_000, 1_499_999, 39_999),
    (1_500_000, 1_999_999, 59_999),
    ("GE2M", None, 0.04),
]

def reward_from_table(diamants: float, table) -> int:
    if diamants < 35_000:
        return 0
    for lo, hi, val in table:
        if lo == "GE2M":
            return int(round(diamants * 0.04))
        if lo <= diamants <= hi:
            return int(val)
    return 0

def debutant_bonus(row: pd.Series) -> tuple[str,int,str]:
    """Retourne (etat 'Validé/Non validé', montant, palier_bonus_str).
       Eligibilité : colonne AL indique 'débutant non diplômé 90j' (présence/texte), et bonus non encore utilisé."""
    al = str(row.get("al","")).strip().lower()
    elig = (al not in ["", "nan", "none", "0", "non", "false"])
    if not elig or beginner_bonus_used(row):
        return ("Non validé", 0, "")

    d = row["diamants"]
    if 75_000 <= d <= 149_999:
        return ("Validé", 500, "Bonus 1")
    if 150_000 <= d <= 499_999:
        return ("Validé", 1088, "Bonus 2")
    if 500_000 <= d <= 2_000_000:
        return ("Validé", 3000, "Bonus 3")
    return ("Non validé", 0, "")

# ---------------- Tables de synthèse ----------------

def compute_creators_table(df_in: pd.DataFrame) -> pd.DataFrame:
    df = df_in.copy()

    # Actif ? (règle en fonction de 150k)
    df["Actif"] = df.apply(is_active, axis=1).map({True:"Actif", False:"Inactif"})

    # Palier 2 ?
    df["Palier 2"] = df.apply(palier2_valid, axis=1).map({True:"Validé", False:"Non validé"})

    # Récompenses Palier 1 / 2 (montants)
    df["_r1"] = df["diamants"].apply(lambda x: reward_from_table(x, P1))
    df["_r2"] = df["diamants"].apply(lambda x: reward_from_table(x, P2))

    # N’afficher que l’un des deux :
    # - si Palier 2 validé => Palier 1 vide
    # - sinon => Palier 2 vide
    df["Récompense palier 1"] = np.where(df["Palier 2"]=="Validé", "", df["_r1"].astype("Int64"))
    df["Récompense palier 2"] = np.where(df["Palier 2"]=="Validé", df["_r2"].astype("Int64"), "")

    # Bonus débutant (une seule fois si bonus_used!=True)
    bonus = df.apply(debutant_bonus, axis=1)
    df["Bonus débutant"] = [b[0] for b in bonus]
    df["_bonus_montant"] = [b[1] for b in bonus]

    # Récompense totale = (palier choisi) + bonus
    r_choisi = np.where(df["Palier 2"]=="Validé", df["_r2"], df["_r1"])
    df["Récompense totale"] = (r_choisi + df["_bonus_montant"]).astype(int)

    # Mise en forme numériques “propres”
    for col in ["Récompense totale"]:
        df[col] = df[col].astype(int)

    # Colonnes de sortie (ordre)
    out_cols = [
        "user","manager","agent","diamants","heures","jours",
        "Actif","Palier 2","Récompense palier 1","Récompense palier 2",
        "Bonus débutant","Récompense totale"
    ]
    # sécurise les absents
    out_cols = [c for c in out_cols if c in df.columns]

    # Tri décroissant sur diamants
    df = df[out_cols].sort_values("diamants", ascending=False).reset_index(drop=True)
    return df

def compute_agents_table(df_crea: pd.DataFrame) -> pd.DataFrame:
    """Agrège par Agent :
       - Diamants actifs (créateurs 'Actif')
       - Diamants totaux
       - Commission : 0 si <200k. 2% de 200k à 4M, puis 3% au-delà.
       - Bonus agent : +1000 si bonus2 d’un créateur, +15000 si bonus3 d’un créateur (selon libellé sauvé par debutant_bonus)."""
    df = df_crea.copy()
    # tag actif bool
    active_mask = df["Actif"].eq("Actif")
    # diamants actifs & totaux
    g = df.groupby("agent", dropna=False)
    actifs = g.apply(lambda x: x.loc[active_mask.reindex(x.index, fill_value=False), "diamants"].sum()).rename("Diamants actifs")
    totaux = g["diamants"].sum().rename("Diamants totaux")

    # commission
    def com_calc(d_actifs):
        if d_actifs < 200_000:
            return 0
        base = min(d_actifs, 4_000_000)
        com = base * 0.02
        if d_actifs > 4_000_000:
            com += (d_actifs - 4_000_000) * 0.03
        return int(round(com))

    # bonus agent d’après le libellé du bonus (si tu veux strict: relire via diamants)
    bonus_agent = g.apply(
        lambda x: int((x["_bonus_montant"]==1088).sum())*1000 + int((x["_bonus_montant"]==3000).sum())*15000
    ).rename("Bonus agent")

    out = pd.concat([actifs, totaux, bonus_agent], axis=1).fillna(0)
    out["Commission"] = out["Diamants actifs"].apply(com_calc)
    out["Récompense totale agent"] = (out["Commission"] + out["Bonus agent"]).astype(int)

    out = out.reset_index().rename(columns={"agent":"Agent"})
    out = out.sort_values("Diamants actifs", ascending=False)
    return out

def compute_managers_table(df_crea: pd.DataFrame) -> pd.DataFrame:
    """Identique aux agents mais par Groupe/Manager.
       Bonus manager : 5000 si un créateur déclenche Bonus 3 (3000 côté créateur)."""
    df = df_crea.copy()
    active_mask = df["Actif"].eq("Actif")
    g = df.groupby("manager", dropna=False)
    actifs = g.apply(lambda x: x.loc[active_mask.reindex(x.index, fill_value=False), "diamants"].sum()).rename("Diamants actifs")
    totaux = g["diamants"].sum().rename("Diamants totaux")

    def com_calc(d_actifs):
        if d_actifs < 200_000:
            return 0
        base = min(d_actifs, 4_000_000)
        com = base * 0.02
        if d_actifs > 4_000_000:
            com += (d_actifs - 4_000_000) * 0.03
        return int(round(com))

    bonus_mgr = g.apply(lambda x: int((x["_bonus_montant"]==3000).sum())*5000).rename("Bonus manager")

    out = pd.concat([actifs, totaux, bonus_mgr], axis=1).fillna(0)
    out["Commission"] = out["Diamants actifs"].apply(com_calc)
    out["Récompense totale manager"] = (out["Commission"] + out["Bonus manager"]).astype(int)

    out = out.reset_index().rename(columns={"manager":"Manager"})
    out = out.sort_values("Diamants actifs", ascending=False)
    return out
