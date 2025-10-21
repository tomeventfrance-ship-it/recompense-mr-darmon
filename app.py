import streamlit as st
import pandas as pd
from utils import load_df, compute_creators_table

st.set_page_config(page_title="Récompenses – Créateurs", layout="wide")

st.title("💎 Récompenses – Créateurs")
st.caption("Calcul automatique des récompenses pour les créateurs (activité + paliers + bonus débutant).")

with st.expander("Importez votre/vos fichier(s) (.xlsx / .csv)", expanded=True):
    files = st.file_uploader("Drag and drop files here", type=["xlsx","csv"], accept_multiple_files=True)
    col_a, col_b = st.columns(2)
    if col_a.button("Vider les fichiers de la session"):
        st.session_state.pop("crea_src", None)
        st.rerun()

# Lecture & mémoire de session
if files:
    try:
        dfs = [load_df(f) for f in files]
        df_in = pd.concat(dfs, ignore_index=True)
        st.session_state["crea_src"] = df_in
        st.success("Fichier(s) importé(s) avec succès.")
    except Exception as e:
        st.error(f"Erreur de lecture : {e}")

src = st.session_state.get("crea_src", None)

if src is not None and len(src):
    # Calcul
    out = compute_creators_table(src)

    st.subheader("Tableau calculé")
    st.dataframe(out, use_container_width=True)

    # Export
    csv = out.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Télécharger le CSV", data=csv, file_name="Recompense_Créateurs.csv", mime="text/csv")
else:
    st.info("Importez un fichier pour démarrer.")
