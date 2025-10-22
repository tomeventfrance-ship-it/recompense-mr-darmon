import io
import pandas as pd
import streamlit as st

from utils import (
    parse_uploaded_files,
    compute_creators_table,
    compute_agents_table_from_creators,
    compute_managers_table_from_creators,
    CANON,
)
from history import (
    load_history_creators, save_history_creators, update_history_creators,
    load_history_agents, save_history_agents, update_history_agents,
    load_history_managers, save_history_managers, update_history_managers,
)

# --------------------- CONFIGURATION GÉNÉRALE ---------------------
st.set_page_config(page_title="Logiciel Tom Consulting & Event", page_icon="💎", layout="wide")
st.title("💎 Logiciel Récompense – Tom Consulting & Event")
st.caption("Calcul automatique : Créateurs + Agents + Managers (paliers, bonus, activité).")

# --------------------- UPLOAD ---------------------
uploaded_files = st.file_uploader(
    "Importe un ou plusieurs fichiers (.xlsx / .csv)",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("➡️ Importe au moins un fichier pour démarrer.")
    st.stop()

# --------------------- LECTURE ET NORMALISATION ---------------------
try:
    df_source = parse_uploaded_files(uploaded_files)
except Exception as e:
    st.error(f"Erreur de lecture du fichier : {e}")
    st.stop()

# --------------------- HISTORIQUES ---------------------
hist_creators = load_history_creators()
hist_agents = load_history_agents()
hist_managers = load_history_managers()

# --------------------- CRÉATEURS ---------------------
try:
    creators_table = compute_creators_table(df_source, history_df=hist_creators)
except Exception as e:
    st.error(f"Erreur lors du calcul des créateurs : {e}")
    st.stop()

# Mise à jour de l’historique (confirmé à vie / bonus déjà utilisé)
hist_creators_updated = update_history_creators(hist_creators, creators_table)
save_history_creators(hist_creators_updated)

# --------------------- AGENTS ---------------------
try:
    agents_table, agent_events = compute_agents_table_from_creators(creators_table, hist_agents)
except Exception as e:
    st.error(f"Erreur lors du calcul des agents : {e}")
    st.stop()

hist_agents_updated = update_history_agents(hist_agents, agent_events)
save_history_agents(hist_agents_updated)

# --------------------- MANAGERS ---------------------
try:
    managers_table, manager_events = compute_managers_table_from_creators(creators_table, hist_managers)
except Exception as e:
    st.error(f"Erreur lors du calcul des managers : {e}")
    st.stop()

hist_managers_updated = update_history_managers(hist_managers, manager_events)
save_history_managers(hist_managers_updated)

# --------------------- AFFICHAGE ---------------------
tab1, tab2, tab3 = st.tabs(["Créateurs", "Agents", "Managers"])

with tab1:
    st.subheader("💎 Récompenses – Créateurs")
    st.dataframe(creators_table, use_container_width=True, height=550)
    st.download_button(
        "⬇️ Télécharger le tableau des créateurs (CSV)",
        data=creators_table.to_csv(index=False, encoding="utf-8-sig"),
        file_name="recompenses_createurs.csv",
        mime="text/csv",
        use_container_width=True
    )

with tab2:
    st.subheader("🤝 Récompenses – Agents")
    st.dataframe(agents_table, use_container_width=True, height=550)
    st.download_button(
        "⬇️ Télécharger le tableau des agents (CSV)",
        data=agents_table.to_csv(index=False, encoding="utf-8-sig"),
        file_name="recompenses_agents.csv",
        mime="text/csv",
        use_container_width=True
    )
    with st.expander("📘 Journal des carry-over (agents)"):
        st.dataframe(agent_events, use_container_width=True)

with tab3:
    st.subheader("👑 Récompenses – Managers")
    st.dataframe(managers_table, use_container_width=True, height=550)
    st.download_button(
        "⬇️ Télécharger le tableau des managers (CSV)",
        data=managers_table.to_csv(index=False, encoding="utf-8-sig"),
        file_name="recompenses_managers.csv",
        mime="text/csv",
        use_container_width=True
    )
    with st.expander("📗 Journal des carry-over (managers)"):
        st.dataframe(manager_events, use_container_width=True)

# --------------------- INFORMATIONS ---------------------
with st.expander("ℹ️ Colonnes attendues et correspondances automatiques"):
    st.json(CANON)
