import streamlit as st
import pandas as pd
from utils import (
    normalize_source, ensure_df,
    compute_creators_table, compute_agents_table, compute_managers_table
)

st.set_page_config(page_title="Récompenses – Créateurs / Agents / Managers", layout="wide")
st.title("💎 Récompenses – Créateurs / Agents / Managers")

uploaded_files = st.file_uploader(
    "Importez votre/vos fichier(s) (.xlsx / .csv)", type=["xlsx","xls","csv"], accept_multiple_files=True
)
history_files = st.file_uploader(
    "Historique (optionnel) – bonus débutant déjà payés & confirmé 150k",
    type=["xlsx","xls","csv"], accept_multiple_files=True
)

# Lecture fichiers (toujours robustes → DataFrame)
def load_df(file):
    if file is None: return pd.DataFrame()
    if file.name.lower().endswith((".xlsx",".xls")):
        return pd.read_excel(file)
    return pd.read_csv(file, sep=None, engine="python")

dfs = [normalize_source(ensure_df(load_df(f))) for f in (uploaded_files or [])]
df_current = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

hist_dfs = [normalize_source(ensure_df(load_df(f))) for f in (history_files or [])]
df_history = pd.concat(hist_dfs, ignore_index=True) if hist_dfs else pd.DataFrame()

if not df_current.empty:
    st.success(f"Fichier(s) importé(s) : {len(uploaded_files)} • Lignes totales : {len(df_current)}")
    with st.expander("Afficher un aperçu des colonnes source"):
        st.dataframe(df_current.head(20), use_container_width=True)

    st.subheader("Créateurs")
    try:
        crea = compute_creators_table(df_current, df_history)
        st.dataframe(crea, use_container_width=True, height=500)
        st.download_button("📦 Export CSV – Créateurs", crea.to_csv(index=False).encode("utf-8"), "creators.csv", "text/csv")
    except Exception as e:
        st.error(f"Erreur créateurs : {e}")

    st.subheader("Agents")
    try:
        agents = compute_agents_table(df_current, df_history)
        st.dataframe(agents, use_container_width=True, height=400)
        st.download_button("📦 Export CSV – Agents", agents.to_csv(index=False).encode("utf-8"), "agents.csv", "text/csv")
    except Exception as e:
        st.error(f"Erreur agents : {e}")

    st.subheader("Managers")
    try:
        managers = compute_managers_table(df_current, df_history)
        st.dataframe(managers, use_container_width=True, height=400)
        st.download_button("📦 Export CSV – Managers", managers.to_csv(index=False).encode("utf-8"), "managers.csv", "text/csv")
    except Exception as e:
        st.error(f"Erreur managers : {e}")
else:
    st.info("Importez au moins un fichier pour démarrer.")
