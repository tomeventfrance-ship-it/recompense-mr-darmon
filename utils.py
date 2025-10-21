# utils.py — version stable (alignements corrigés)

import io, re
import pandas as pd
import numpy as np

# ---------- Lecture & mapping ----------
CANDIDATES = {
    "diamants": ["Diamants","Total diamants","Nombre de diamants","Diamonds"],
    "heures":   ["Durée de live (heures)","Durée de live","Heures de live","Temps de live (h)"],
    "jours":    ["Jours de passage en live","Jours de live","Nombre de jours de live"],
    "agent":    ["Agent","Agent (col.E)","Agent(e)"],
    "manager":  ["Groupe/Manager","Manager","Groupe","Groupe (col.D)"],
    "user":     ["Nom d’utilisateur","Nom d'utilisateur","Username","Utilisateur","Pseudo"],
    "al":       ["AL","Débutant non diplômé 90j","Debutant non diplome 90j"],
    "deja150":  ["déjà 150k","deja 150k","a deja fait 150k"],
    "bonus_used": ["bonus_deja_utilise","bonus déjà utilisé","bonus utilise","bonus_used"]
}
CANON = ["user","manager","agent","diamants","heures","jours","al","deja150","bonus_used"]

def _norm(s:str)->str:
    s = str(s).lower()
    s = s.encode("ascii","ignore").decode()
    s = re.sub(r"[^a-z0-9 ]+"," ",s)
    s = re.sub(r"\s+"," ",s).strip()
    return s

def _pick(df:pd.DataFrame, keys)->str|None:
    norm = {_norm(c): c for c in df.columns}
    for k in keys:
        n=_norm(k)
        if n in norm: return norm[n]
    for k in keys:
        nk=_norm(k)
        for c in df.columns:
            if nk in _norm(c): return c
    return None

def load_df(file_like)->pd.DataFrame:
    name = getattr(file_like,"name","")
    if isinstance(file_like,(bytes,bytearray)):
        bio=io.BytesIO(file_like); bio.name=name; file_like=bio
    raw = pd.read_csv(file_like) if str(name).lower().endswith(".csv") else pd.read_excel(file_like)

    found={}
    for canon,cand in CANDIDATES.items():
        col=_pick(raw,cand)
        if col is not None: found[canon]=col

    missing_core=[k for k in ["diamants","heures","jours"] if k not in found]
    if missing_core:
        pretty={"diamants":"Diamants","heures":"Durée de live (heures)","jours":"Jours de passage en live"}
        raise ValueError("Colonnes manquantes: "+", ".join(pretty[k] for k in missing_core))

    use_cols=[found[k] for k in CANON if k in found]
    df = raw.loc[:,use_cols].rename(columns={found[k]:k for k in found})

    for opt in CANON:
        if opt not in df.columns: df[opt]=""

    for num in ["diamants","heures","jours"]:
        df[num]=pd.to_numeric(df[num],errors="coerce").fillna(0)

    for s in ["user","agent","manager","al","deja150","bonus_used"]:
        df[s]=df[s].astype(str).replace({"nan":""}).str.strip()

    return df[CANON]

# ---------- Barèmes ----------
def palier1_reward(d):
    if d>=2_000_000: return round(d*0.04)
    table=[
        (35_000, 74_999, 1_000),
        (75_000, 149_000, 2_500),
        (150_000, 199_999, 5_000),
        (200_000, 299_999, 6_000),
        (300_000, 399_999, 7_999),
        (400_000, 499_999,12_000),
        (500_000, 599_999,15_000),
        (600_000, 699_999,18_000),
        (700_000, 799_999,21_000),
        (800_000, 899_999,24_000),
        (900_000, 999_999,26_999),
        (1_000_000,1_499_999,30_000),
        (1_500_000,1_999_999,44_999),
    ]
    for a,b,v in table:
        if a<=d<=b: return v
    return 0

def palier2_reward(d):
    if d>=2_000_000: return round(d*0.04)
    table=[
        (35_000, 74_999, 1_000),
        (75_000, 149_000, 2_500),
        (150_000, 199_999, 6_000),
        (200_000, 299_999, 7_999),
        (300_000, 399_999,12_000),
        (400_000, 499_999,15_000),
        (500_000, 599_999,20_000),
        (600_000, 699_999,24_000),
        (700_000, 799_999,26_999),
        (800_000, 899_999,30_000),
        (900_000, 999_999,35_000),
        (1_000_000,1_499_999,39_999),
        (1_500_000,1_999_999,59_999),
    ]
    for a,b,v in table:
        if a<=d<=b: return v
    return 0

def _is_true(s:str)->bool:
    return _norm(s) in {"1","true","vrai","oui","yes","used"}

def debutant_bonus_series(diamants:pd.Series, al:pd.Series, bonus_used:pd.Series)->tuple[pd.Series,pd.Series]:
    al_ok = al.map(lambda x: _norm(x) in {"al","debutant non diplome 90j","debutant non diplome 90 j","debutant"})
    not_used = ~bonus_used.map(_is_true)
    elig = al_ok & not_used

    b = pd.Series(0, index=diamants.index, dtype=int)
    b = np.where(elig & (diamants.between(75_000,149_999)), 500, b)
    b = np.where(elig & (diamants.between(150_000,499_999)),1088, b)
    b = np.where(elig & (diamants.between(500_000,2_000_000)),3000, b)
    b = pd.Series(b, index=diamants.index, dtype=int)

    flag = pd.Series(np.where(b>0,"Validé","Non validé"), index=diamants.index)
    return b, flag

# ---------- Créateurs ----------
def compute_creators_table(df:pd.DataFrame)->pd.DataFrame:
    idx = df.index

    actif = ((df["jours"]>=12) & (df["heures"]>=25)) | (df["diamants"]>=150_000)
    palier2 = (df["jours"]>=20) & (df["heures"]>=80)

    r1 = df["diamants"].apply(palier1_reward)
    r2 = df["diamants"].apply(palier2_reward)

    aff_p1 = pd.Series(np.where(palier2, 0, r1), index=idx, dtype=int)
    aff_p2 = pd.Series(np.where(palier2, r2, 0), index=idx, dtype=int)

    bonus_vals, bonus_flags = debutant_bonus_series(df["diamants"], df["al"], df["bonus_used"])
    total = (aff_p1 + aff_p2 + bonus_vals).astype(int)

    out = pd.DataFrame({
        "Nom d’utilisateur": df["user"].replace({"":"(non fourni)"}),
        "Groupe/Manager": df["manager"],
        "Agent": df["agent"],
        "Diamants": df["diamants"].astype(int),
        "Durée de live (heures)": df["heures"].astype(int),
        "Jours de passage en live": df["jours"].astype(int),
        "Actif": np.where(actif,"Validé","Non validé"),
        "Palier 2": np.where(palier2,"Validé","Non validé"),
        "Récompense palier 1": aff_p1.values,
        "Récompense palier 2": aff_p2.values,
        "Bonus débutant": bonus_flags.values,
        "Récompense totale": total.values,
    }, index=idx)

    out = out.sort_values(by=["Diamants","Récompense totale"], ascending=[False,False]).reset_index(drop=True)
    return out

# ---------- Agents ----------
def _agent_reward(sum_active:int)->int:
    if sum_active < 200_000:
        return 0
    if sum_active < 4_000_000:
        return round(sum_active * 0.02)
    return round(sum_active * 0.03)

def compute_agents_table(df:pd.DataFrame)->pd.DataFrame:
    actif = ((df["jours"]>=12) & (df["heures"]>=25)) | (df["diamants"]>=150_000)

    g = df.groupby("agent", dropna=False)
    total = g["diamants"].sum().astype(int)
    actifs = df.loc[actif].groupby("agent", dropna=False)["diamants"].sum().reindex(total.index).fillna(0).astype(int)

    reward = actifs.apply(_agent_reward).astype(int)
    perte = (total - actifs).astype(int)

    out = pd.DataFrame({
        "Agent": total.index.where(total.index!="", "(non défini)"),
        "Diamants actifs": actifs.values,
        "Diamants totaux": total.values,
        "Perte (diamants inactifs)": perte.values,
        "Récompense agent": reward.values
    }).sort_values(by=["Diamants actifs","Diamants totaux"], ascending=False).reset_index(drop=True)

    return out

# ---------- Managers ----------
def compute_managers_table(df:pd.DataFrame)->pd.DataFrame:
    actif = ((df["jours"]>=12) & (df["heures"]>=25)) | (df["diamants"]>=150_000)
    palier3 = df["diamants"]>=500_000

    g = df.groupby("manager", dropna=False)
    total = g["diamants"].sum().astype(int)
    actifs = df.loc[actif].groupby("manager", dropna=False)["diamants"].sum().reindex(total.index).fillna(0).astype(int)

    base_reward = actifs.apply(_agent_reward).astype(int)
    bonus_3 = df.loc[palier3].groupby("manager", dropna=False)["diamants"].count().reindex(total.index).fillna(0).astype(int)*5000
    perte = (total - actifs).astype(int)

    out = pd.DataFrame({
        "Manager/Groupe": total.index.where(total.index!="","(non défini)"),
        "Diamants actifs": actifs.values,
        "Diamants totaux": total.values,
        "Perte (diamants inactifs)": perte.values,
        "Bonus 3 (5000 x nb créateurs ≥500k)": bonus_3.values,
        "Récompense manager (hors bonus)": base_reward.values,
        "Récompense totale": (base_reward + bonus_3).values.astype(int)
    }).sort_values(by=["Diamants actifs","Diamants totaux"], ascending=False).reset_index(drop=True)

    return out
