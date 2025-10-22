import streamlit as st
import pandas as pd
from utils import (
    compute_managers_table_from_creators
)

st.set_page_config(page_title="Récompenses – Managers", layout="wide")

st.title("🏢 Récompenses – Managers")

if "crea_table" not in st.session_state or st.session_state.crea_table is None:
    st.warning("Veuillez d’abord importer vos fichiers sur la page **Créateurs**.")
    st.stop()

crea_table = st.session_state.crea_table

try:
    managers_table = compute_managers_table_from_creators(crea_table)
except Exception as e:
    st.error(f"Erreur de calcul Managers : {e}")
    st.stop()

st.success("✅ Calcul Managers terminé.")
st.dataframe(managers_table, use_container_width=True)

@st.cache_data
def _to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "⬇️ Télécharger le tableau Managers (CSV)",
    data=_to_csv(managers_table),
    file_name="recompenses_managers.csv",
    mime="text/csv",
)
