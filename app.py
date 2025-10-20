import streamlit as st, pandas as pd
from utils import REQUIRED, prepare_creators, detect_user_col

st.set_page_config(page_title="Récompenses – Créateurs", layout="wide")
st.title("💎 Récompenses – Créateurs")

up = st.file_uploader("📂 Importez votre fichier (.xlsx / .csv)", type=["xlsx","csv"], key="upload_crea")

if not up:
    st.info("Importez un fichier pour démarrer.")
    st.stop()

df = pd.read_csv(up) if up.name.lower().endswith(".csv") else pd.read_excel(up)
missing = [c for c in REQUIRED if c not in df.columns]
if missing:
    st.error(f"Colonnes manquantes : {missing}")
    st.stop()

# option manuelle si la colonne utilisateur n'est pas détectée
user_col = detect_user_col(df)
if user_col is None:
    with st.expander("Sélection du nom d’utilisateur (si non détecté)"):
        pick = st.selectbox("Colonne du nom d’utilisateur :", ["(aucune)"]+list(df.columns), index=0)
        if pick != "(aucune)":
            df = df.rename(columns={pick: "Nom d'utilisateur"})
            # la détection retrouvera cette colonne dans prepare_creators

crea = prepare_creators(df)
st.dataframe(crea, use_container_width=True)
st.download_button("⬇️ Télécharger (CSV)", crea.to_csv(index=False).encode("utf-8"),
                   file_name="Récompense_Créateurs.csv", mime="text/csv")
st.caption("Tom Consulting & Event")
