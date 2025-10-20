import re
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Logiciel Récompense - Tom Consulting & Event", layout="wide")
st.title("💎 Logiciel Récompense - Tom Consulting & Event")

# ---------- helpers ----------
def to_int_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(r"[^\d]", "", regex=True), errors="coerce").fillna(0).astype(int)

def parse_hours_cell(v) -> float:
    if pd.isna(v): return 0.0
    s = str(v).lower()
    h = re.search(r"(\d+)\s*h", s)
    m = re.search(r"(\d+)\s*min", s)
    sec = re.search(r"(\d+)\s*s", s)
    hh = int(h.group(1)) if h else 0
    mm = int(m.group(1)) if m else 0
    ss = int(sec.group(1)) if sec else 0
    # gère aussi un simple nombre (ex: "23.5")
    if not (h or m or sec):
        try: return float(str(v).replace(",", "."))
        except: return 0.0
    return hh + mm/60 + ss/3600

def reward_p1(d):
    d=int(d)
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

def reward_p2(d):
    d=int(d)
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

def bonus_debutant(d):
    d=int(d)
    if 75000<=d<=149999: return 500
    if 150000<=d<=499999: return 1088
    if d>=500000: return 3000
    return 0

# ---------- UI ----------
uploaded = st.file_uploader("📂 Importez votre fichier (.xlsx /.csv)", type=["xlsx","csv"])
if not uploaded:
    st.info("Importez votre fichier pour démarrer les calculs.")
    st.stop()

# lecture
if uploaded.name.lower().endswith(".csv"):
    df = pd.read_csv(uploaded)
else:
    df = pd.read_excel(uploaded)

required = ["Diamants","Durée de LIVE","Jours de passage en LIVE valides","Statut du diplôme","Agent","Groupe"]
missing = [c for c in required if c not in df.columns]
if missing:
    st.error(f"Colonnes manquantes: {missing}")
    st.stop()

# conversions robustes
df["Diamants_num"] = to_int_series(df["Diamants"])
df["Heures_num"] = df["Durée de LIVE"].apply(parse_hours_cell).astype(float)
df["Jours_num"] = to_int_series(df["Jours de passage en LIVE valides"])

# statut débutant/confirmé
is_confirmed = (df["Diamants_num"] >= 150000) | (df["Statut du diplôme"].astype(str).str.contains("non-?débutant|non-?debutant", case=False, regex=True))
df["Type créateur"] = np.where(is_confirmed, "Confirmé", "Débutant")

# actif
df["Actif"] = np.where(
    (df["Diamants_num"]>=750) &
    (
        ((df["Type créateur"]=="Confirmé") & (df["Jours_num"]>=12) & (df["Heures_num"]>=25))
        | ((df["Type créateur"]=="Débutant") & (df["Jours_num"]>=7) & (df["Heures_num"]>=15))
    ),
    True, False
)

# palier 2 (20j/80h)
df["Palier 2"] = np.where((df["Jours_num"]>=20) & (df["Heures_num"]>=80), "Validé", "Non validé")

# récompenses créateurs
df["Récompense palier 1"] = np.where(df["Actif"] & (df["Palier 2"]!="Validé"), df["Diamants_num"].apply(reward_p1), 0)
df["Récompense palier 2"] = np.where(df["Actif"] & (df["Palier 2"]=="Validé"), df["Diamants_num"].apply(reward_p2), 0)

# bonus débutant (une seule tranche)
is_eligible_bonus = df["Statut du diplôme"].astype(str).str.contains("non dipl", case=False, regex=True) | df["Statut du diplôme"].astype(str).str.contains("90", case=False)
df["Montant bonus débutant"] = np.where(is_eligible_bonus & (df["Type créateur"]=="Débutant"),
                                       df["Diamants_num"].apply(bonus_debutant), 0)

base = np.where(df["Récompense palier 2"]>0, df["Récompense palier 2"], df["Récompense palier 1"])
df["Récompense totale"] = (base + df["Montant bonus débutant"]).astype(int)

# affichage
out_cols = [
    "Diamants","Durée de LIVE","Jours de passage en LIVE valides","Statut du diplôme","Agent","Groupe",
    "Diamants_num","Heures_num","Jours_num","Type créateur","Actif","Palier 2",
    "Récompense palier 1","Récompense palier 2","Montant bonus débutant","Récompense totale"
]
st.success("✅ Fichier importé avec succès — calculs effectués.")
st.dataframe(df[out_cols], use_container_width=True)

# export
st.download_button("⬇️ Télécharger (CSV)", df[out_cols].to_csv(index=False).encode("utf-8"), "Recompense_Creators.csv", "text/csv")
