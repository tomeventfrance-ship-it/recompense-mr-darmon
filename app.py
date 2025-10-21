# app.py
uploaded = st.file_uploader("Importez un ou plusieurs fichiers (le dernier = mois courant)", type=["xlsx","csv"], accept_multiple_files=True)
if not uploaded: st.stop()

dfs = []
for f in uploaded:
    df = pd.read_csv(f) if f.name.lower().endswith(".csv") else pd.read_excel(f)
    dfs.append(df)

from utils import merge_bonus_history, compute_creators_table
prior_bonus = merge_bonus_history(*dfs[:-1]) if len(dfs) >= 2 else None
current = dfs[-1]

table = compute_creators_table(current, prior_bonus_users=prior_bonus)
st.dataframe(table, use_container_width=True)
st.download_button("⬇️ CSV", table.to_csv(index=False).encode("utf-8-sig"), "Recompense_Creators.csv", "text/csv")

import io
import pandas as pd
import streamlit as st
from utils import compute_creators_table

st.set_page_config(page_title="Récompenses – Créateurs", layout="wide")

st.title("💎 Récompenses – Créateurs")
st.caption("Automatisation des récompenses selon les règles validées (paliers, actif, bonus débutant).")

uploaded = st.file_uploader(
    "Importez votre fichier (.xlsx ou .csv)", type=["xlsx", "csv"], label_visibility="visible"
)

if uploaded:
    st.success("Fichier importé avec succès !")
    try:
        if uploaded.name.lower().endswith(".csv"):
            df_src = pd.read_csv(uploaded)
        else:
            df_src = pd.read_excel(uploaded)

        # Calcul
        df_crea = compute_creators_table(df_src)

        # Affichage
        st.dataframe(df_crea, use_container_width=True)

        # Export CSV
        csv = df_crea.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Télécharger le tableau créateurs (CSV)",
            data=csv,
            file_name="Recompense_Creators.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"Erreur lors du traitement du fichier : {e}")
else:
    st.info("Importez un fichier pour démarrer.")

