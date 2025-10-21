# pages/02_Managers.py
import io
import pandas as pd
import streamlit as st
from utils import load_df, compute_managers_table

st.set_page_config(page_title="Récompenses – Managers", page_icon="🏢", layout="wide")

st.title("🏢 Récompenses – Managers")
st.caption("Agrégation sur les créateurs **actifs** (seuil 200k, 2% → 3%).")

# Récupérer éventuel fichier mémorisé
store = st.session_state.get("store", {"current": None})
df = None

uploaded = st.file_uploader(
    "📂 Importez le **même** fichier source (ou laissez vide pour utiliser celui mémorisé)",
    type=["xlsx","csv"],
    accept_multiple_files=False,
    key="managers_upl"
)

def _load_uploaded(u):
    bio = io.BytesIO(u.getvalue()); bio.name = u.name
    return load_df(bio)

if uploaded:
    df = _load_uploaded(uploaded)
    # Met à jour la session (courant seulement)
    st.session_state.store = st.session_state.get("store", {"current": None, "history": []})
    st.session_state.store["current"] = {"name": uploaded.name, "bytes": uploaded.getvalue()}
    st.success("✅ Fichier managers chargé et mémorisé pour la session.")
elif store and store["current"]:
    bio = io.BytesIO(store["current"]["bytes"]); bio.name = store["current"]["name"]
    df = load_df(bio)
    st.info(f"♻️ Fichier repris de la session: **{store['current']['name']}**")
else:
    st.info("Importez un fichier ou chargez-le d’abord dans l’onglet Créateurs.", icon="📥")
    st.stop()

# Calcul
try:
    table = compute_managers_table(df)
except Exception as e:
    st.error(f"❌ Erreur de traitement : {e}")
    st.stop()

st.dataframe(table, use_container_width=True, height=620)

# Exports
@st.cache_data
def _csv(d): return d.to_csv(index=False).encode("utf-8-sig")

@st.cache_data
def _xlsx(d):
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as xw:
        d.to_excel(xw, index=False, sheet_name="Managers")
    return bio.getvalue()

c1, c2 = st.columns(2)
with c1:
    st.download_button("⬇️ CSV Managers", _csv(table), file_name="Recompense_Managers.csv",
                       mime="text/csv", type="primary")
with c2:
    st.download_button("⬇️ XLSX Managers", _xlsx(table), file_name="Recompense_Managers.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
