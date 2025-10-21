import streamlit as st
import pandas as pd
from utils import compute_creators_table  # ta fonction de calcul principale

# Configuration de la page
st.set_page_config(page_title="Récompenses - Créateurs", page_icon="💎", layout="wide")

st.title("💎 Récompenses – Créateurs")
st.write("Automatisation des récompenses pour les créateurs de contenu Tom Consulting & Event.")

# Zone d'import du fichier
uploaded = st.file_uploader("📂 Importez votre fichier (.xlsx ou .csv)", type=["xlsx", "csv"])

if uploaded:
    # Lecture du fichier complet
    try:
        if uploaded.name.lower().endswith(".csv"):
            df_raw = pd.read_csv(uploaded)
        else:
            df_raw = pd.read_excel(uploaded)

        st.success("✅ Fichier importé avec succès !")

        # Application des calculs du tableau créateurs
        df_result = compute_creators_table(df_raw)

        # Aperçu visuel (les 10 premières lignes seulement)
        st.subheader("Aperçu du tableau calculé (10 premières lignes)")
        st.dataframe(df_result.head(10), use_container_width=True)

        # Téléchargement du fichier complet
        csv_bytes = df_result.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Télécharger le tableau complet (CSV)",
            data=csv_bytes,
            file_name="recompenses_createurs_complet.csv",
            mime="text/csv",
            use_container_width=True
        )

    except Exception as e:
        st.error(f"❌ Erreur lors du traitement du fichier : {e}")

else:
    st.info("👉 Importez votre fichier pour démarrer le calcul automatique.")
uploaded = st.file_uploader(
    "Importez vos fichiers (mois courant + anciens en option)", 
    type=["xlsx","csv"], accept_multiple_files=True
)

if uploaded:
    # charge tout
    dfs = []
    for f in uploaded:
        df = load_df(f)  # ta fonction de lecture existante
        dfs.append(df)

    # s’il y a plusieurs fichiers, construit l’historique sur tous sauf le dernier
    history_users = None
    if len(dfs) >= 2:
        history_users = merge_history(*dfs[:-1])

    current_df = dfs[-1]
    table = compute_creators_table(current_df, history_users=history_users)
    show_and_export(table)  # ton affichage + export

