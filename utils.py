# utils.py — Strict aux colonnes convenues + parseur heures + montant bonus

import io, re
import pandas as pd
import numpy as np

# --------- Noms exacts attendus ----------
EXPECTED = {
    "periode"   : "Période des données",
    "user"      : "Nom d'utilisateur du/de la créateur(trice)",
    "manager"   : "Groupe",
    "agent"     : "Agent",
    "relation"  : "Date d'établissement de la relation",
    "diamants"  : "Diamants",
    "heures"    : "Durée de LIVE",
    "jours"     : "Jours de passage en LIVE valides",
    "al"        : "Statut du diplôme",
}

def _norm_text(s: str) -> str:
    s = str(s)
    s = s.encode("ascii","ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

BACKUPS = {
    "periode":   {"periode des donnees","periode"},
    "user":      {"nom d utilisateur du de la createur trice","nom d utilisateur","username"},
    "manager":   {"groupe","manager","groupe manager"},
    "agent":     {"agent","agent e"},
    "relation":  {"date d etablissement de la relation","date relation"},
    "diamants":  {"diamants","diamonds"},
    "heures":    {"duree de live","duree live","heures de live","temps de live h","duree de live heures","duree de live h"},
    "jours":     {"jours de passage en live valides","jours de live","nb jours live"},
    "al":        {"statut du diplome","al","debutant non diplome 90j","debutant"},
}

def _pick_strict(df: pd.DataFrame, key: str) -> str:
    exact = EXPECTED[key]
    if exact in df.columns: return exact
    m = {_norm_text(c): c for c in map(str, df.columns)}
    for alt in BACKUPS.get(key, set()):
        if alt in m: return m[alt]
    raise ValueError(f"Colonne manquante: « {exact} »")

# --------- conversion "Durée de live" vers heures (int) ----------
def _parse_hours_series(s: pd.Series) -> pd.Series:
    def _one(x):
        if pd.isna(x): return 0.0
        # déjà numérique
        if isinstance(x,(int,float,np.integer,np.floating)): 
            return float(x)
        t = str(x).strip()
        if t == "": return 0.0
        # virgule décimale
        if re.fullmatch(r"\d+,\d+", t):
            return float(t.replace(",", "."))
        # HH:MM[:SS]
        if ":" in t:
            parts = [p for p in re.split(r":", t) if p!=""]
            try:
                h = float(parts[0]); m = float(parts[1]) if len(parts)>1 else 0.0
                s = float(parts[2]) if len(parts)>2 else 0.0
                return h + m/60.0 + s/3600.0
            except: 
                pass
        # “12 h 30”, “12h30”, “1h”, “90 min”
        m = re.findall(r"(\d+(?:[.,]\d+)?)\s*(h|heures|hour|hrs|min|m)", t.lower())
        if m:
            total = 0.0; last_unit = None
            for val, unit in m:
                v = float(val.replace(",", "."))
                if unit.startswith("h"):
                    total += v
                    last_unit = "h"
                else:
                    total += v/60.0
                    last_unit = "m"
            return total
        # nombre texte “12.5”
        try:
            return float(t.replace(",", "."))
        except:
            return 0.0
    out = s.apply(_one).fillna(0.0)
    # on tronque à l’entier (comme demandé)
    return out.astype(float).apply(lambda v: int(v))

def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = list(map(str, df.columns))
    cols = {k: _pick_strict(df, k) for k in EXPECTED.keys()}
    out = df[[cols[k] for k in EXPECTED.keys()]].rename(columns={
        cols["periode"] : "Période des données",
        cols["user"]    : "Nom d’utilisateur",
        cols["manager"] : "Groupe/Manager",
        cols["agent"]   : "Agent",
        cols["relation"]: "Date relation",
        cols["diamants"]: "Diamants",
        cols["heures"]  : "Durée de live (heures)",
        cols["jours"]   : "Jours de passage en live",
        cols["al"]      : "AL",
    })

    # Types
    out["Diamants"] = pd.to_numeric(out["Diamants"], errors="coerce").fillna(0).astype(int)
    out["Jours de passage en live"] = pd.to_numeric(out["Jours de passage en live"], errors="coerce").fillna(0).astype(int)
    out["Durée de live (heures)"] = _parse_hours_series(out["Durée de live (heures)"])
    for n in ["Nom d’utilisateur","Groupe/Manager","Agent","AL","Période des données","Date relation"]:
        out[n] = out[n].astype(str).fillna("").str.strip()
    out["Nom d’utilisateur"] = out["Nom d’utilisateur"].replace({"":"(non fourni)"})
    return out

def load_df(file_like) -> pd.DataFrame:
    if isinstance(file_like, pd.DataFrame): return _standardize(file_like)
    name = getattr(file_like, "name", "")
    if isinstance(file_like, (bytes, bytearray)):
        bio = io.BytesIO(file_like); bio.name = name or ""
        file_like = bio
    fn = str(name).lower()
    if fn.endswith(".csv"):
        raw = pd.read_csv(file_like)
    elif fn.endswith((".xls",".xlsx")):
        raw = pd.read_excel(file_like)
    else:
        try: raw = pd.read_csv(file_like)
        except Exception:
            if hasattr(file_like,"seek"): file_like.seek(0)
            raw = pd.read_excel(file_like)
    return _standardize(raw)

# --------- Barèmes ----------
def palier1_reward(d:int)->int:
    if d>=2_000_000: return round(d*0.04)
    table=[(35_000,74_999,1_000),(75_000,149_000,2_500),(150_000,199_999,5_000),
           (200_000,299_999,6_000),(300_000,399_999,7_999),(400_000,499_999,12_000),
           (500_000,599_999,15_000),(600_000,699_999,18_000),(700_000,799_999,21_000),
           (800_000,899_999,24_000),(900_000,999_999,26_999),(1_000_000,1_499_999,30_000),
           (1_500_000,1_999_999,44_999)]
    for a,b,v in table:
        if a<=d<=b: return v
    return 0

def palier2_reward(d:int)->int:
    if d>=2_000_000: return round(d*0.04)
    table=[(35_000,74_999,1_000),(75_000,149_000,2_500),(150_000,199_999,6_000),
           (200_000,299_999,7_999),(300_000,399_999,12_000),(400_000,499_999,15_000),
           (500_000,599_999,20_000),(600_000,699_999,24_000),(700_000,799_999,26_999),
           (800_000,899_999,30_000),(900_000,999_999,35_000),(1_000_000,1_499_999,39_999),
           (1_500_000,1_999_999,59_999)]
    for a,b,v in table:
        if a<=d<=b: return v
    return 0

def _al_ok(x)->bool:
    return _norm_text(x) in {"al","debutant non diplome 90j","debutant non diplome 90 j","debutant","debutant 90j"}

def debutant_bonus_numpy(diamants: pd.Series, al: pd.Series):
    d = diamants.to_numpy()
    alv = np.vectorize(_al_ok)(al.to_numpy())
    b = np.zeros(d.shape[0], dtype=int)
    b[(alv) & ( (d>=75_000) & (d<=149_999) )]    =  500
    b[(alv) & ( (d>=150_000) & (d<=499_999) )]   = 1088
    b[(alv) & ( (d>=500_000) & (d<=2_000_000) )] = 3000
    return pd.Series(b, index=diamants.index, dtype=int), pd.Series(np.where(b>0,"Validé","Non validé"), index=diamants.index)

# --------- Tables ----------
def compute_creators_table(df: pd.DataFrame) -> pd.DataFrame:
    actif = ((df["Jours de passage en live"]>=12) & (df["Durée de live (heures)"]>=25)) | (df["Diamants"]>=150_000)
    pal2  = (df["Jours de passage en live"]>=20) & (df["Durée de live (heures)"]>=80)

    r1 = df["Diamants"].apply(palier1_reward).astype(int).to_numpy()
    r2 = df["Diamants"].apply(palier2_reward).astype(int).to_numpy()
    aff_p1 = np.where(pal2.to_numpy(), 0, r1).astype(int)
    aff_p2 = np.where(pal2.to_numpy(), r2, 0).astype(int)

    bonus_vals, bonus_flags = debutant_bonus_numpy(df["Diamants"], df["AL"])
    total = (aff_p1 + aff_p2 + bonus_vals.to_numpy()).astype(int)

    out = pd.DataFrame({
        "Nom d’utilisateur": df["Nom d’utilisateur"],
        "Groupe/Manager": df["Groupe/Manager"],
        "Agent": df["Agent"],
        "Diamants": df["Diamants"].astype(int),
        "Durée de live (heures)": df["Durée de live (heures)"].astype(int),
        "Jours de passage en live": df["Jours de passage en live"].astype(int),
        "Actif": np.where(actif,"Validé","Non validé"),
        "Palier 2": np.where(pal2,"Validé","Non validé"),
        "Récompense palier 1": aff_p1,
        "Récompense palier 2": aff_p2,
        "Bonus débutant": bonus_flags.values,
        "Montant bonus": bonus_vals.values,          # <<< ajouté
        "Récompense totale": total,
    }).sort_values(by=["Diamants","Récompense totale"], ascending=[False,False]).reset_index(drop=True)

    return out

def _agent_reward(sum_active:int)->int:
    if sum_active < 200_000: return 0
    if sum_active < 4_000_000: return round(sum_active*0.02)
    return round(sum_active*0.03)

def compute_agents_table(df: pd.DataFrame) -> pd.DataFrame:
    actif = ((df["Jours de passage en live"]>=12) & (df["Durée de live (heures)"]>=25)) | (df["Diamants"]>=150_000)
    g = df.groupby("Agent", dropna=False)
    tot   = g["Diamants"].sum().astype(int)
    act   = df.loc[actif].groupby("Agent", dropna=False)["Diamants"].sum().reindex(tot.index).fillna(0).astype(int)
    perte = (tot - act).astype(int)
    rew   = act.apply(_agent_reward).astype(int)
    return pd.DataFrame({
        "Agent": tot.index.where(tot.index!="","(non défini)"),
        "Diamants actifs": act.values,
        "Diamants totaux": tot.values,
        "Perte (diamants inactifs)": perte.values,
        "Récompense agent": rew.values
    }).sort_values(by=["Diamants actifs","Diamants totaux"], ascending=False).reset_index(drop=True)

def compute_managers_table(df: pd.DataFrame) -> pd.DataFrame:
    actif = ((df["Jours de passage en live"]>=12) & (df["Durée de live (heures)"]>=25)) | (df["Diamants"]>=150_000)
    pal3  = df["Diamants"]>=500_000
    g = df.groupby("Groupe/Manager", dropna=False)
    tot   = g["Diamants"].sum().astype(int)
    act   = df.loc[actif].groupby("Groupe/Manager", dropna=False)["Diamants"].sum().reindex(tot.index).fillna(0).astype(int)
    base  = act.apply(_agent_reward).astype(int)
    b3    = df.loc[pal3].groupby("Groupe/Manager", dropna=False)["Diamants"].count().reindex(tot.index).fillna(0).astype(int)*5000
    perte = (tot - act).astype(int)
    return pd.DataFrame({
        "Manager/Groupe": tot.index.where(tot.index!="","(non défini)"),
        "Diamants actifs": act.values,
        "Diamants totaux": tot.values,
        "Perte (diamants inactifs)": perte.values,
        "Bonus 3 (5000 x nb créateurs ≥500k)": b3.values,
        "Récompense manager (hors bonus)": base.values,
        "Récompense totale": (base+b3).values.astype(int)
    }).sort_values(by=["Diamants actifs","Diamants totaux"], ascending=False).reset_index(drop=True)
