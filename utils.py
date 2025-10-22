# utils.py — version complète (avec load_df)
from __future__ import annotations
import pandas as pd
import numpy as np

# -------------------- mapping colonnes --------------------
CANON = {
    "period":        "Période des données",
    "username":      "Nom d’utilisateur",
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
    "period": ["Période des données","periode des données","période","periode"],
    "username": ["Nom d’utilisateur","Nom d'utilisateur","username","utilisateur"],
    "group": ["Groupe","manager","groupe/manager"],
    "agent": ["Agent","agent(e)"],
    "relation_date": ["Date d’établissement de la relation","date d'etablissement de la relation","date relation"],
    "diamonds": ["Diamants","diamant","diamonds"],
    "live_hours": ["Durée de LIVE (heures)","duree de live (heures)","heures live","durée live (heures)"],
    "live_days": ["Jours de passage en LIVE valides","jours de passage en live valides","jours live","jours de live"],
    "al_status": ["Statut du diplôme","al","statut du diplome"],
}

# -------------------- lecture fichiers --------------------
def _read_one(upload):
    """Prend un UploadedFile Streamlit (ou bytes) et renvoie un DataFrame."""
    if upload is None:
        return pd.DataFrame()
    name = getattr(upload, "name", "") or ""
    # data en bytes
    data = upload if isinstance(upload, (bytes, bytearray)) else upload.read()
    if name.lower().endswith((".xlsx",".xls")):
        return pd.read_excel(data)
    return pd.read_csv(pd.io.common.BytesIO(data), sep=None, engine="python")

def load_df(files, history_file=None):
    """Concatène 1..N fichiers source ; lit l’historique facultatif."""
    if not files:
        return pd.DataFrame(), pd.DataFrame()
    if not isinstance(files, (list, tuple)):
        files = [files]
    parts = []
    for f in files:
        try:
            df = _read_one(f)
            if not df.empty:
                parts.append(df)
        except Exception:
            continue
    src = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    hist = pd.DataFrame()
    if history_file is not None:
        try:
            hist = _read_one(history_file)
        except Exception:
            hist = pd.DataFrame()
    return src, hist

# -------------------- normalisation colonnes --------------------
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    colmap = {}
    low = {c.strip().lower(): c for c in df.columns}
    for key, names in ALIASES.items():
        for name in names:
            c = low.get(name.strip().lower())
            if c is not None:
                colmap[CANON[key]] = c
                break
    out = df.copy()
    for key, canon in CANON.items():
        src = colmap.get(canon)
        out[canon] = out[src] if src in out.columns else np.nan
    return out[REQUIRED].copy()

def _to_datetime(s):
    try:
        return pd.to_datetime(s, errors="coerce", utc=True).dt.tz_localize(None)
    except Exception:
        return pd.to_datetime(s, errors="coerce")

# -------------------- règles bonus --------------------
BONUS_THRESHOLDS = [(500_000,3,3000),(150_000,2,1088),(75_000,1,500)]
AGENT_BONUS   = {2:1000, 3:15000}
MANAGER_BONUS = {2:1000, 3:5000}

def _beginner_eligible(al_status, relation_date, ref_date):
    is_deb = True
    if isinstance(al_status, str):
        t = al_status.lower()
        if "diplôm" in t or "diplom" in t:  # diplômé => pas débutant
            is_deb = False
    if pd.isna(relation_date): return False
    delta = (ref_date.normalize() - relation_date.normalize()).days
    return is_deb and 0 <= delta <= 90

def _highest_level(d):
    for th,lev,_ in BONUS_THRESHOLDS:
        if pd.notna(d) and float(d) >= th:
            return lev
    return 0

def _level_amount(level):
    for _,lev,amt in BONUS_THRESHOLDS:
        if level==lev: return amt
    return 0

# -------------------- historique --------------------
H_ALIASES = {
    "username": ["Nom d’utilisateur","Nom d'utilisateur","username"],
    "already_used_level": ["already_used_level","bonus_deja_utilise_niveau","bonus_used_level"],
    "confirmed_150k": ["confirmed_150k","deja_150k","a_deja_fait_150k"],
}
def _normalize_history(h):
    if h is None or h.empty:
        return pd.DataFrame(columns=["username","already_used_level","confirmed_150k"])
    low = {c.strip().lower(): c for c in h.columns}
    out = pd.DataFrame()
    for k,als in H_ALIASES.items():
        col = None
        for a in als:
            col = low.get(a.strip().lower())
            if col: break
        out[k] = h[col] if col in h.columns else np.nan
    out["username"] = out["username"].astype(str).str.strip()
    out["already_used_level"] = pd.to_numeric(out["already_used_level"], errors="coerce").fillna(0).astype(int)
    out["confirmed_150k"] = out["confirmed_150k"].astype(str).str.lower().isin(["1","true","vrai","yes","oui"])
    return out

# -------------------- calculs --------------------
def compute_creators_table(df: pd.DataFrame, history_df: pd.DataFrame|None=None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    src = _normalize_columns(df)

    # types
    src[CANON["diamonds"]]   = pd.to_numeric(src[CANON["diamonds"]], errors="coerce").fillna(0)
    src[CANON["live_hours"]] = pd.to_numeric(src[CANON["live_hours"]], errors="coerce").fillna(0)
    src[CANON["live_days"]]  = pd.to_numeric(src[CANON["live_days"]], errors="coerce").fillna(0)
    src[CANON["relation_date"]] = _to_datetime(src[CANON["relation_date"]])

    # date de référence (fin de période trouvée)
    per = pd.to_datetime(src[CANON["period"]], errors="coerce")
    ref_date = per.dropna().iloc[-1] if per.notna().any() else pd.Timestamp.utcnow().tz_localize(None)

    # agrégation par utilisateur
    key = CANON["username"]
    g = src.groupby(key, dropna=False).agg({
        CANON["diamonds"]:"sum",
        CANON["live_hours"]:"sum",
        CANON["live_days"]:"sum",
        CANON["relation_date"]:"min",
        CANON["period"]:"max",
        CANON["agent"]: lambda s: s.dropna().iloc[0] if s.dropna().size else np.nan,
        CANON["group"]: lambda s: s.dropna().iloc[0] if s.dropna().size else np.nan,
        CANON["al_status"]: lambda s: s.dropna().iloc[0] if s.dropna().size else np.nan,
    }).reset_index()

    hist = _normalize_history(history_df if history_df is not None else pd.DataFrame())
    used_map = hist.set_index("username")["already_used_level"] if not hist.empty else pd.Series(dtype=int)
    conf_map = hist.set_index("username")["confirmed_150k"] if not hist.empty else pd.Series(dtype=bool)

    names = g[key].astype(str).str.strip()
    already_used = names.map(used_map).fillna(0).astype(int)
    confirmed_150k = names.map(conf_map).fillna(False) | (g[CANON["diamonds"]] >= 150_000)

    beginner = g.apply(lambda r: _beginner_eligible(r[CANON["al_status"]], r[CANON["relation_date"]], ref_date), axis=1)
    level = g[CANON["diamonds"]].apply(_highest_level).astype(int)

    payable_level = np.where((beginner) & (level > already_used), level, 0).astype(int)
    bonus_amount = pd.Series(payable_level).apply(_level_amount).astype(int)

    agent_bonus = np.select([payable_level==3, payable_level==2], [AGENT_BONUS[3], AGENT_BONUS[2]], default=0).astype(int)
    manager_bonus = np.select([payable_level==3, payable_level==2], [MANAGER_BONUS[3], MANAGER_BONUS[2]], default=0).astype(int)

    out = pd.DataFrame({
        CANON["period"]: g[CANON["period"]],
        CANON["username"]: g[CANON["username"]],
        CANON["group"]: g[CANON["group"]],
        CANON["agent"]: g[CANON["agent"]],
        CANON["relation_date"]: g[CANON["relation_date"]],
        CANON["diamonds"]: g[CANON["diamonds"]].astype(int),
        CANON["live_hours"]: g[CANON["live_hours"]].astype(int),
        CANON["live_days"]: g[CANON["live_days"]].astype(int),
        CANON["al_status"]: g[CANON["al_status"]],
        "Débutant éligible (≤90j)": beginner.astype(bool),
        "Palier bonus atteint (1/2/3)": level,
        "Palier bonus payé (1/2/3)": payable_level,
        "Montant bonus (diamants)": bonus_amount,
        "Bonus Agent (diamants)": agent_bonus,
        "Bonus Manager (diamants)": manager_bonus,
        "Confirmé 150k": confirmed_150k.astype(bool),
    })
    return out

def compute_agents_table(creators_df: pd.DataFrame) -> pd.DataFrame:
    if creators_df is None or creators_df.empty:
        return pd.DataFrame(columns=["Agent","Créateurs concernés","Bonus total (diamants)"])
    df = creators_df.copy()
    df["Agent"] = df["Agent"].fillna("—")
    df["Bonus Agent (diamants)"] = pd.to_numeric(df.get("Bonus Agent (diamants)"), errors="coerce").fillna(0).astype(int)
    agg = df.groupby("Agent", dropna=False).agg(
        **{
            "Bonus total (diamants)": ("Bonus Agent (diamants)", "sum"),
            "Créateurs concernés": ("Nom d’utilisateur", "nunique"),
        }
    ).reset_index().sort_values("Bonus total (diamants)", ascending=False)
    return agg

def compute_managers_table(creators_df: pd.DataFrame) -> pd.DataFrame:
    if creators_df is None or creators_df.empty:
        return pd.DataFrame(columns=["Groupe","Créateurs concernés","Bonus total (diamants)"])
    df = creators_df.copy()
    df["Groupe"] = df["Groupe"].fillna("—")
    df["Bonus Manager (diamants)"] = pd.to_numeric(df.get("Bonus Manager (diamants)"), errors="coerce").fillna(0).astype(int)
    agg = df.groupby("Groupe", dropna=False).agg(
        **{
            "Bonus total (diamants)": ("Bonus Manager (diamants)", "sum"),
            "Créateurs concernés": ("Nom d’utilisateur", "nunique"),
        }
    ).reset_index().sort_values("Bonus total (diamants)", ascending=False)
    return agg
def ensure_df(x):
    """Retourne le DataFrame si x est un tuple (df, …)."""
    return x[0] if isinstance(x, tuple) else x

