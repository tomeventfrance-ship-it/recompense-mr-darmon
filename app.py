# -*- coding: utf-8 -*-
import io
import os
import pandas as pd
import streamlit as st

# --- imports “métier” ---
try:
    from utils import (
        load_df,                    # optionnel : si absent on lit localement
        compute_creators_table,
        compute_agents_table,
        compute_managers_table,
    )
except Exception:
    load_df = None
    def _missing(*_, **__):
        raise RuntimeError("Fonctions de calcul introuvables dans utils.py")
    compute_creators_table = _missing
    compute_agents_table   = _missing
    compute_managers_table = _missing

from history import (
    empty_history,
    load_history_from_uploaded,
    apply_updates_from_creators,
    to_csv_bytes,
)

st.set_page_config(page_title="Récompenses – Tom Consulting & Event", layout="wide")
st.title("💎 Récompenses – Créateurs / Agents / Managers")

# --------- helpers E/S ----------
def _safe_read(uploaded):
    """Lit un UploadedFile en DataFrame (fallback si utils.load_df indisponible)."""
    if load_df is not None:
        return load_df(uploaded)

    name = uploaded.name.lower()
    data = uploaded.read()
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(data), encoding="utf-8")
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(data))
    raise ValueError(f"Format non supporté : {uploaded.name}")

def _concat_dfs(dfs):
    if not dfs:
        return pd.DataFrame()
    base = pd.concat(dfs, ignore_index=True)
    # nettoyage léger
    base.columns = [str(c).strip() for c in base.columns]
    return base

def _download_button(df, label, fname):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(label, csv, file_name=fname, mime="text/csv")

# --------- barre latérale ----------
st.sidebar.header("Navigation")
tab_choice = st.sidebar.radio("Aller à :", ["Créateurs", "Agents", "Managers"], index=0)

st.sidebar.caption("Importer 1..N mois (courant + historiques). Les règles bonus/paliers sont gérées côté utils.py.")

# --------- zone d’import ----------
st.subheader(f"Importer votre/vos fichier(s) (.xlsx / .csv)")
uploads = st.file_uploader(
    "Drag and drop files here",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True
)

# Historique (optionnel) – appliqué uniquement côté créateurs
with st.expander("Historique (optionnel) – bonus débutant déjà payés & confirmé 150k"):
    hist_file = st.file_uploader("Importer un historique CSV existant", type=["csv", "xlsx", "xls"], accept_multiple_files=False)
    if hist_file is not None:
        st.caption(f"Fichier historique sélectionné : **{hist_file.name}**")
    else:
        st.caption("Aucun fichier d’historique fourni – un historique vide sera utilisé.")

# --------- lecture + calculs ----------
df = pd.DataFrame()
if uploads:
    try:
        dfs = [_safe_read(u) for u in uploads]
        df  = _concat_dfs(dfs)
        st.success(f"Fichier(s) importé(s) : {len(uploads)} • Lignes totales : {len(df)}")
    except Exception as e:
        st.error(f"Erreur de lecture : {e}")

# boutons utilitaires
cols_btn = st.columns(3)
with cols_btn[0]:
    if st.button("Afficher un aperçu des colonnes source"):
        if df.empty:
            st.warning("Aucune donnée.")
        else:
            st.write(pd.DataFrame({"Colonnes détectées": df.columns}))

with cols_btn[1]:
    show_raw = st.toggle("Voir un échantillon brut", value=False)
with cols_btn[2]:
    pass

if show_raw and not df.empty:
    st.dataframe(df.head(20), use_container_width=True)

# --------- sort selon l’onglet choisi ----------
if df.empty:
    st.info("Importez au moins un fichier pour démarrer.")
    st.stop()

# === Onglet : CRÉATEURS ===
if tab_choice == "Créateurs":
    st.header("Créateurs")
    try:
        creators = compute_creators_table(df)
    except Exception as e:
        st.error(f"Erreur dans compute_creators_table(utils.py) : {e}")
        st.stop()

    # appliquer l’historique : b1/b2/b3 déjà utilisés + confirmé_150k
    try:
        hist_in = load_history_from_uploaded(hist_file) if hist_file else empty_history()
        hist_out, delta = apply_updates_from_creators(creators, hist_in)

        # recalcul “après historique” si besoin ? (les paliers débutant sont payés une seule fois)
        # Ici on n’altère pas les montants déjà calculés : on garde creators tel que fourni par utils.py.
        # On donne juste l’historique à jour en téléchargement.
        with st.expander("Historique mis à jour (diff & export)", expanded=False):
            if not delta.empty:
                st.write("Modifications enregistrées :")
                st.dataframe(delta, use_container_width=True, height=200)
            else:
                st.caption("Aucun changement par rapport à l’historique fourni.")

            st.download_button(
                "💾 Télécharger l’historique à jour (CSV)",
                to_csv_bytes(hist_out),
                file_name="history_updated.csv",
                mime="text/csv"
            )
    except Exception as e:
        st.warning(f"Historique non appliqué : {e}")

    # affichage + téléchargements
    st.subheader("Tableau créateurs")
    st.dataframe(creators, use_container_width=True, hide_index=True)
    _download_button(creators, "⬇️ Exporter créateurs (CSV)", "recompenses_createurs.csv")

# === Onglet : AGENTS ===
elif tab_choice == "Agents":
    st.header("Agents")
    try:
        agents = compute_agents_table(df)
        st.dataframe(agents, use_container_width=True, hide_index=True)
        _download_button(agents, "⬇️ Exporter agents (CSV)", "recompenses_agents.csv")
    except Exception as e:
        st.error(f"Erreur dans compute_agents_table(utils.py) : {e}")

# === Onglet : MANAGERS ===
else:
    st.header("Managers")
    try:
        managers = compute_managers_table(df)
        st.dataframe(managers, use_container_width=True, hide_index=True)
        _download_button(managers, "⬇️ Exporter managers (CSV)", "recompenses_managers.csv")
    except Exception as e:
        st.error(f"Erreur dans compute_managers_table(utils.py) : {e}")
