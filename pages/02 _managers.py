import streamlit as st, pandas as pd
from utils import REQUIRED, prepare_creators, aggregate_managers

st.set_page_config(page_title="Récompenses – Managers", layout="wide")
st.title("🏆 Récompenses – Managers")

up = st.file_uploader("📂 Importez votre fichier (.xlsx / .csv)", type=["xlsx","csv"], key="upload_managers")

if not up:
    st.info("Importez le même fichier export pour générer le tableau Managers.")
    st.stop()

df = pd.read_csv(up) if up.name.lower().endswith(".csv") else pd.read_excel(up)
missing = [c for c in REQUIRED if c not in df.columns]
if missing:
    st.error(f"Colonnes manquantes : {missing}")
    st.stop()

crea = prepare_creators(df)
man = aggregate_managers(crea)
st.dataframe(man, use_container_width=True)
st.download_button("⬇️ Télécharger (CSV)", man.to_csv(index=False, sep=";").encode("utf-8-sig"),
                   file_name="Récompense_Managers.csv", mime="text/csv")
st.caption("Tom Consulting & Event")
