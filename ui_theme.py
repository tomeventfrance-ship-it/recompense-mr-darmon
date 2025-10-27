# ui_theme.py — Rouge/Blanc/Noir + logo en arrière‑plan + typographie Poppins moderne
import os
import base64
from pathlib import Path as _Path
import streamlit as st

PRIMARY = "#e5093f"
BLACK   = "#0b0b0b"
WHITE   = "#ffffff"

def _logo_b64() -> str | None:
    p = _Path("assets/logo.png")
    if not p.exists():
        return None
    try:
        return base64.b64encode(p.read_bytes()).decode("utf-8")
    except Exception:
        return None

def apply_theme(role: str | None = None):
    font_stack = "'Poppins', 'Nunito Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    st.markdown(
        "<link href='https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap' rel='stylesheet'>",
        unsafe_allow_html=True,
    )

    css = f"""
    <style>
      :root {{
        --md-primary: {PRIMARY};
        --md-black: {BLACK};
        --md-white: {WHITE};
      }}
      [data-testid="stAppViewContainer"] {{
        background: radial-gradient(1200px 600px at 20% 0%, #ff2f5a 0%, #c4002b 40%, #0b0b0b 100%) !important;
        color: var(--md-white);
        font-family: {font_stack};
      }}
      section.main {{ position: relative; z-index: 1; }}
      [data-testid="stSidebar"] > div:first-child {{
        background: #0f0f10 !important;
        border-right: 1px solid rgba(255,255,255,0.06);
        color: var(--md-white);
        font-family: {font_stack};
      }}
      h1, h2, h3, h4, h5, h6 {{ color: var(--md-white); letter-spacing: .3px; font-weight: 600; }}
      p, .stMarkdown, .stText, small {{ color: rgba(255,255,255,0.9); font-weight: 400; }}
      .stButton>button {{
        background: var(--md-primary) !important;
        color: var(--md-white) !important;
        border: 0 !important;
        font-weight: 600;
        border-radius: 10px;
        font-family: {font_stack};
      }}
      .stButton>button:hover {{ filter: brightness(1.06); }}
      .stDownloadButton>button {{
        background: transparent !important;
        border: 1px solid var(--md-primary) !important;
        color: var(--md-primary) !important;
        font-weight: 600;
        border-radius: 10px;
        font-family: {font_stack};
      }}
      .stDownloadButton>button:hover {{
        background: var(--md-primary) !important;
        color: var(--md-white) !important;
      }}
      .stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
      .stTabs [data-baseweb="tab"] {{
        background: rgba(255,255,255,0.06);
        border-radius: 10px;
        padding: 8px 14px;
        color: var(--md-white);
        font-weight: 600;
        font-family: {font_stack};
      }}
      .stTabs [aria-selected="true"] {{
        background: var(--md-primary);
        color: var(--md-white);
      }}
      .stDataFrame thead tr th {{
        background: #000 !important;
        color: #fff !important;
        font-weight: 700 !important;
        font-family: {font_stack};
      }}
      .stDataFrame tbody tr:nth-child(odd) td {{ background: rgba(255,255,255,0.06) !important; }}
      .stDataFrame tbody tr:nth-child(even) td {{ background: rgba(255,255,255,0.025) !important; }}
      .app-footer {{ color: rgba(255,255,255,0.75) !important; font-family: {font_stack}; }}
      #MainMenu {{ visibility: visible !important; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

    b64 = _logo_b64()
    if b64:
        st.markdown(
            """<style>
            .bg-logo {
              position: fixed; inset: 0; pointer-events: none;
              background: center / 28vmax no-repeat url('data:image/png;base64,""" + b64 + """');
              opacity: .08; z-index: 0;
            }
            </style><div class='bg-logo'></div>""",
            unsafe_allow_html=True,
        )

    tag = (os.getenv("MD_ROLE", "") or st.secrets.get("DEFAULT_ROLE", "ADMIN")).upper()
    st.markdown(
        '<div style="position:fixed;top:8px;right:12px;padding:4px 10px;'
        'background:rgba(0,0,0,0.35);border:1px solid rgba(255,255,255,0.15);'
        'border-radius:12px;color:#fff;font-size:12px;z-index:1000;">' + tag.title() + ' mode</div>',
        unsafe_allow_html=True,
    )
