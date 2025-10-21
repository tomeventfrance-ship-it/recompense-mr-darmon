# app.py — option “remplacer” + purge session + tables

import streamlit as st
import pandas as pd
from utils import load_df, compute_creators_table, compute_agents_table, compute_managers_table

st.set_page_config(page_title="Récompenses", layout="wide")
st.title("💎 Récompenses – Créateurs")

# Mémoire locale de session
if "stored_dfs" not in st.session_state:
    st.session_state.stored_dfs = []

with st.sidebar:
    st.header("Navigation")
    onglet = st.radio("Section", ["Créateurs","Agents","Managers"], index=0)
    st.divider()
    replace = st.checkbox("Remplacer les données précédentes", value=True,
                          help="Si coché: seuls les fichiers importés maintenant seront utilisés.")
    if st.button("🗑️ Vider les fichiers de la session"):
        st.session_state.stored_dfs = []
        st.success("Session vidée.")

uploaded = st.file_uploader("Importez votre/vos fichier(s) (.xlsx / .csv)", type=["xlsx","xls","csv"], accept_multiple_files=True)
if uploaded:
    try:
        dfs = [load_df(f) for f in uploaded]
        if replace:
            st.session_state.stored_dfs = dfs
        else:
            st.session_state.stored_dfs.extend(dfs)
        st.success(f"Fichier(s) importé(s) avec succès. Source(s) en mémoire: {len(st.session_state.stored_dfs)}")
    except Exception as e:
        st.error(f"Erreur de lecture : {e}")

if not st.session_state.stored_dfs:
    st.info("Importez un fichier pour démarrer.")
    st.stop()

# Concat sans doublonner exact (facultatif simple)
base = pd.concat(st.session_state.stored_dfs, ignore_index=True)

if onglet == "Créateurs":
    table = compute_creators_table(base)
    st.subheader("Table Créateurs")
    st.dataframe(table, use_container_width=True)
    st.download_button("⬇️ Télécharger (CSV)", table.to_csv(index=False).encode("utf-8"), "Recompense_Creators.csv", "text/csv")

elif onglet == "Agents":
    table = compute_agents_table(base)
    st.subheader("Table Agents")
    st.dataframe(table, use_container_width=True)
    st.download_button("⬇️ Télécharger (CSV)", table.to_csv(index=False).encode("utf-8"), "Recompense_Agents.csv", "text/csv")

else:
    table = compute_managers_table(base)
    st.subheader("Table Managers")
    st.dataframe(table, use_container_width=True)
    st.download_button("⬇️ Télécharger (CSV)", table.to_csv(index=False).encode("utf-8"), "Recompense_Managers.csv", "text/csv")
