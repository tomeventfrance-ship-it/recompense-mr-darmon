# ui_theme.py — thème visuel indépendant (ADMIN vs MANAGER)
# Usage dans app.py (2 lignes) :
#   from ui_theme import apply_theme
#   apply_theme()  # auto: lit le rôle via env MD_ROLE ou argument apply_theme('ADMIN'|'MANAGER')
import os, streamlit as st

THEMES = {
    "ADMIN": {
        "bg": "linear-gradient(135deg, #0f1117 0%, #1a2033 60%, #222b45 100%)",
        "sidebar_bg": "#0f1117",
        "primary": "#00e5ff",
        "text": "#e6eefb",
        "muted": "#94a3b8",
        "tag": "Admin mode",
    },
    "MANAGER": {
        "bg": "linear-gradient(135deg, #0f1117 0%, #162720 60%, #12352b 100%)",
        "sidebar_bg": "#0e1c18",
        "primary": "#22c55e",
        "text": "#e6f8ef",
        "muted": "#9fb3a7",
        "tag": "Manager mode",
    },
}

def _css(theme: dict) -> str:
    return f"""
    <style>
    /* Fond app */
    [data-testid="stAppViewContainer"] {{
        background: {theme['bg']} !important;
        color: {theme['text']} !important;
    }}
    /* Sidebar */
    [data-testid="stSidebar"] > div:first-child {{
        background: {theme['sidebar_bg']} !important;
    }}
    /* Titres */
    h1, h2, h3, h4, h5, h6 {{ color: {theme['text']} !important; }}
    /* Texte atténué */
    .stMarkdown, .stText, .stCaption, p, small {{ color: {theme['muted']} !important; }}
    /* DataFrame header */
    .stDataFrame thead tr th {{ background: rgba(255,255,255,0.06) !important; color: {theme['text']} !important; }}
    /* Boutons primaires */
    .stButton>button {{
        background: {theme['primary']} !important;
        color: #0b0f14 !important;
        border: 0 !important;
        font-weight: 600;
    }}
    .stDownloadButton>button {{
        background: transparent !important;
        border: 1px solid {theme['primary']} !important;
        color: {theme['primary']} !important;
        font-weight: 600;
    }}
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
    .stTabs [data-baseweb="tab"] {{
        background: rgba(255,255,255,0.04);
        border-radius: 10px;
        padding: 8px 14px;
        color: {theme['text']};
    }}
    /* Tableau alterné */
    .stDataFrame tbody tr:nth-child(odd) td {{ background: rgba(0,0,0,0.12) !important; }}
    .stDataFrame tbody tr:nth-child(even) td {{ background: rgba(0,0,0,0.04) !important; }}
    /* Footer custom si présent */
    .app-footer {{ color: {theme['muted']} !important; }}
    </style>
    """

def apply_theme(role: str | None = None):
    if role is None:
        role = os.getenv("MD_ROLE", "").upper() or st.secrets.get("DEFAULT_ROLE", "").upper()
        if role not in THEMES:  # fallback si rien
            role = "ADMIN"
    theme = THEMES.get(role, THEMES["ADMIN"])
    st.markdown(_css(theme), unsafe_allow_html=True)
    # Badge coin haut droit pour repère visuel
    st.markdown(
        f"""<div style="position:fixed;top:8px;right:12px;padding:4px 10px;
        background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);
        border-radius:12px;color:{theme['text']};font-size:12px;z-index:1000;">{theme['tag']}</div>""",
        unsafe_allow_html=True,
    )
