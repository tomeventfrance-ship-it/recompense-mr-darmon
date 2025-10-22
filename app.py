# app.py
# ----------------------------------------
# Application Streamlit – Récompenses Tom Consulting & Event
# Onglets : Créateurs / Agents / Managers
# Prend 1..N fichiers (.xlsx/.csv), fusionne, applique l’historique (via utils),
# calcule les tableaux et propose le téléchargement.
# ----------------------------------------

import io
import pandas as pd
import streamlit as st

from utils import (
    load_df,
    compute_creators_table,
    compute_agents_table_from_creators,
    compute_managers_table_from_creators,
    CANON
)

# -----------------------------
# CONFIG UI
# -----------------------------
st.set_page_config(
    page_title="Récompenses – Créateurs / Agents / Managers",
    page_icon="💎",
    layout="wide",
)

st.title("💎 Récompenses – Créateurs")

st.caption(
    "Calcul automatique des récompenses (activité + paliers + bonus débutant) "
    "et répartition Agents / Managers."
)

# -----------------------------
# UPLOAD
# -----------------------------
st.subheader("Importez votre/vos fichier(s) (.xlsx / .csv)")
uploaded_files = st.file_uploader(
    "Glissez et déposez ici",
    type=["xlsx", "csv"],
    accept_multiple_files=True
)

if "last_files_payload" not in st.session_state:
    st.session_state.last_files_payload = None

use_last = False
c1, c2 = st.columns([1, 1])
with c1:
    if st.button("🧠 Utiliser les fichiers mémorisés (si dispo)"):
        if st.session_state.last_files_payload is not None:
            use_last = True
        else:
            st.info("Aucun jeu de fichiers mémorisé dans cette session.")
with c2:
    if st.button("🗑️ Vider les fichiers de la session"):
        st.session_state.last_files_payload = None
        st.success("Mémoire de fichiers vidée.")

# -----------------------------
# LECTURE + FUSION
# -----------------------------
def _concat_loaded(list_dfs: list[pd.DataFrame]) -> pd.DataFrame:
    if not list_dfs:
        return pd.DataFrame()
    df = pd.concat(list_dfs, ignore_index=True)
    df = df.drop_duplicates()
    return df

df_raw = pd.DataFrame()

try:
    if uploaded_files and len(uploaded_files) > 0:
        loaded = []
        for f in uploaded_files:
            # ✅ Correction ici : on lit les bytes
            data = f.read()
            bio = io.BytesIO(data)
            df = load_df(bio)
            loaded.append(df)
        df_raw = _concat_loaded(loaded)
        st.session_state.last_files_payload = [f.name for f in uploaded_files]
        st.success(f"Fichier(s) importé(s) avec succès : {', '.join([f.name for f in uploaded_files])}")
    elif use_last and st.session_state.last_files_payload:
        st.info("Réutilisation des fichiers mémorisés.")
except Exception as e:
    st.error(f"Erreur de lecture : {e}")

if df_raw.empty:
    st.info("Importez au moins un fichier pour démarrer.")
    st.stop()

# -----------------------------
# CALCULS
# -----------------------------
try:
    creators_df = compute_creators_table(df_raw)
    agents_df = compute_agents_table_from_creators(creators_df)
    managers_df = compute_managers_table_from_creators(creators_df)
except Exception as e:
    st.error(f"Erreur lors du traitement des données : {e}")
    st.stop()

# -----------------------------
# AFFICHAGE
# -----------------------------
tab_crea, tab_agents, tab_man = st.tabs(["Créateurs", "Agents", "Managers"])

def _download_button(df: pd.DataFrame, label: str, filename: str, key: str):
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    st.download_button(
        label=label,
        data=buf.getvalue().encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        key=key
    )

with tab_crea:
    st.subheader("Tableau Créateurs")
    st.dataframe(creators_df, use_container_width=True, height=520)
    _download_button(creators_df, "⬇️ Télécharger (CSV) – Créateurs", "Recompense_Createurs.csv", "dl_crea")

with tab_agents:
    st.subheader("Tableau Agents")
    st.dataframe(agents_df, use_container_width=True, height=520)
    _download_button(agents_df, "⬇️ Télécharger (CSV) – Agents", "Recompense_Agents.csv", "dl_agents")

with tab_man:
    st.subheader("Tableau Managers")
    st.dataframe(managers_df, use_container_width=True, height=520)
    _download_button(managers_df, "⬇️ Télécharger (CSV) – Managers", "Recompense_Managers.csv", "dl_man")

# -----------------------------
# INFO COLONNES MAPPÉES
# -----------------------------
with st.expander("ℹ️ Colonnes attendues (noms canoniques)"):
    st.write(pd.DataFrame([CANON]).T.rename(columns={0: "Nom source → Nom canonique"}))
