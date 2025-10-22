# app.py
import io
import pandas as pd
import streamlit as st

from utils import (
    compute_creators_table,
    compute_agents_table_from_creators,
    compute_managers_table_from_creators,
    CANON,
)

st.set_page_config(page_title="Récompenses – Créateurs / Agents / Managers", page_icon="💎", layout="wide")
st.title("💎 Récompenses – Créateurs")
st.caption("Calcul automatique des récompenses (activité + paliers + bonus débutant) et répartition Agents / Managers.")

# ---------- helpers ----------
def read_uploaded_file(f) -> pd.DataFrame:
    name = (f.name or "").lower()
    data = f.read()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(data), engine="openpyxl")
    elif name.endswith(".csv"):
        # tente utf-8 puis fallback latin-1
        try:
            return pd.read_csv(io.StringIO(data.decode("utf-8")))
        except UnicodeDecodeError:
            return pd.read_csv(io.StringIO(data.decode("latin-1")))
    else:
        raise ValueError(f"Extension non supportée: {name}")

def concat_clean(dfs):
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    return df.drop_duplicates()

def download_csv(df, label, filename, key):
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    st.download_button(label, buf.getvalue().encode("utf-8-sig"), filename, "text/csv", key=key)

# ---------- upload ----------
st.subheader("Importez votre/vos fichier(s) (.xlsx / .csv)")
uploaded_files = st.file_uploader("Drag and drop files here", type=["xlsx", "xls", "csv"], accept_multiple_files=True)

if "last_payload_names" not in st.session_state:
    st.session_state.last_payload_names = None
    st.session_state.last_payload_data = None  # liste de bytes pour relecture

c1, c2 = st.columns(2)
use_last = False
with c1:
    if st.button("🧠 Utiliser les fichiers mémorisés (si dispo)"):
        if st.session_state.last_payload_data:
            use_last = True
        else:
            st.info("Aucun jeu de fichiers mémorisé dans cette session.")
with c2:
    if st.button("🗑️ Vider les fichiers de la session"):
        st.session_state.last_payload_names = None
        st.session_state.last_payload_data = None
        st.success("Mémoire de fichiers vidée.")

# ---------- lecture ----------
df_raw = pd.DataFrame()
try:
    if uploaded_files:
        dfs, names, blobs = [], [], []
        for f in uploaded_files:
            raw = f.read()
            # relire via un buffer (on garde les bytes pour “mémoire”)
            names.append(f.name)
            blobs.append(raw)
            dfs.append(read_uploaded_file(type("UF", (), {"name": f.name, "read": lambda self=raw: self})()))
        df_raw = concat_clean(dfs)
        st.session_state.last_payload_names = names
        st.session_state.last_payload_data = blobs
        st.success(f"Fichier(s) importé(s) : {', '.join(names)}")
    elif use_last and st.session_state.last_payload_data:
        dfs = []
        for name, blob in zip(st.session_state.last_payload_names, st.session_state.last_payload_data):
            dfs.append(read_uploaded_file(type("UF", (), {"name": name, "read": lambda self=blob: self})()))
        df_raw = concat_clean(dfs)
        st.info(f"Réutilisation : {', '.join(st.session_state.last_payload_names)}")
except Exception as e:
    st.error(f"Erreur de lecture : {e}")

if df_raw.empty:
    st.info("Importez au moins un fichier pour démarrer.")
    st.stop()

# ---------- calculs ----------
try:
    creators_df = compute_creators_table(df_raw)
    agents_df   = compute_agents_table_from_creators(creators_df)
    managers_df = compute_managers_table_from_creators(creators_df)
except Exception as e:
    st.error(f"Erreur lors du traitement des données : {e}")
    st.stop()

# ---------- affichage ----------
tab_crea, tab_agents, tab_man = st.tabs(["Créateurs", "Agents", "Managers"])

with tab_crea:
    st.subheader("Tableau Créateurs")
    st.dataframe(creators_df, use_container_width=True, height=520)
    download_csv(creators_df, "⬇️ Télécharger (CSV) – Créateurs", "Recompense_Createurs.csv", "dl_crea")

with tab_agents:
    st.subheader("Tableau Agents")
    st.dataframe(agents_df, use_container_width=True, height=520)
    download_csv(agents_df, "⬇️ Télécharger (CSV) – Agents", "Recompense_Agents.csv", "dl_agents")

with tab_man:
    st.subheader("Tableau Managers")
    st.dataframe(managers_df, use_container_width=True, height=520)
    download_csv(managers_df, "⬇️ Télécharger (CSV) – Managers", "Recompense_Managers.csv", "dl_man")

with st.expander("ℹ️ Colonnes attendues (noms canoniques)"):
    st.write(pd.DataFrame([CANON]).T.rename(columns={0: "Nom source → Nom canonique"}))
