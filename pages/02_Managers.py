import streamlit as st
import pandas as pd
from utils import load_df, compute_creators_table, compute_managers_table

st.set_page_config(page_title="Récompenses – Managers", layout="wide")

st.sidebar.title("Managers")

st.title("🏁 Récompenses – Managers")
st.caption("Somme des diamants **actifs**, commissions et bonus managers (bonus 3 = 5000 par créateur).")

with st.expander("Importez votre/vos fichier(s) (.xlsx / .csv)", expanded=True):
    files = st.file_uploader("Drag and drop files here", type=["xlsx","csv"], accept_multiple_files=True, key="mgr_up")
    if st.button("Vider les fichiers de la session (Managers)"):
        st.session_state.pop("mgr_src", None)
        st.rerun()

if files:
    try:
        dfs = [load_df(f) for f in files]
        df_in = pd.concat(dfs, ignore_index=True)
        st.session_state["mgr_src"] = df_in
        st.success("Fichier(s) importé(s) avec succès.")
    except Exception as e:
        st.error(f"Erreur de lecture : {e}")

src = st.session_state.get("mgr_src", None)

if src is not None and len(src):
    crea = compute_creators_table(src)
    out = compute_managers_table(crea)

    st.subheader("Tableau Managers")
    st.dataframe(out, use_container_width=True)

    csv = out.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Télécharger le CSV Managers", data=csv, file_name="Recompense_Managers.csv", mime="text/csv")
else:
    st.info("Importez un fichier pour démarrer.")
