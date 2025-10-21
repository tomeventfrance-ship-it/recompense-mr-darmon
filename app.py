import io
import pandas as pd
import streamlit as st

from utils import (
    load_df, merge_history, compute_creators_table
)

st.set_page_config(page_title="Récompenses – Créateurs", layout="wide")

st.title("💎 Récompenses – Créateurs")
st.caption("Automatisation des récompenses pour les créateurs Tom Consulting & Event.")

uploaded = st.file_uploader(
    "Importez un ou plusieurs fichiers Excel/CSV (le **dernier** = mois courant ; les précédents = **historique** 150k)",
    type=["xlsx", "csv"], accept_multiple_files=True
)

if not uploaded:
    st.info("Importez un fichier pour démarrer.", icon="📥")
    st.stop()

# Charge tous les fichiers
dfs = []
for f in uploaded:
    st.success(f"Fichier importé : **{f.name}**", icon="✅")
    dfs.append(load_df(f))

# Historique (tous sauf le dernier), mois courant = dernier
history_users = None
if len(dfs) >= 2:
    history_users = merge_history(*dfs[:-1])

current_df = dfs[-1]

# Calcul
try:
    table = compute_creators_table(current_df, history_users=history_users)
except Exception as e:
    st.error(f"Erreur du traitement : {e}")
    st.stop()

# Aperçu
st.subheader("Aperçu")
st.dataframe(table, use_container_width=True, height=600)

# Exports
@st.cache_data(show_spinner=False)
def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

@st.cache_data(show_spinner=False)
def _to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as xw:
        df.to_excel(xw, index=False, sheet_name="Récompenses")
    return bio.getvalue()

c1, c2 = st.columns(2)
with c1:
    st.download_button(
        "⬇️ Télécharger en CSV",
        data=_to_csv_bytes(table),
        file_name="Recompense_Creators.csv",
        mime="text/csv",
        type="primary"
    )
with c2:
    st.download_button(
        "⬇️ Télécharger en XLSX",
        data=_to_xlsx_bytes(table),
        file_name="Recompense_Creators.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.caption("Tri décroissant sur « Récompense totale ». Les montants sont en **diamants**.")
