# app.py — UI + orchestration
import pandas as pd
import streamlit as st
from utils import (
    load_df,
    compute_creators_table,
    compute_agents_table,
    compute_managers_table,
)

def _ensure_df(x):
    return x[0] if isinstance(x, tuple) else x

st.set_page_config(page_title="Récompenses – Créateurs / Agents / Managers",
                   layout="wide", page_icon="💎")
st.title("💎 Récompenses – Créateurs / Agents / Managers")

with st.expander("Importer votre/vos fichier(s) (.xlsx / .csv)", expanded=True):
    uploaded_files = st.file_uploader("Drag and drop files here",
                                      type=["xlsx","xls","csv"], accept_multiple_files=True)
    history_files = st.file_uploader("Historique (optionnel) – bonus débutant déjà payés & confirmé 150k",
                                     type=["xlsx","xls","csv"], accept_multiple_files=True)

def _concat(files):
    if not files: return None
    dfs = []
    for f in files:
        df = _ensure_df(load_df(f))
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else None

df_current = _concat(uploaded_files)
df_history = _concat(history_files)

# helpers d’aperçu
col1, col2 = st.columns([1,1])
with col1:
    if st.toggle("Afficher un aperçu des colonnes source", value=False):
        if df_current is not None:
            st.write("Colonnes (courant) :", list(df_current.columns))
        if df_history is not None:
            st.write("Colonnes (historique) :", list(df_history.columns))
with col2:
    st.toggle("Voir un échantillon brut", value=False, key="raw")

if st.session_state.get("raw") and df_current is not None:
    st.dataframe(df_current.head(20), use_container_width=True)

st.markdown("---")
st.header("Créateurs")

creators_table = None
if df_current is None:
    st.info("Importez au moins un fichier pour démarrer.")
else:
    try:
        creators_table = compute_creators_table(df_current, df_history)
        st.dataframe(creators_table, use_container_width=True)
        st.download_button(
            "⬇️ Télécharger le tableau créateurs (CSV)",
            creators_table.to_csv(index=False).encode("utf-8"),
            "recompenses_createurs.csv",
            "text/csv"
        )
    except Exception as e:
        st.error(f"Erreur calcul créateurs : {e}")

st.markdown("---")
st.header("Agents")
if creators_table is not None:
    try:
        agents_table = compute_agents_table(None, None, creators_table=creators_table)
        st.dataframe(agents_table, use_container_width=True)
        st.download_button(
            "⬇️ Télécharger le tableau agents (CSV)",
            agents_table.to_csv(index=False).encode("utf-8"),
            "recompenses_agents.csv",
            "text/csv"
        )
    except Exception as e:
        st.error(f"Erreur calcul agents : {e}")

st.markdown("---")
st.header("Managers")
if creators_table is not None:
    try:
        managers_table = compute_managers_table(None, None, creators_table=creators_table)
        st.dataframe(managers_table, use_container_width=True)
        st.download_button(
            "⬇️ Télécharger le tableau managers (CSV)",
            managers_table.to_csv(index=False).encode("utf-8"),
            "recompenses_managers.csv",
            "text/csv"
        )
    except Exception as e:
        st.error(f"Erreur calcul managers : {e}")

st.caption("Les calculs Agents/Managers sont dérivés exclusivement du tableau Créateurs.")
