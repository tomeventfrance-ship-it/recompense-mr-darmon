import streamlit as st
import pandas as pd
from utils import (
    compute_agents_table_from_creators, normalize_columns, compute_creators_table
)

st.set_page_config(page_title="Récompenses – Agents", layout="wide")
st.sidebar.title("Navigation")

st.title("🧑‍💼 Récompenses – Agents")

# On réutilise la table créateurs si déjà calculée sur l’accueil
if "crea_table" not in st.session_state or st.session_state.crea_table is None:
    st.warning("Veuillez d’abord importer vos fichiers sur la page **Créateurs**.")
    st.stop()

crea_table = st.session_state.crea_table

try:
    agents_table = compute_agents_table_from_creators(crea_table)
except Exception as e:
    st.error(f"Erreur de calcul Agents : {e}")
    st.stop()

st.success("✅ Calcul Agents terminé.")
st.dataframe(agents_table, use_container_width=True)

@st.cache_data
def _to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "⬇️ Télécharger le tableau Agents (CSV)",
    data=_to_csv(agents_table),
    file_name="recompenses_agents.csv",
    mime="text/csv",
)
