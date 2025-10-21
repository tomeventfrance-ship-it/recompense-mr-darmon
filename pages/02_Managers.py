import io
import pandas as pd
import streamlit as st
from utils import load_df, compute_managers_table

st.set_page_config(page_title="Récompenses – Managers", layout="wide")
st.sidebar.title("app")  # idem

st.title("🏢 Récompenses – Managers")

uploaded = st.file_uploader(
    "Importez le **même** fichier source (XLSX ou CSV)",
    type=["xlsx","csv"], accept_multiple_files=False
)

if not uploaded:
    st.info("Importez un fichier pour démarrer.", icon="📥")
    st.stop()

df = load_df(uploaded)

try:
    table = compute_managers_table(df)
except Exception as e:
    st.error(f"Erreur du traitement : {e}")
    st.stop()

st.dataframe(table, use_container_width=True, height=600)

@st.cache_data
def _csv(d): return d.to_csv(index=False).encode("utf-8")

@st.cache_data
def _xlsx(d):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as xw:
        d.to_excel(xw, index=False, sheet_name="Managers")
    return bio.getvalue()

c1, c2 = st.columns(2)
with c1:
    st.download_button("⬇️ CSV Managers", data=_csv(table), file_name="Recompense_Managers.csv", mime="text/csv", type="primary")
with c2:
    st.download_button("⬇️ XLSX Managers", data=_xlsx(table), file_name="Recompense_Managers.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
