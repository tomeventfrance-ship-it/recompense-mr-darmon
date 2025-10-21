# utils.py — utilise EXCLUSIVEMENT les colonnes spécifiées par Tom

import io, re
import pandas as pd
import numpy as np

# --------- noms exacts attendus (avec accents) ----------
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

# Petit normaliseur robuste (si un export change légèrement l’en-tête)
def _norm(s: str) -> str:
    s = str(s)
    s = s.encode("ascii","ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

# correspondances de secours -> en-têtes EXACTS ci-dessus
BACKUPS = {
    "periode":   {"periode des donnees","periode"},
    "user":      {"nom d utilisateur du de la createur trice","nom d utilisateur","username"},
    "manager":   {"groupe","manager"},
    "agent":     {"agent","agent e"},
    "relation":  {"date d etablissement de la relation","date relation"},
    "diamants":  {"diamants","diamonds"},
    "heures":    {"duree de live","duree live","heures de live","temps de live h","duree de live heures"},
    "jours":     {"jours de passage en live valides","jours de live","nb jours live"},
    "al":        {"statut du diplome","al","debutant non diplome 90j"},
}

# ---------- Lecture & standardisation (ne garde QUE les colonnes ci-dessus) ----------
def _pick_strict(df: pd.DataFrame, key: str) -> str:
    exact = EXPECTED[key]
    if exact in df.columns: return exact
    # fallback souple si l’export renomme légèrement
    want = BACKUPS.get(key, set())
    m = {_norm(c): c for c in map(str, df.columns)}
    for w in want:
        if w in m: return m[w]
    raise ValueError(f"Colonne manquante: « {exact} »")

def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = list(map(str, df.columns))
    df = df.reset_index(drop=True)

    # Sélection stricte des seules colonnes requises
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
    for n in ["Diamants","Durée de live (heures)","Jours de passage en live"]:
        out[n] = pd.to_numeric(out[n], errors="coerce").fillna(0).astype(int)
    for n in ["Nom d’utilisateur","Groupe/Manager","Agent","AL","Période des données","Date relation"]:
        out[n] = out[n].astype(str).fillna("").str.strip()

    # Drapeaux vides propres
    out["Nom d’utilisateur"] = out["Nom d’utilisateur"].replace({"":"(non fourni)"})

    return out

def load_df(file_like) -> pd.DataFrame:
    # accepte DataFrame, Bytes, fichiers streamlit
    if isinstance(file_like, pd.DataFrame):
        return _standardize(file_like)
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
        try:
            raw = pd.read_csv(file_like)
        except Exception:
            file_like.seek(0) if hasattr(file_like,"seek") else None
            raw = pd.read_excel(file_like)
    return _standardize(raw)

# ---------- Barèmes & règles ----------
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

def _norm(s):  # réutilisé pour AL/flags
    s = str(s)
    s = s.encode("ascii","ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def debutant_bonus_numpy(diamants: pd.Series, al: pd.Series):
    d = diamants.to_numpy()
    al_ok = np.vectorize(lambda x: _norm(x) in {
        "al","debutant non diplome 90j","debutant non diplome 90 j","debutant","debutant 90j"
    })(al.to_numpy())
    b = np.zeros(d.shape[0], dtype=int)
    b[(al_ok) & ( (d>=75_000) & (d<=149_999) )]    =  500
    b[(al_ok) & ( (d>=150_000) & (d<=499_999) )]   = 1088
    b[(al_ok) & ( (d>=500_000) & (d<=2_000_000) )] = 3000
    return pd.Series(b, index=diamants.index, dtype=int), pd.Series(np.where(b>0,"Validé","Non validé"), index=diamants.index)

# ---------- Créateurs ----------
def compute_creators_table(df: pd.DataFrame) -> pd.DataFrame:
    # conditions d’activité & palier 2
    actif = ((df["Jours de passage en live"]>=12) & (df["Durée de live (heures)"]>=25)) | (df["Diamants"]>=150_000)
    pal2  = (df["Jours de passage en live"]>=20) & (df["Durée de live (heures)"]>=80)

    r1 = df["Diamants"].apply(palier1_reward).astype(int).to_numpy()
    r2 = df["Diamants"].apply(palier2_reward).astype(int).to_numpy()
    aff_p1 = np.where(pal2.to_numpy(), 0, r1).astype(int)  # n’affiche pas P1 si P2 validé
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
        "Récompense totale": total,
    }).sort_values(by=["Diamants","Récompense totale"], ascending=[False,False]).reset_index(drop=True)

    return out

# ---------- Agents ----------
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

# ---------- Managers ----------
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
