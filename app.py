# app.py — multi-imports, dédup, garde le dernier, résumé périodes

import streamlit as st
import pandas as pd
from utils import load_df, compute_creators_table

st.set_page_config(page_title="Récompenses – Créateurs", layout="wide")

st.title("💎 Récompenses – Créateurs")
st.caption("Calcul automatique des récompenses (activité + paliers + bonus débutant).")

# --- Session store ---
if "dfs" not in st.session_state:
    st.session_state.dfs = []      # liste de DataFrames normalisés (utils.load_df)
if "sources" not in st.session_state:
    st.session_state.sources = []  # noms de fichiers (juste informatif)

# --- Upload zone ---
with st.expander("Importez votre/vos fichier(s) (.xlsx / .csv)", expanded=True):
    files = st.file_uploader(
        "Drag and drop files here",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
        label_visibility="visible"
    )

    col_a, col_b = st.columns([1,1])
    with col_a:
        if st.button("📥 Ajouter ces fichier(s) à la session", use_container_width=True):
            if not files:
                st.warning("Aucun fichier sélectionné.")
            else:
                added = 0
                for f in files:
                    try:
                        df = load_df(f)  # utils.py -> normalise colonnes
                        st.session_state.dfs.append(df)
                        st.session_state.sources.append(getattr(f, "name", "fichier"))
                        added += 1
                    except Exception as e:
                        st.error(f"Erreur de lecture **{getattr(f,'name','(sans nom)')}** : {e}")
                if added:
                    st.success(f"{added} fichier(s) ajouté(s) à la session ✅")

    with col_b:
        if st.button("🧹 Vider les fichiers de la session", type="secondary", use_container_width=True):
            st.session_state.dfs = []
            st.session_state.sources = []
            st.experimental_rerun()

# --- Fusion + dédup ---
if not st.session_state.dfs:
    st.info("Importez un fichier pour démarrer.")
    st.stop()

# concatène tous les fichiers de la session
all_df = pd.concat(st.session_state.dfs, ignore_index=True)

# clé de dédup : (Période, Nom d’utilisateur). On garde **le dernier** importé.
# (concat garde l’ordre → les derniers ajoutés sont en bas → keep='last')
dedup_df = (
    all_df
    .assign(_order=range(len(all_df)))  # au cas où
    .sort_values("_order")
    .drop_duplicates(subset=["Période des données", "Nom d’utilisateur"], keep="last")
    .drop(columns=["_order"])
    .reset_index(drop=True)
)

# résumé périodes chargées
with st.expander("📦 Périodes chargées en session", expanded=True):
    periods = (
        dedup_df["Période des données"]
        .astype(str)
        .value_counts()
        .rename_axis("Période")
        .reset_index(name="Créateurs (lignes)")
        .sort_values("Période")
    )
    st.dataframe(periods, use_container_width=True, hide_index=True)
    st.caption(f"Fichiers en session : {', '.join(st.session_state.sources)}")

# --- Calcul & affichage ---
try:
    table = compute_creators_table(dedup_df)
except Exception as e:
    st.error(f"Erreur de traitement : {e}")
    st.stop()

st.success("Calcul terminé ✅")
st.dataframe(table, use_container_width=True, hide_index=True)

# --- Exports ---
csv = table.to_csv(index=False).encode("utf-8-sig")
xlsx_name = "Recompense_Createurs.xlsx"

@st.cache_data(show_spinner=False)
def to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    import io
    from pandas import ExcelWriter
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Créateurs")
    return bio.getvalue()

col1, col2 = st.columns(2)
with col1:
    st.download_button("⬇️ Exporter en CSV", data=csv, file_name="Recompense_Createurs.csv", mime="text/csv", use_container_width=True)
with col2:
    st.download_button("⬇️ Exporter en Excel", data=to_xlsx_bytes(table), file_name=xlsx_name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
