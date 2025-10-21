# app.py
import io
import pandas as pd
import streamlit as st
from utils import load_df, merge_history, merge_bonus_history, compute_creators_table

st.set_page_config(page_title="Récompenses – Créateurs", page_icon="💎", layout="wide")

st.title("💎 Récompenses – Créateurs")
st.caption("Calcul automatique des récompenses (paliers, actif, bonus débutant à vie).")

# ---------- Mémoire de session ----------
if "store" not in st.session_state:
    st.session_state.store = {"current": None, "history": []}  # current: dict{name,bytes} ; history: list[dict]

def _pack(file):  # transforme un UploadedFile en {name, bytes}
    return {"name": file.name, "bytes": file.getvalue()}

def _load_from_pack(pack):
    bio = io.BytesIO(pack["bytes"])
    bio.name = pack["name"]
    return load_df(bio)

# ---------- Upload (multi) : dernier = mois courant ; autres = historique ----------
uploaded = st.file_uploader(
    "📂 Importez un ou plusieurs fichiers (le **dernier** est le mois **courant**, les autres = **historique**)",
    type=["xlsx", "csv"],
    accept_multiple_files=True,
    key="crea_upl"
)

if uploaded:
    packs = [_pack(f) for f in uploaded]
    if len(packs) == 1:
        st.session_state.store["current"] = packs[0]
        st.session_state.store["history"] = []
    else:
        st.session_state.store["current"] = packs[-1]
        st.session_state.store["history"] = packs[:-1]
    st.success("✅ Fichiers mémorisés pour la session (changements d’onglets sans re-upload).")

# Outils session
cA, cB, cC = st.columns([1,1,3])
with cA:
    if st.button("🗑️ Vider les fichiers de la session"):
        st.session_state.store = {"current": None, "history": []}
        st.toast("Session vidée.")
with cB:
    if st.session_state.store["current"]:
        st.caption(f"Courant: **{st.session_state.store['current']['name']}** | Historique: {len(st.session_state.store['history'])} fichier(s)")

# Pas de fichier → stop
if not st.session_state.store["current"]:
    st.info("Importez au moins un fichier ou réutilisez ceux mémorisés dans la session.", icon="📥")
    st.stop()

# ---------- Charger courant + historique ----------
current_df = _load_from_pack(st.session_state.store["current"])
history_users_150k = None
prior_bonus_users = None
if st.session_state.store["history"]:
    hist_dfs = [_load_from_pack(p) for p in st.session_state.store["history"]]
    history_users_150k = merge_history(*hist_dfs)
    prior_bonus_users = merge_bonus_history(*hist_dfs)

# ---------- Calcul principal ----------
try:
    table = compute_creators_table(
        current_df,
        history_users_150k=history_users_150k,
        prior_bonus_users=prior_bonus_users
    )
except Exception as e:
    st.error(f"❌ Erreur de traitement : {e}")
    st.stop()

# ---------- Affichage ----------
st.subheader("Aperçu du tableau calculé")
st.dataframe(table, use_container_width=True, height=620)

# ---------- Exports ----------
@st.cache_data(show_spinner=False)
def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")

@st.cache_data(show_spinner=False)
def _to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as xw:
        df.to_excel(xw, index=False, sheet_name="Créateurs")
    return bio.getvalue()

c1, c2 = st.columns(2)
with c1:
    st.download_button("⬇️ Télécharger CSV (créateurs)", _to_csv_bytes(table),
                       file_name="Recompense_Creators.csv", mime="text/csv", type="primary")
with c2:
    st.download_button("⬇️ Télécharger XLSX (créateurs)", _to_xlsx_bytes(table),
                       file_name="Recompense_Creators.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.caption("Tri décroissant sur « Récompense totale ». Montants en **diamants**. Bonus débutant : one-shot à vie.")
