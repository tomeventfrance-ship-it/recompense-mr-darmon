import streamlit as st
import pandas as pd
from utils import REQUIRED, prepare_creators, aggregate_agents

st.set_page_config(page_title="Récompenses – Agents", layout="wide")
st.title("👔 Récompenses – Agents")

uploaded = st.file_uploader("📂 Importez votre fichier (.xlsx / .csv)", type=["xlsx","csv"], key="upload_agents")

if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        st.error(f"Colonnes manquantes: {missing}")
    else:
        crea = prepare_creators(df)
        agents = aggregate_agents(crea)
        st.dataframe(agents, use_container_width=True)
        st.download_button("⬇️ Télécharger (CSV)", agents.to_csv(index=False, sep=";").encode("utf-8-sig"),
                           file_name="Récompense_Agents.csv", mime="text/csv")
else:
    st.info("Importez le même fichier export pour générer le tableau Agents.")
st.caption("Tom Consulting & Event")

