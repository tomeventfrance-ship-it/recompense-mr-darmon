import streamlit as st
import pandas as pd
from utils import load_df, keep_needed_columns

st.set_page_config(page_title="Récompenses – Créateurs", page_icon="💎", layout="wide")

st.title("💎 Récompenses – Créateurs")
st.caption("Affichage fidèle des données importées (colonnes nécessaires uniquement). Aucune logique agents/managers ici.")

st.divider()

uploaded_files = st.file_uploader(
    "Importez un ou plusieurs fichiers (.xlsx, .xls, .csv)",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("Importez au moins un fichier pour démarrer.")
    st.stop()

dfs = []
for f in uploaded_files:
    try:
        df = load_df(f)
        df = keep_needed_columns(df)
        dfs.append(df)
    except Exception as e:
        st.error(f"Erreur de lecture du fichier **{f.name}** : {e}")

if not dfs:
    st.error("Aucune donnée exploitable.")
    st.stop()

# Concat simple (lignes les unes sous les autres) sans dédoublonnage ni calcul.
final_df = pd.concat(dfs, ignore_index=True)

st.success("✅ Fichier(s) chargé(s) et colonnes filtrées.")
st.dataframe(final_df, use_container_width=True)

# Export CSV fidèle
csv_bytes = final_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 Télécharger (CSV)",
    data=csv_bytes,
    file_name="createurs_filtre.csv",
    mime="text/csv"
)
