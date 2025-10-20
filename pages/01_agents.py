import streamlit as st, pandas as pd
from utils import REQUIRED, prepare_creators, aggregate_agents

st.set_page_config(page_title="Récompenses – Agents", layout="wide")
st.title("👔 Récompenses – Agents")

up = st.file_uploader("📂 Importez votre fichier (.xlsx / .csv)", type=["xlsx","csv"], key="upload_agents")

if not up:
    st.info("Importez le même fichier export pour générer le tableau Agents.")
    st.stop()

df = pd.read_csv(up) if up.name.lower().endswith(".csv") else pd.read_excel(up)
missing = [c for c in REQUIRED if c not in df.columns]
if missing:
    st.error(f"Colonnes manquantes : {missing}")
    st.stop()

crea = prepare_creators(df)
agents = aggregate_agents(crea)
st.dataframe(agents, use_container_width=True)
st.download_button("⬇️ Télécharger (CSV)", agents.to_csv(index=False, sep=";").encode("utf-8-sig"),
                   file_name="Récompense_Agents.csv", mime="text/csv")
st.caption("Tom Consulting & Event")
