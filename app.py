
import streamlit as st

# --- Configuration de la page ---
st.set_page_config(
    page_title="Monsieur Darmon",
    layout="wide",
    page_icon="❤️",
)

# --- Thème visuel global ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Poppins', sans-serif;
        color: white;
        background: linear-gradient(to bottom right, #8B0000, #000000);
    }

    h1 {
        text-align: center;
        font-weight: 600;
        color: white;
        margin-bottom: 10px;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    </style>
    """, unsafe_allow_html=True
)

# --- En-tête principale ---
st.markdown("<h1>Monsieur Darmon</h1>", unsafe_allow_html=True)

# --- Espace pour les 3 onglets (chargement fichiers, tableaux, etc.) ---
st.write("Zone de chargement des fichiers et affichage des tableaux ici.")
