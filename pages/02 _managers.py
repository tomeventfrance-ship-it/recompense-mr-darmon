import streamlit as st
import pandas as pd
from utils import REQUIRED, prepare_creators, aggregate_managers

st.set_page_config(page_title="Récompenses – Managers", layout="wide")
st.title("🏆 Récompenses – Managers")

uploaded = st.file_uploader("📂 Importez votre fichier (.xlsx / .csv)", type=["xlsx","csv"], key="upload_managers")

if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        st.error(f"Colonnes manquantes: {missing}")
    else:
        crea = prepare_creators(df)
        managers = aggregate_managers(crea)
        st.dataframe(managers, use_container_width=True)
        st.download_button("⬇️ Télécharger (CSV)", managers.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           file_name="Récompense_Managers.csv", mime="text/csv")
else:
    st.info("Importez le même fichier export pour générer le tableau Managers.")
st.caption("Tom Consulting & Event")

