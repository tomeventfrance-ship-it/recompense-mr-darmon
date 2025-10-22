# app.py — Récompenses Créateurs / Agents / Managers
import pandas as pd
import streamlit as st

# ---- Fonctions de calcul venant de utils.py (déjà existantes chez toi) ----
# Elles doivent être présentes dans utils.py : load_df, compute_creators_table,
# compute_agents_table, compute_managers_table
from utils import load_df, compute_creators_table, compute_agents_table, compute_managers_table

# ---- Patch anti-bug concat (tuple -> DataFrame) ---------------------------
def _ensure_df(x):
    """Si load_df renvoie (df, ...), on récupère le df ; sinon on renvoie tel quel."""
    return x[0] if isinstance(x, tuple) else x


# ======================== UI ===============================================
st.set_page_config(page_title="Récompenses – Créateurs / Agents / Managers",
                   layout="wide", page_icon="💎")

st.title("💎 Récompenses – Créateurs / Agents / Managers")

with st.expander("Importer votre/vos fichier(s) (.xlsx / .csv)", expanded=True):
    uploaded_files = st.file_uploader(
        "Drag and drop files here",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
        help="Limite 200MB par fichier • XLSX, XLS, CSV"
    )

    history_files = st.file_uploader(
        "Historique (optionnel) – bonus débutant déjà payés & confirmé 150k",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True
    )

# ====== Construction DataFrames robustes (corrige l'erreur 'tuple' concat) ==
def _concat_files(files):
    if not files:
        return None
    dfs = []
    for f in files:
        try:
            df = _ensure_df(load_df(f))
            dfs.append(df)
        except Exception as e:
            st.error(f"Erreur de lecture : {e}")
            return None
    try:
        return pd.concat(dfs, ignore_index=True) if dfs else None
    except Exception as e:
        st.error(f"Erreur de concaténation : {e}")
        return None

df_current = _concat_files(uploaded_files)
df_history = _concat_files(history_files)

# ====== Aperçu colonnes source =============================================
col1, col2 = st.columns([1, 1])
with col1:
    if st.toggle("Afficher un aperçu des colonnes source", value=False):
        if df_current is not None:
            st.write("Colonnes détectées (fichier(s) courant(s)) :", list(df_current.columns))
        if df_history is not None:
            st.write("Colonnes détectées (historique) :", list(df_history.columns))

with col2:
    st.toggle("Voir un échantillon brut", value=False, key="raw_toggle")

if st.session_state.get("raw_toggle") and df_current is not None:
    st.dataframe(df_current.head(20), use_container_width=True)

st.markdown("---")

# ======================== Créateurs ========================================
st.header("Créateurs")
if df_current is None:
    st.info("Importez au moins un fichier pour démarrer.")
else:
    try:
        creators_table = compute_creators_table(df_current, df_history)
        st.dataframe(creators_table, use_container_width=True)
        st.download_button(
            "⬇️ Télécharger le tableau créateurs (CSV)",
            data=creators_table.to_csv(index=False).encode("utf-8"),
            file_name="recompenses_createurs.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"Erreur dans compute_creators_table(utils.py) : {e}")

st.markdown("---")

# ======================== Agents ===========================================
st.header("Agents")
if df_current is not None:
    try:
        agents_table = compute_agents_table(df_current, df_history)
        st.dataframe(agents_table, use_container_width=True)
        st.download_button(
            "⬇️ Télécharger le tableau agents (CSV)",
            data=agents_table.to_csv(index=False).encode("utf-8"),
            file_name="recompenses_agents.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"Erreur dans compute_agents_table(utils.py) : {e}")

st.markdown("---")

# ======================== Managers =========================================
st.header("Managers")
if df_current is not None:
    try:
        managers_table = compute_managers_table(df_current, df_history)
        st.dataframe(managers_table, use_container_width=True)
        st.download_button(
            "⬇️ Télécharger le tableau managers (CSV)",
            data=managers_table.to_csv(index=False).encode("utf-8"),
            file_name="recompenses_managers.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"Erreur dans compute_managers_table(utils.py) : {e}")

# ======================== Notes ============================================
st.caption("Importer 1..N mois (courant + historiques). Les règles bonus/paliers sont gérées côté utils.py.")
