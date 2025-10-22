import streamlit as st
import pandas as pd
from utils import load_df, compute_creators_table

st.set_page_config(page_title="Récompenses – Créateurs", page_icon="💎", layout="wide")

st.title("💎 Récompenses – Créateurs")
st.caption("Calcul automatique des récompenses (activité + paliers + bonus débutant) et répartition Agents / Managers.")

st.divider()

# --- Téléversement ---
uploaded_files = st.file_uploader(
    "Importez votre/vos fichier(s) (.xlsx / .csv)",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True
)

# --- Lecture des fichiers ---
dfs = []
if uploaded_files:
    for f in uploaded_files:
        try:
            df = load_df(f)
            dfs.append(df)
        except Exception as e:
            st.error(f"Erreur de lecture du fichier **{f.name}** : {e}")
else:
    st.info("Importez au moins un fichier pour démarrer.")
    st.stop()

# --- Calcul du tableau final ---
try:
    results = compute_creators_table(dfs)
except Exception as e:
    st.error(f"Erreur lors du traitement des données : {e}")
    st.stop()

if results is None or results.empty:
    st.warning("Aucune donnée calculée. Vérifiez vos fichiers.")
    st.stop()

# --- Affichage du tableau ---
st.success("✅ Fichiers importés avec succès et traités.")
st.dataframe(results, use_container_width=True)

# --- Téléchargement Excel ---
@st.cache_data
def convert_df_to_excel(df: pd.DataFrame) -> bytes:
    from io import BytesIO
    with pd.ExcelWriter(BytesIO(), engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Résultats")
        writer.close()
        data = writer.book
    return writer.book

try:
    excel_data = results.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Télécharger les résultats au format CSV",
        data=excel_data,
        file_name="recompenses_createurs.csv",
        mime="text/csv"
    )
except Exception as e:
    st.error(f"Erreur lors de la génération du fichier d'export : {e}")
