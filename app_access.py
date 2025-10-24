# app_access.py — Portail d'accès (indépendant) sans toucher app_v6.py
# Rôles: ADMIN (email unique) et MANAGER (liste). Blocage par défaut.
# Usage: déployer CE fichier comme "main file" sur Streamlit Cloud.
#        Mettre app_v6.py dans le même repo (il ne sera pas modifié).
# Secrets à définir (Settings → Secrets):
#   ADMIN_EMAIL="admin@tondomaine.com"
#   MANAGER_EMAILS="manager1@tondomaine.com,manager2@tondomaine.com"

import streamlit as st
import os

st.set_page_config(page_title="Portail d'accès • Monsieur Darmon", layout="wide")

def get_allowed_sets():
    admin = st.secrets.get("ADMIN_EMAIL", "").strip()
    managers = st.secrets.get("MANAGER_EMAILS", "").strip()
    managers_set = set([m.strip() for m in managers.split(",") if m.strip()]) if managers else set()
    return admin, managers_set

def get_current_user_email():
    # Streamlit Cloud: email dispo si "Require users to log in" activé
    if hasattr(st, "experimental_user"):
        u = st.experimental_user
        if isinstance(u, dict):
            return u.get("email")
        # compat: certains environnements exposent st.experimental_user.email
        try:
            return getattr(u, "email", None)
        except Exception:
            pass
    # fallback local: champ manuel
    return st.text_input("Email (local/test)")

def gate_access():
    admin_email, manager_set = get_allowed_sets()
    user_email = get_current_user_email()

    st.markdown("### Portail d'accès")
    if not user_email:
        st.info("Connectez-vous pour continuer ou saisissez un email en local.")
        st.stop()

    role = None
    if admin_email and user_email.lower() == admin_email.lower():
        role = "ADMIN"
    elif user_email.lower() in {m.lower() for m in manager_set}:
        role = "MANAGER"

    if role is None:
        st.error("Accès refusé. Cet espace est réservé aux managers autorisés.")
        st.stop()

    st.success(f"Accès accordé: {role}")
    return role, user_email

role, email = gate_access()

# Placeholder pour vues différentes plus tard
if role == "ADMIN":
    st.caption("Mode: ADMIN — la vue dédiée sera ajoutée plus tard.")
else:
    st.caption("Mode: MANAGER — la vue dédiée sera ajoutée plus tard.")

# Exécuter l'app validée sans la modifier
try:
    with open("app_v6.py", "r", encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, "app_v6.py", "exec"), globals(), globals())
except FileNotFoundError:
    st.error("Fichier app_v6.py introuvable dans le repo. Ajoutez-le à la racine.")
