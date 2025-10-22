# -*- coding: utf-8 -*-
import io
import re
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional

import numpy as np
import pandas as pd

# ===============================================================
#              COLONNES CANONIQUES & ALIAS TOLÉRANTS
# ===============================================================

# Libellés cibles (ceux qu’on utilisera partout dans le code)
CANON = {
    "period": "Période des données",                            # A
    "username": "Nom d’utilisateur du/de la créateur(trice)",   # C
    "group": "Groupe/Manager",                                  # D
    "agent": "Agent",                                           # E
    "relation_date": "Date d’établissement de la relation",     # F
    "diamonds": "Diamants",                                     # H
    "live_hours": "Durée de LIVE (heures)",                     # I
    "live_days": "Jours de passage en LIVE valides",            # J
    "al_status": "Statut du diplôme",                           # AL (AL = débutant / non diplômé 90j)
}

# Variantes fréquemment vues (accents/majuscules/abréviations)
ALIASES = {
    "period": [
        "période des données", "periode des donnees", "période",
        "période des données (a)", "période données",
    ],
    "username": [
        "nom d’utilisateur", "nom d'utilisateur", "créateur", "createur", "user",
        "nom d’utilisateur du/de la créateur(trice)",
    ],
    "group": [
        "groupe", "manager", "groupe/manager", "groupe(manager)"
    ],
    "agent": [
        "agent(e)", "agent référent", "agent referent",
    ],
    "relation_date": [
        "date d’etablissement de la relation", "date d’établissement de la relation",
        "date relation", "relation date", "date etabliss.", "date d'etablissement de la relation",
    ],
    "diamonds": [
        "diamant", "nb diamants", "diamonds", "total diamants"
    ],
    "live_hours": [
        "durée de live (heures)", "duree de live (heures)", "heures live", "durée de live",
        "durée de live (h)", "live hours"
    ],
    "live_days": [
        "jours de passage en live valides", "jours de passage en live", "jours live",
        "nb jours live", "live days", "jours de passage en live  valides",
    ],
    "al_status": [
        "statut du diplome", "statut du diplôme", "al", "al = debutant non diplome 90j",
        "statut al", "debutant 90j",
    ],
}

# ===============================================================
#                    PARAMÈTRES – RÈGLES MÉTIER
# ===============================================================

# Seuils BONUS DÉBUTANT (non cumulables, on paie le plus haut atteint)
BONUS_TIERS = [
    (500_000, 3000, "b3"),   # palier 3
    (150_000, 1088, "b2"),   # palier 2
    (75_000,   500, "b1"),   # palier 1
]
BEGINNER_WINDOW_DAYS = 90     # fenêtre “débutant” à partir de la relation

# Bonus Agents / Managers (non cumulables)
AGENT_BONUS = {  # selon palier atteint par le créateur CE MOIS-CI
    "b2": 1000,
    "b3": 15000,
}
MANAGER_BONUS = {
    "b2": 1000,
    "b3": 5000,
}

# ===============================================================
#                          OUTILS
# ===============================================================

def _norm(s: str) -> str:
    """Normalise une étiquette: minuscule, retire accents/espaces superflus."""
    if not isinstance(s, str):
        return ""
    t = s.strip().lower()
    t = (t
         .replace("é", "e").replace("è", "e").replace("ê", "e")
         .replace("à", "a").replace("â", "a").replace("ô", "o")
         .replace("î", "i").replace("ï", "i").replace("ù", "u").replace("û", "u")
         .replace("’", "'").replace("`", "'"))
    t = re.sub(r"\s+", " ", t)
    return t


def _match_columns(df: pd.DataFrame) -> Dict[str, str]:
    """
    Essaie d’associer les colonnes du fichier aux libellés CANON en utilisant ALIASES.
    Retourne un dict: {CANON_LABEL: df_column_name}
    Lève une ValueError si une colonne essentielle manque.
    """
    cols = list(df.columns)
    norm_map = {c: _norm(c) for c in cols}

    mapping: Dict[str, str] = {}
    # 1) tentatives exactes (sensibles aux accents/majuscules)
    for key, canon in CANON.items():
        if canon in cols:
            mapping[canon] = canon

    # 2) sinon, on parcourt les alias
    for key, canon in CANON.items():
        if canon in mapping:
            continue
        candidates = [_norm(canon)] + ALIASES.get(key, [])
        candidates = [_norm(x) for x in candidates]
        found = None
        for c in cols:
            if norm_map[c] in candidates:
                found = c
                break
        if found:
            mapping[canon] = found

    # Colonnes minimales requises
    required = [
        CANON["period"], CANON["username"], CANON["group"], CANON["agent"],
        CANON["relation_date"], CANON["diamonds"], CANON["live_hours"],
        CANON["live_days"], CANON["al_status"]
    ]
    missing = [c for c in required if c not in mapping]
    if missing:
        raise ValueError(f"Colonnes manquantes : {', '.join(missing)}")

    return mapping


def _coerce_numeric(s: pd.Series) -> pd.Series:
    """Convertit en nombre (en tolérant virgules/espaces/vides)."""
    return pd.to_numeric(
        s.astype(str).str.replace(",", ".", regex=False).str.replace(r"[^\d\.-]", "", regex=True),
        errors="coerce"
    )


def _coerce_date(s: pd.Series) -> pd.Series:
    """Convertit en date (tolérant formats variés)."""
    return pd.to_datetime(s, errors="coerce", utc=False)


# ===============================================================
#                 LECTURE & NORMALISATION FICHIERS
# ===============================================================

def _read_one_file(f) -> pd.DataFrame:
    """
    Lit un fichier streamlit (UploadedFile) en DataFrame.
    Supporte .xlsx / .xls / .csv
    """
    name = getattr(f, "name", "uploaded")
    suffix = name.split(".")[-1].lower()

    if suffix in ("xlsx", "xls"):
        data = f.read()
        bio = io.BytesIO(data)
        df = pd.read_excel(bio)
    elif suffix == "csv":
        data = f.read()
        bio = io.BytesIO(data)
        df = pd.read_csv(bio, encoding="utf-8", sep=None, engine="python")
    else:
        raise ValueError(f"Format non supporté: {suffix}")
    return df


def parse_uploaded_files(uploaded_files: List) -> pd.DataFrame:
    """
    Concatène tous les fichiers importés, normalise les colonnes
    et ne conserve QUE les colonnes nécessaires à nos calculs.
    """
    if not uploaded_files:
        raise ValueError("Aucun fichier importé.")

    frames = []
    for f in uploaded_files:
        df_raw = _read_one_file(f)
        mapping = _match_columns(df_raw)

        df = pd.DataFrame({CANON_KEY: df_raw[src] for CANON_KEY, src in mapping.items()})

        # Casts
        df[CANON["diamonds"]] = _coerce_numeric(df[CANON["diamonds"]]).fillna(0)
        df[CANON["live_hours"]] = _coerce_numeric(df[CANON["live_hours"]]).fillna(0)
        df[CANON["live_days"]] = _coerce_numeric(df[CANON["live_days"]]).fillna(0)
        df[CANON["relation_date"]] = _coerce_date(df[CANON["relation_date"]])
        df[CANON["period"]] = df[CANON["period"]].astype(str).str.strip()

        # Sélection stricte des colonnes utiles (et ordre)
        df = df[[CANON[k] for k in [
            "period", "username", "group", "agent", "relation_date",
            "diamonds", "live_hours", "live_days", "al_status"
        ]]]

        frames.append(df)

    all_df = pd.concat(frames, ignore_index=True)

    # Nettoyage basique
    all_df[CANON["username"]] = all_df[CANON["username"]].astype(str).str.strip()
    all_df[CANON["group"]] = all_df[CANON["group"]].astype(str).str.strip()
    all_df[CANON["agent"]] = all_df[CANON["agent"]].astype(str).str.strip()
    all_df[CANON["al_status"]] = all_df[CANON["al_status"]].astype(str).str.strip()

    return all_df


# ===============================================================
#                    LOGIQUE CRÉATEURS (Bonus)
# ===============================================================

def _within_beginner_window(relation_date: pd.Timestamp, period_str: str) -> bool:
    """
    Vrai si la période (mois) est dans la fenêtre 90j après relation_date.
    On place la période au dernier jour du mois pour la comparaison.
    """
    if pd.isna(relation_date):
        return False
    try:
        # On tolère plusieurs formats pour 'period'
        # ex: "2025-10", "2025/10", "2025-10-01", "2025-10-31 00:00:00"
        p = str(period_str).strip()
        pdt = pd.to_datetime(p, errors="coerce")
        if pd.isna(pdt):
            # Essai sur "YYYY-MM"
            m = re.match(r"^\s*(\d{4})[-/](\d{1,2})", p)
            if m:
                y, mth = int(m.group(1)), int(m.group(2))
                pdt = pd.Timestamp(year=y, month=mth, day=1)
        if pd.isna(pdt):
            return False
        # fin de mois
        month_end = (pdt + pd.offsets.MonthEnd(0)).normalize()
        return month_end <= (relation_date + pd.Timedelta(days=BEGINNER_WINDOW_DAYS))
    except Exception:
        return False


def _decide_beginner_bonus(
    diamonds: float,
    is_beginner_window: bool,
    used_flags: Dict[str, bool]
) -> Tuple[int, Optional[str], Dict[str, bool]]:
    """
    Renvoie (montant, code_tier, new_used_flags)
      - montant: 0 si non éligible,
      - code_tier: "b1"/"b2"/"b3" si attribué,
      - new_used_flags: flags mis à jour si on a consommé un palier.
    Règles :
      - fenêtre 90j obligatoire,
      - non cumul : on paie le plus HAUT palier atteint,
      - chaque palier n'est payé qu'une seule fois à vie (via used_flags).
    """
    new_flags = dict(used_flags or {})
    if not is_beginner_window:
        return 0, None, new_flags

    for threshold, amount, code in BONUS_TIERS:  # triés du plus haut au plus bas
        if diamonds >= threshold and not new_flags.get(code, False):
            new_flags[code] = True  # consommé à vie
            return amount, code, new_flags

    return 0, None, new_flags


def compute_creators_table(
    df: pd.DataFrame,
    history_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Calcule, pour chaque ligne (créateur x période), les paliers atteints et
    le BONUS DÉBUTANT à payer (le plus haut, non cumulable, fenêtre 90j, jamais deux fois).
    `history_df` peut contenir les colonnes:
      username, b1_used, b2_used, b3_used, confirmed_150k (bool)
    """
    df = df.copy()

    # Index d’historique (si fourni)
    hist = history_df.copy() if history_df is not None else pd.DataFrame(
        columns=["username", "b1_used", "b2_used", "b3_used", "confirmed_150k"]
    )
    hist["username"] = hist["username"].astype(str).str.strip()
    hist = hist.drop_duplicates(subset=["username"]).set_index("username", drop=False)

    out_rows = []
    for _, row in df.iterrows():
        username = str(row[CANON["username"]]).strip()
        period = str(row[CANON["period"]]).strip()
        grp = str(row[CANON["group"]]).strip()
        agent = str(row[CANON["agent"]]).strip()
        rel_date = row[CANON["relation_date"]]
        diamonds = float(row[CANON["diamonds"]]) if pd.notna(row[CANON["diamonds"]]) else 0.0
        hours = float(row[CANON["live_hours"]]) if pd.notna(row[CANON["live_hours"]]) else 0.0
        days = float(row[CANON["live_days"]]) if pd.notna(row[CANON["live_days"]]) else 0.0
        al = str(row[CANON["al_status"]]).strip()

        # Récup flags historiques si présents
        used_flags = {"b1": False, "b2": False, "b3": False}
        confirmed_150k = False
        if username in hist.index:
            used_flags["b1"] = bool(hist.loc[username].get("b1_used", False))
            used_flags["b2"] = bool(hist.loc[username].get("b2_used", False))
            used_flags["b3"] = bool(hist.loc[username].get("b3_used", False))
            confirmed_150k = bool(hist.loc[username].get("confirmed_150k", False))

        # “Confirmé 150k” si historique le dit, sinon auto-confirm si ce mois >=150k
        if diamonds >= 150_000:
            confirmed_150k = True

        # Fenêtre 90j pour bonus débutant
        in_window = _within_beginner_window(rel_date, period)

        bonus_amount, bonus_code, new_flags = _decide_beginner_bonus(
            diamonds=diamonds,
            is_beginner_window=in_window and (al.lower().startswith("deb") or "90" in al),
            used_flags=used_flags
        )

        # Palier atteint (pour agents/managers)
        palier = None
        if diamonds >= 500_000:
            palier = "b3"
        elif diamonds >= 150_000:
            palier = "b2"
        elif diamonds >= 75_000:
            palier = "b1"
        else:
            palier = None

        out_rows.append({
            CANON["period"]: period,
            CANON["username"]: username,
            CANON["group"]: grp,
            CANON["agent"]: agent,
            CANON["relation_date"]: rel_date,
            CANON["diamonds"]: int(diamonds),
            CANON["live_hours"]: float(hours),
            CANON["live_days"]: float(days),
            CANON["al_status"]: al,
            "Débutant: éligible 90j": bool(in_window),
            "Palier atteint": palier,                 # b1/b2/b3/None
            "Montant bonus (débutant)": int(bonus_amount),
            "Code bonus payé": bonus_code,            # b1/b2/b3/None
            "Confirmé 150k": bool(confirmed_150k),
            # Flags mis à jour (pour history.update)
            "_b1_used_new": bool(new_flags.get("b1", False)),
            "_b2_used_new": bool(new_flags.get("b2", False)),
            "_b3_used_new": bool(new_flags.get("b3", False)),
        })

    table = pd.DataFrame(out_rows)

    # Ordonner les colonnes
    front = [
        CANON["period"], CANON["username"], CANON["group"], CANON["agent"],
        CANON["relation_date"], CANON["diamonds"], CANON["live_hours"],
        CANON["live_days"], CANON["al_status"],
        "Débutant: éligible 90j", "Palier atteint", "Montant bonus (débutant)",
        "Code bonus payé", "Confirmé 150k",
    ]
    hidden_flags = ["_b1_used_new", "_b2_used_new", "_b3_used_new"]
    table = table[front + hidden_flags]

    return table


# ===============================================================
#        LOGIQUE AGENTS / MANAGERS À PARTIR DES CRÉATEURS
# ===============================================================

def _highest_agent_bonus(palier: Optional[str]) -> int:
    if palier is None:
        return 0
    return int(AGENT_BONUS.get(palier, 0))


def _highest_manager_bonus(palier: Optional[str]) -> int:
    if palier is None:
        return 0
    return int(MANAGER_BONUS.get(palier, 0))


def compute_agents_table_from_creators(
    creators_table: pd.DataFrame,
    hist_agents: Optional[pd.DataFrame] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    À partir du tableau créateurs, calcule la prime agent par ligne (non cumul : on garde
    le PLUS HAUT palier b2/b3). Agrège par agent.
    Retourne (table_agents_agrégée, journal_evenements).
    """
    df = creators_table.copy()
    rows = []
    events = []
    for _, r in df.iterrows():
        agent = str(r.get(CANON["agent"], "")).strip()
        username = str(r.get(CANON["username"], "")).strip()
        period = str(r.get(CANON["period"], "")).strip()
        palier = r.get("Palier atteint", None)
        amount = _highest_agent_bonus(palier)

        rows.append({"Agent": agent, "Montant": int(amount)})
        if amount > 0:
            events.append({
                "Période": period,
                "Agent": agent,
                "Créateur": username,
                "Palier": palier,
                "Prime agent": int(amount),
            })

    base = pd.DataFrame(rows)
    if base.empty:
        return pd.DataFrame(columns=["Agent", "Total primes"]), pd.DataFrame(columns=["Période", "Agent", "Créateur", "Palier", "Prime agent"])

    agg = base.groupby("Agent", dropna=False)["Montant"].sum().reset_index()
    agg.rename(columns={"Montant": "Total primes"}, inplace=True)

    return agg, pd.DataFrame(events)


def compute_managers_table_from_creators(
    creators_table: pd.DataFrame,
    hist_managers: Optional[pd.DataFrame] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    À partir du tableau créateurs, calcule la prime manager par ligne (non cumul : plus haut b2/b3).
    Agrège par groupe/manager.
    Retourne (table_managers_agrégée, journal_evenements).
    """
    df = creators_table.copy()
    rows = []
    events = []
    for _, r in df.iterrows():
        manager = str(r.get(CANON["group"], "")).strip()
        username = str(r.get(CANON["username"], "")).strip()
        period = str(r.get(CANON["period"], "")).strip()
        palier = r.get("Palier atteint", None)
        amount = _highest_manager_bonus(palier)

        rows.append({"Manager": manager, "Montant": int(amount)})
        if amount > 0:
            events.append({
                "Période": period,
                "Manager": manager,
                "Créateur": username,
                "Palier": palier,
                "Prime manager": int(amount),
            })

    base = pd.DataFrame(rows)
    if base.empty:
        return pd.DataFrame(columns=["Manager", "Total primes"]), pd.DataFrame(columns=["Période", "Manager", "Créateur", "Palier", "Prime manager"])

    agg = base.groupby("Manager", dropna=False)["Montant"].sum().reset_index()
    agg.rename(columns={"Montant": "Total primes"}, inplace=True)

    return agg, pd.DataFrame(events)

# --- Compat: noms attendus par app.py ---
try:
    compute_creators_table
except NameError:
    compute_creators_table = compute_creators  # adapte si ton vrai nom est build_creators_table, etc.

try:
    compute_agents_table
except NameError:
    compute_agents_table = compute_agents

try:
    compute_managers_table
except NameError:
    compute_managers_table = compute_managers
