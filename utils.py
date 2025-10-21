import re, pandas as pd, numpy as np

REQUIRED = ["Diamants","Durée de LIVE","Jours de passage en LIVE valides","Statut du diplôme","Agent","Groupe"]

def to_int_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(r"[^\d]", "", regex=True), errors="coerce").fillna(0).astype(int)

def parse_hours_cell(v) -> float:
    if pd.isna(v): return 0.0
    s=str(v).lower()
    h=re.search(r"(\d+)\s*h",s); m=re.search(r"(\d+)\s*min",s); sec=re.search(r"(\d+)\s*s",s)
    hh=int(h.group(1)) if h else 0; mm=int(m.group(1)) if m else 0; ss=int(sec.group(1)) if sec else 0
    if not (h or m or sec):
        try: return float(str(v).replace(",","."))
        except: return 0.0
    return hh+mm/60+ss/3600

def reward_p1(d:int)->int:
    if 35000<=d<=74999: return 1000
    if 75000<=d<=149999: return 2500
    if 150000<=d<=199999: return 5000
    if 200000<=d<=299999: return 6000
    if 300000<=d<=399999: return 7999
    if 400000<=d<=499999: return 12000
    if 500000<=d<=599999: return 15000
    if 600000<=d<=699999: return 18000
    if 700000<=d<=799999: return 21000
    if 800000<=d<=899999: return 24000
    if 900000<=d<=999999: return 26999
    if 1_000_000<=d<=1_499_999: return 30000
    if 1_500_000<=d<=1_999_999: return 44999
    if d>=2_000_000: return int(round(d*0.04))
    return 0

def reward_p2(d:int)->int:
    if 35000<=d<=74999: return 1000
    if 75000<=d<=149999: return 2500
    if 150000<=d<=199999: return 6000
    if 200000<=d<=299999: return 7999
    if 300000<=d<=399999: return 12000
    if 400000<=d<=499999: return 15000
    if 500000<=d<=599999: return 20000
    if 600000<=d<=699999: return 24000
    if 700000<=d<=799999: return 26999
    if 800000<=d<=899999: return 30000
    if 900000<=d<=999999: return 35000
    if 1_000_000<=d<=1_499_999: return 39999
    if 1_500_000<=d<=1_999_999: return 59999
    if d>=2_000_000: return int(round(d*0.04))
    return 0

def bonus_debutant(d:int)->int:
    if 75000<=d<=149999: return 500
    if 150000<=d<=499999: return 1088
    if d>=500000: return 3000
    return 0

def pct_reward(active:int)->int:
    a=int(active)
    if a<200_000: return 0
    base_2=min(a,4_000_000)*0.02
    extra_3=max(a-4_000_000,0)*0.03
    return int(base_2+extra_3)

def detect_user_col(df: pd.DataFrame):
    norm={c:c.lower().replace("’","'").strip() for c in df.columns}
    for col,low in norm.items():
        if any(k in low for k in ["nom d'utilisateur","username","user name","pseudo","utilisateur","handle","name","nom"]):
            return col
    return None

def prepare_creators(df: pd.DataFrame) -> pd.DataFrame:
    user_col = detect_user_col(df)
    df["Diamants_num"]=to_int_series(df["Diamants"])
    df["Heures_num"]=df["Durée de LIVE"].apply(parse_hours_cell).astype(float)
    df["Jours_num"]=to_int_series(df["Jours de passage en LIVE valides"])
    is_conf=(df["Diamants_num"]>=150000)|df["Statut du diplôme"].astype(str).str.contains("non-?débutant|non-?debutant",case=False,regex=True)
    df["Type créateur"]=np.where(is_conf,"Confirmé","Débutant")
    df["Actif"]=np.where(
        (df["Diamants_num"]>=750)&(
            ((df["Type créateur"]=="Confirmé")&(df["Jours_num"]>=12)&(df["Heures_num"]>=25))|
            ((df["Type créateur"]=="Débutant")&(df["Jours_num"]>=7)&(df["Heures_num"]>=15))
        ),True,False)
    df["Palier 2"]=np.where((df["Jours_num"]>=20)&(df["Heures_num"]>=80),"Validé","Non validé")
    df["Récompense palier 1"]=np.where(df["Actif"]&(df["Palier 2"]!="Validé"),df["Diamants_num"].apply(reward_p1),0)
    df["Récompense palier 2"]=np.where(df["Actif"]&(df["Palier 2"]=="Validé"),df["Diamants_num"].apply(reward_p2),0)
    elig=df["Statut du diplôme"].astype(str).str.contains("non dipl",case=False,regex=True)|df["Statut du diplôme"].astype(str).str.contains("90",case=False)
    df["Montant bonus débutant"]=np.where(elig&(df["Type créateur"]=="Débutant"),df["Diamants_num"].apply(bonus_debutant),0)
    base=np.where(df["Récompense palier 2"]>0,df["Récompense palier 2"],df["Récompense palier 1"])
    df["Récompense totale"]=(base+df["Montant bonus débutant"]).astype(int)
    out=([user_col] if user_col else [])+[
        "Diamants","Durée de LIVE","Jours de passage en LIVE valides","Statut du diplôme","Agent","Groupe",
        "Diamants_num","Heures_num","Jours_num","Type créateur","Actif","Palier 2",
        "Récompense palier 1","Récompense palier 2","Montant bonus débutant","Récompense totale"
    ]
    return df[out].copy()

def aggregate_agents(crea: pd.DataFrame) -> pd.DataFrame:
    t=crea.copy()
    t["Diamants_actifs_crea"]=np.where(t["Actif"],t["Diamants_num"],0)
    g=t.groupby("Agent",dropna=False)
    out=g.agg(
        Creators_total=("Diamants_num","count"),
        Creators_actifs=("Actif",lambda s:int(s.sum())),
        Diamants_actifs=("Diamants_actifs_crea","sum"),
        Diamants_totaux=("Diamants_num","sum"),
        Bonus2_count=("Montant bonus débutant",lambda s:int((s==1088).sum())),
        Bonus3_count=("Montant bonus débutant",lambda s:int((s==3000).sum())),
    ).reset_index()
    out["Perte_estimée"]=out["Diamants_totaux"]-out["Diamants_actifs"]
    out["Récompense_%"]=out["Diamants_actifs"].apply(pct_reward).astype(int)
    out["Bonus_agent"]=(out["Bonus2_count"]*1000+out["Bonus3_count"]*15000).astype(int)
    out["Récompense_finale"]=np.where(out["Diamants_actifs"]>=200_000,out["Récompense_%"]+out["Bonus_agent"],0).astype(int)
    return out.sort_values(["Diamants_actifs","Diamants_totaux"],ascending=False)

def aggregate_managers(crea: pd.DataFrame) -> pd.DataFrame:
    t=crea.copy()
    t["Diamants_actifs_crea"]=np.where(t["Actif"],t["Diamants_num"],0)
    g=t.groupby("Groupe",dropna=False)
    out=g.agg(
        Creators_total=("Diamants_num","count"),
        Creators_actifs=("Actif",lambda s:int(s.sum())),
        Diamants_actifs=("Diamants_actifs_crea","sum"),
        Diamants_totaux=("Diamants_num","sum"),
        Bonus3_count=("Montant bonus débutant",lambda s:int((s==3000).sum())),
    ).reset_index()
    out["Perte_estimée"]=out["Diamants_totaux"]-out["Diamants_actifs"]
    out["Récompense_%"]=out["Diamants_actifs"].apply(pct_reward).astype(int)
    out["Bonus_manager"]=(out["Bonus3_count"]*5000).astype(int)
    out["Récompense_finale"]=np.where(out["Diamants_actifs"]>=200_000,out["Récompense_%"]+out["Bonus_manager"],0).astype(int)
    return out.sort_values(["Diamants_actifs","Diamants_totaux"],ascending=False)
import pandas as pd

def compute_creators_table(df_source: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule les récompenses créateurs avec les paliers, bonus et totaux.
    """

    df = df_source.copy()

    # Vérification des colonnes minimales
    required_cols = ["Nombre de live", "Durée totale (heures)", "Diamants générés"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Colonne manquante dans le fichier importé : '{col}'")

    # Palier 1
    df["Palier 1 atteint"] = df["Diamants générés"] >= 50000

    # Palier 2
    df["Palier 2 atteint"] = df["Diamants générés"] >= 150000

    # Récompense de base selon le palier
    df["Récompense (base)"] = 0
    df.loc[df["Palier 1 atteint"], "Récompense (base)"] = 1000
    df.loc[df["Palier 2 atteint"], "Récompense (base)"] = 3000

    # Bonus si plus de 10 lives
    df["Bonus Live"] = 0
    df.loc[df["Nombre de live"] >= 10, "Bonus Live"] = 500

    # Bonus durée totale
    df["Bonus Temps"] = 0
    df.loc[df["Durée totale (heures)"] >= 20, "Bonus Temps"] = 500

    # Total final
    df["Total Récompense"] = df["Récompense (base)"] + df["Bonus Live"] + df["Bonus Temps"]

    # Statut
    df["Statut"] = df["Total Récompense"].apply(lambda x: "Validé" if x > 0 else "Non validé")

    return df

