import io
import pandas as pd
import streamlit as st
from utils import (
    load_df, normalize_columns, compute_creators_table,
    compute_agents_table_from_creators, compute_managers_table_from_creators,
)

st.set_page_config(page_title="Récompenses – Créateurs", layout="wide")

st.title("💎 Récompenses – Créateurs")
st.caption("Calcul automatique des récompenses pour les créateurs (activité + paliers + bonus débutant).")

# -------- Upload --------
uploaded_files = st.file_uploader(
    "Importez votre/vos fichier(s) (.xlsx / .csv)",
    type=["xlsx", "csv"], accept_multiple_files=True
)

# Mémoire de session : on garde le dernier DF consolidé + l’historique brut non cumulé
if "raw_files" not in st.session_state:
    st.session_state.raw_files = []     # liste de (name, bytes)
if "crea_df" not in st.session_state:
    st.session_state.crea_df = None
if "crea_table" not in st.session_state:
    st.session_state.crea_table = None

col_l, col_r = st.columns([1,1])
with col_l:
    if st.button("🧹 Vider les fichiers de la session"):
        st.session_state.raw_files = []
        st.session_state.crea_df = None
        st.session_state.crea_table = None
        st.success("Session vidée.")
        st.stop()

# Empile les fichiers ajoutés cette fois-ci dans la mémoire
if uploaded_files:
    for f in uploaded_files:
        st.session_state.raw_files.append((f.name, f.getvalue()))
    st.success(f"Fichier(s) importé(s) avec succès.")

# Si on a des fichiers mémorisés, on construit le DF source courant
if st.session_state.raw_files:
    # Charge puis concatène tous les fichiers importés (mois différents autorisés)
    dfs = []
    for name, data in st.session_state.raw_files:
        try:
            df = load_df(io.BytesIO(data), name)
            df = normalize_columns(df)  # met les colonnes aux noms canoniques
            dfs.append(df)
        except Exception as e:
            st.error(f"Erreur de lecture ({name}) : {e}")
            st.stop()

    if not dfs:
        st.info("Aucun fichier exploitable.")
        st.stop()

    # On recolle tout puis on laisse la logique de calcul décider de l'historique
    full_df = pd.concat(dfs, ignore_index=True)
    st.session_state.crea_df = full_df

    # --- Calcul table Créateurs
    try:
        crea_table = compute_creators_table(full_df)
        st.session_state.crea_table = crea_table
    except Exception as e:
        st.error(f"Erreur de traitement : {e}")
        st.stop()

    st.success("✅ Calcul terminé.")
    st.dataframe(crea_table, use_container_width=True)

    # Téléchargement CSV
    @st.cache_data
    def _to_csv(df: pd.DataFrame) -> bytes:
        return df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "⬇️ Télécharger le tableau Créateurs (CSV)",
        data=_to_csv(crea_table),
        file_name="recompenses_createurs.csv",
        mime="text/csv",
    )
else:
    st.info("Importez un fichier pour démarrer.")
