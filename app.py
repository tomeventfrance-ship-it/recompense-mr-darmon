# app.py  (mode safe: un ou plusieurs fichiers, pas de cache, lecture directe)
import pandas as pd
import streamlit as st
from utils import (
    compute_creators_table,
    compute_agents_table_from_creators,
    compute_managers_table_from_creators,
)

st.set_page_config(page_title="Récompenses – Créateurs / Agents / Managers", page_icon="💎", layout="wide")
st.title("💎 Récompenses – Créateurs")

st.caption("Importez un ou plusieurs .xlsx/.csv (mois courant + historiques). Aucune mémorisation en session pour éviter les erreurs de type.")

def read_any(uploaded_file):
    """Lecture directe depuis l'UploadedFile (évite tout .read() / .getvalue())."""
    name = uploaded_file.name.lower()
    uploaded_file.seek(0)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file, engine="openpyxl")
    elif name.endswith(".csv"):
        try:
            return pd.read_csv(uploaded_file)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding="latin-1")
    else:
        raise ValueError(f"Extension non supportée: {uploaded_file.name}")

def concat_clean(dfs):
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True).drop_duplicates()

uploaded = st.file_uploader("Drag and drop files here", type=["xlsx", "xls", "csv"], accept_multiple_files=True)

if not uploaded:
    st.info("Importez au moins un fichier pour démarrer.")
    st.stop()

# Lire tous les fichiers importés
dfs = []
try:
    for f in uploaded:
        dfs.append(read_any(f))
    df_raw = concat_clean(dfs)
except Exception as e:
    st.error(f"Erreur de lecture : {e}")
    st.stop()

# Calculs
try:
    crea = compute_creators_table(df_raw)
    agents = compute_agents_table_from_creators(crea)
    managers = compute_managers_table_from_creators(crea)
except Exception as e:
    st.error(f"Erreur lors du traitement des données : {e}")
    st.stop()

# UI
tab1, tab2, tab3 = st.tabs(["Créateurs", "Agents", "Managers"])

with tab1:
    st.subheader("Créateurs")
    st.dataframe(crea, use_container_width=True, height=520)
    st.download_button("⬇️ CSV Créateurs", crea.to_csv(index=False, encoding="utf-8-sig"), "Recompense_Createurs.csv", "text/csv")

with tab2:
    st.subheader("Agents")
    st.dataframe(agents, use_container_width=True, height=520)
    st.download_button("⬇️ CSV Agents", agents.to_csv(index=False, encoding="utf-8-sig"), "Recompense_Agents.csv", "text/csv")

with tab3:
    st.subheader("Managers")
    st.dataframe(managers, use_container_width=True, height=520)
    st.download_button("⬇️ CSV Managers", managers.to_csv(index=False, encoding="utf-8-sig"), "Recompense_Managers.csv", "text/csv")
