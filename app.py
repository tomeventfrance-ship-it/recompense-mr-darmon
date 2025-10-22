# app.py — Récompenses (Créateurs / Agents / Managers)
# - Import multi-fichiers (.xlsx/.csv)
# - Déduplication (Période + Nom d’utilisateur) en gardant le dernier importé
# - Historique persistant (history.csv) pour ever_150k & bonus_used
# - Bonus créateurs 75k/150k/500k = 500/1088/3000 (non cumulés, palier le plus haut)
# - Bonus agents = +1000 (palier2) / +15000 (palier3), non cumulés par créateur
# - Bonus managers = +1000 (palier2) / +5000 (palier3), non cumulés par créateur

import io
import pandas as pd
import streamlit as st

from utils import (
    load_df, normalize_columns, compute_creators_table,
    compute_agents_table_from_creators, compute_managers_table_from_creators,
    CANON
)
from history import load_history, save_history, update_history

st.set_page_config(page_title="Récompenses – Tom Consulting & Event", layout="wide")
st.title("💎 Récompenses – Tom Consulting & Event")

# ---------------------- Mémoire de session ----------------------
if "raw_files" not in st.session_state:
    st.session_state.raw_files = []   # liste de (name, bytes)
if "df_src" not in st.session_state:
    st.session_state.df_src = None
if "crea_table" not in st.session_state:
    st.session_state.crea_table = None
if "agents_table" not in st.session_state:
    st.session_state.agents_table = None
if "managers_table" not in st.session_state:
    st.session_state.managers_table = None

# ---------------------- Barre latérale ----------------------
with st.sidebar:
    st.header("Navigation")
    section = st.radio("Section", ["Créateurs", "Agents", "Managers"], index=0)
    st.divider()
    replace = st.checkbox("Remplacer les données à l’import", value=True)
    if st.button("🧹 Vider la session"):
        st.session_state.raw_files = []
        st.session_state.df_src = None
        st.session_state.crea_table = None
        st.session_state.agents_table = None
        st.session_state.managers_table = None
        st.toast("Session vidée.")
    st.divider()
    st.caption("Importez vos fichiers sur l’onglet **Créateurs**.")

# ---------------------- Import fichiers (dans section Créateurs) ----------------------
if section == "Créateurs":
    with st.expander("📂 Import (.xlsx/.csv)", expanded=True):
        files = st.file_uploader(
            "Glissez 1 ou plusieurs fichiers",
            type=["xlsx", "xls", "csv"],
            accept_multiple_files=True
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📥 Ajouter à la session", use_container_width=True):
                if not files:
                    st.warning("Aucun fichier sélectionné.")
                else:
                    if replace:
                        st.session_state.raw_files = []
                    added = 0
                    for f in files:
                        st.session_state.raw_files.append((f.name, f.getvalue()))
                        added += 1
                    if added:
                        st.success(f"{added} fichier(s) ajouté(s).")

        with c2:
            if st.button("♻️ Recalculer maintenant", use_container_width=True):
                st.experimental_rerun()

# ---------------------- Construction du DataFrame source ----------------------
def build_source_df():
    if not st.session_state.raw_files:
        return None, []
    frames = []
    names = []
    for name, data in st.session_state.raw_files:
        try:
            bio = io.BytesIO(data)
            df = load_df([bio])  # utils.load_df empile et normalise si liste; ici 1 par fichier
            # load_df renvoie déjà un df normalisé si plusieurs passés; on renormalise par sécurité
            df = normalize_columns(df)
            df["_f_import"] = name  # info
            frames.append(df)
            names.append(name)
        except Exception as e:
            st.error(f"Erreur de lecture ({name}) : {e}")
            return None, []
    if not frames:
        return None, []
    full = pd.concat(frames, ignore_index=True)

    # Déduplication: (Période, Nom d’utilisateur) -> garde le DERNIER importé
    # On s'appuie sur l'ordre d'empilement (raw_files), donc on ajoute un ordre
    full["_ord"] = range(len(full))
    full = (full.sort_values("_ord")
                 .drop_duplicates(subset=[CANON["period"], CANON["username"]], keep="last")
                 .drop(columns=["_ord"])
                 .reset_index(drop=True))
    return full, names

# Reconstruit la base si pas encore faite
if st.session_state.df_src is None and st.session_state.raw_files:
    base, names = build_source_df()
    if base is not None:
        st.session_state.df_src = base
else:
    # Si déjà construite, on affiche le résumé des périodes
    base = st.session_state.df_src
    names = [n for n, _ in st.session_state.raw_files]

# ---------------------- Si pas d’import ----------------------
if base is None:
    st.info("Importez un fichier dans **Créateurs** pour démarrer.")
    st.stop()

# ---------------------- Résumé des périodes ----------------------
with st.expander("📦 Périodes chargées", expanded=True):
    periods = (base[CANON["period"]].astype(str)
               .value_counts()
               .rename_axis("Période").reset_index(name="Lignes")
               .sort_values("Période"))
    st.dataframe(periods, use_container_width=True, hide_index=True)
    st.caption(f"Fichiers en session : {', '.join(names)}")

# ---------------------- Calcul Créateurs + Historique ----------------------
def compute_all():
    # Historique
    hist = load_history()

    # Table créateurs (avec prise en compte de l’historique passé via bonus_used/ever_150k)
    crea = compute_creators_table(base, history_df=hist)

    # Met à jour l’historique (ever_150k, bonus_used) puis sauve
    hist_new = update_history(hist, crea)
    save_history(hist_new)

    # Agents / Managers à partir de la table créateurs calculée
    agents = compute_agents_table_from_creators(crea)
    managers = compute_managers_table_from_creators(crea)
    return crea, agents, managers

if st.session_state.crea_table is None or section == "Créateurs":
    try:
        crea_table, agents_table, managers_table = compute_all()
        st.session_state.crea_table = crea_table
        st.session_state.agents_table = agents_table
        st.session_state.managers_table = managers_table
    except Exception as e:
        st.error(f"Erreur de calcul : {e}")
        st.stop()

# ---------------------- Affichages & exports ----------------------
@st.cache_data(show_spinner=False)
def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")

if section == "Créateurs":
    st.subheader("Créateurs")
    st.dataframe(st.session_state.crea_table, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Exporter Créateurs (CSV)",
        data=_to_csv_bytes(st.session_state.crea_table),
        file_name="recompenses_createurs.csv",
        mime="text/csv",
        use_container_width=True
    )

elif section == "Agents":
    st.subheader("Agents")
    if st.session_state.agents_table is None:
        st.warning("Calcule d’abord la page **Créateurs**.")
        st.stop()
    st.dataframe(st.session_state.agents_table, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Exporter Agents (CSV)",
        data=_to_csv_bytes(st.session_state.agents_table),
        file_name="recompenses_agents.csv",
        mime="text/csv",
        use_container_width=True
    )

else:
    st.subheader("Managers")
    if st.session_state.managers_table is None:
        st.warning("Calcule d’abord la page **Créateurs**.")
        st.stop()
    st.dataframe(st.session_state.managers_table, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Exporter Managers (CSV)",
        data=_to_csv_bytes(st.session_state.managers_table),
        file_name="recompenses_managers.csv",
        mime="text/csv",
        use_container_width=True
    )
