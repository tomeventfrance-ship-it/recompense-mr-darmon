import streamlit as st
import pandas as pd
from utils import REQUIRED, prepare_creators

st.set_page_config(page_title="Récompenses – Créateurs", layout="wide")
st.title("💎 Récompenses – Créateurs")

uploaded = st.file_uploader("📂 Importez votre fichier (.xlsx / .csv)", type=["xlsx","csv"], key="upload_crea")

if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        st.error(f"Colonnes manquantes: {missing}")
    else:
        crea = prepare_creators(df)
        st.dataframe(crea, use_container_width=True)
        st.download_button("⬇️ Télécharger (CSV)", crea.to_csv(index=False).encode("utf-8"),
                           file_name="Récompense_Créateurs.csv", mime="text/csv")
else:
    st.info("Importez un fichier pour calculer les récompenses.")
st.caption("Tom Consulting & Event")
