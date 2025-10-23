# app.py
import io
import traceback
import pandas as pd
import streamlit as st

# ---- Fonctions fournies par utils.py (ne rien changer ici) ----
from utils import (
    ensure_df,
    normalize_source,
    compute_creators_table,
    compute_agents_table,
    compute_managers_table,
)

st.set_page_config(
    page_title="Récompenses – Créateurs / Agents / Managers",
    page_icon="💎",
    layout="wide",
)

# ------------------ Helpers locaux (lecture fichiers) ------------------
def read_any_uploaded(file) -> pd.DataFrame:
    """
    Lit un fichier Streamlit (xlsx/xls/csv) -> DataFrame Pandas.
    Renvoie un DataFrame vide si format non reconnu.
    """
    name = (file.name or "").lower()
    data = file.read()
    bio = io.BytesIO(data)

    try:
        if name.endswith(".xlsx") or name.endswith(".xls"):
            df = pd.read_excel(bio)
        elif name.endswith(".csv"):
            # sep=None + engine='python' auto-détecte le séparateur (',' ';' '\t'…)
            df = pd.read_csv(io.BytesIO(data), sep=None, engine="python")
        else:
            return pd.DataFrame()
        return df
    except Exception:
        # Affiche l’erreur mais renvoie DF vide pour ne pas casser l’app
        st.error("Erreur de lecture du fichier :\n" + traceback.format_exc())
        return pd.DataFrame()

def concat_normalized(dfs):
    """Concatène une liste de DataFrames après normalisation des colonnes."""
    clean = []
    for d in dfs:
        if d is None or d.empty:
            continue
        # ensure_df pour robustesse (types/NA), puis normalisation des noms
        d = ensure_df(d)
        d = normalize_source(d)
        if not d.empty:
            clean.append(d)
    if not clean:
        return None
    return pd.concat(clean, ignore_index=True)

def download_csv_button(df: pd.DataFrame, label: str, filename: str):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(label=label, data=csv, file_name=filename, mime="text/csv")

# ----------------------------- UI -------------------------------------
st.title("💎 Récompenses – Créateurs / Agents / Managers")

st.markdown(
    "Importez **un ou plusieurs** fichiers **.xlsx/.xls/.csv** (mois courant + historiques). "
    "Aucune mémorisation cachée : ce que vous importez ici est ce qui est utilisé dans les calculs."
)

with st.container():
    colU, colH = st.columns([3, 3], gap="large")

    with colU:
        uploaded_files = st.file_uploader(
            "Données du·de la créateur(trice) (mois courant) – formats acceptés : XLSX, XLS, CSV",
            type=["xlsx", "xls", "csv"],
            accept_multiple_files=True,
        )

    with colH:
        history_files = st.file_uploader(
            "Historique (optionnel) – bonus débutant déjà payés & créateurs confirmés (≥150k)",
            type=["xlsx", "xls", "csv"],
            accept_multiple_files=True,
        )

    # Aperçu brut (colonnes source)
    show_sample = st.toggle("Voir un échantillon brut", value=False)

# --------------------- Chargement + Normalisation ----------------------
df_current = None
df_history = None

try:
    dfs_cur = []
    if uploaded_files:
        for f in uploaded_files:
            df = read_any_uploaded(f)
            dfs_cur.append(df)
    df_current = concat_normalized(dfs_cur)

    dfs_hist = []
    if history_files:
        for f in history_files:
            df = read_any_uploaded(f)
            dfs_hist.append(df)
    df_history = concat_normalized(dfs_hist)

    # Bandeau d'état d'import
    nb_rows = 0 if df_current is None else len(df_current)
    st.success(f"Fichier(s) importé(s) : **{len(uploaded_files or [])}** • Lignes totales : **{nb_rows}**")

    if show_sample:
        st.caption("Aperçu des colonnes (après normalisation) – 5 premières lignes")
        if df_current is not None and not df_current.empty:
            st.dataframe(df_current.head(5), use_container_width=True)
        else:
            st.info("Aucune donnée importée pour le mois courant.")
        if df_history is not None and not df_history.empty:
            st.caption("Historique – 5 premières lignes")
            st.dataframe(df_history.head(5), use_container_width=True)

except Exception:
    st.error("Erreur lors du traitement d'import :\n" + traceback.format_exc())

# ---------------------------- Navigation ------------------------------
st.sidebar.header("Navigation")
page = st.sidebar.radio("Aller à :", options=["Créateurs", "Agents", "Managers"], index=0)

# ---------------------------- Pages -----------------------------------
if page == "Créateurs":
    st.subheader("Créateurs")
    if df_current is None or df_current.empty:
        st.warning("Importez au moins un fichier pour démarrer.")
    else:
        try:
            table_crea = compute_creators_table(df_current, df_history)
            if table_crea is None or table_crea.empty:
                st.info("Aucune donnée exploitable.")
            else:
                st.dataframe(table_crea, use_container_width=True, height=480)
                colA, colB = st.columns([1, 1])
                with colA:
                    download_csv_button(
                        table_crea, "⬇️ Export CSV – Créateurs", "recompenses_createurs.csv"
                    )
        except Exception:
            st.error("Erreur dans compute_creators_table(utils.py) :\n" + traceback.format_exc())

elif page == "Agents":
    st.subheader("Agents")
    if df_current is None or df_current.empty:
        st.warning("Importez au moins un fichier pour démarrer.")
    else:
        try:
            table_agents = compute_agents_table(df_current, df_history)
            if table_agents is None or table_agents.empty:
                st.info("Aucune donnée exploitable.")
            else:
                st.dataframe(table_agents, use_container_width=True, height=480)
                download_csv_button(
                    table_agents, "⬇️ Export CSV – Agents", "recompenses_agents.csv"
                )
        except Exception:
            st.error("Erreur dans compute_agents_table(utils.py) :\n" + traceback.format_exc())

else:  # Managers
    st.subheader("Managers")
    if df_current is None or df_current.empty:
        st.warning("Importez au moins un fichier pour démarrer.")
    else:
        try:
            table_mgr = compute_managers_table(df_current, df_history)
            if table_mgr is None or table_mgr.empty:
                st.info("Aucune donnée exploitable.")
            else:
                st.dataframe(table_mgr, use_container_width=True, height=480)
                download_csv_button(
                    table_mgr, "⬇️ Export CSV – Managers", "recompenses_managers.csv"
                )
        except Exception:
            st.error("Erreur dans compute_managers_table(utils.py) :\n" + traceback.format_exc())
