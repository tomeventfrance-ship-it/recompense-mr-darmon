import streamlit as st
import pandas as pd

# --- Configuration de la page
st.set_page_config(
    page_title="Récompenses - Créateurs",
    page_icon="💎",
    layout="wide"
)

# --- Titre principal
st.title("💎 Récompenses - Créateurs")
st.caption("Automatisation des récompenses pour Créateurs, Agents et Managers.")

# --- Import du fichier Excel / CSV
uploaded_file = st.file_uploader("Importez votre fichier Excel (.xlsx / .csv)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.success("✅ Fichier importé avec succès !")

        # --- Aperçu du fichier
        st.dataframe(df.head())

        # --- Exemple de calcul automatique
        if 'Récompense palier 1' in df.columns and 'Récompense palier 2' in df.columns:
            df['Récompense totale'] = df[['Récompense palier 1', 'Récompense palier 2']].sum(axis=1)
            st.write("### Aperçu des récompenses totales calculées :")
            if 'Nom d’utilisateur' in df.columns:
                st.dataframe(df[['Nom d’utilisateur', 'Récompense totale']].head())
            else:
                st.dataframe(df[['Récompense totale']].head())

    except Exception as e:
        st.error(f"❌ Erreur lors de la lecture du fichier : {e}")
else:
    st.info("Importez un fichier pour démarrer.")
