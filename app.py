import io, re, yaml
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
import streamlit as st
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

st.set_page_config(page_title="Récompenses TCE", layout="wide")

@st.cache_data(show_spinner=False)
def read_any(file) -> pd.DataFrame:
    name = file.name.lower()
    if name.endswith('.xlsx') or name.endswith('.xls'):
        return pd.read_excel(file)
    return pd.read_csv(file)

def to_numeric_safe(x):
    if pd.isna(x): return 0.0
    s = str(x).strip().replace(' ', '').replace(',', '.')
    try: return float(s)
    except: return 0.0

def parse_duration_to_hours(x) -> float:
    if pd.isna(x): return 0.0
    s = str(x).strip().lower()
    try: return float(s.replace(',', '.'))
    except: pass
    if re.match(r'^\d{1,2}:\d{1,2}(:\d{1,2})?$', s):
        parts = [int(p) for p in s.split(':')]
        h = parts[0]; m = parts[1] if len(parts)>1 else 0; sec = parts[2] if len(parts)>2 else 0
        return h + m/60 + sec/3600
    h = re.search(r'(\d+)\s*h', s); m = re.search(r'(\d+)\s*m', s)
    if h or m:
        hh = int(h.group(1)) if h else 0; mm = int(m.group(1)) if m else 0
        return hh + mm/60
    mm = re.search(r'(\d+)\s*min', s)
    if mm: return int(mm.group(1))/60
    return 0.0

COLS = {
    'periode': 'Période des données',
    'creator_username': "Nom d'utilisateur du/de la créateur(trice)",
    'groupe': 'Groupe',
    'agent': 'Agent',
    'date_relation': "Date d'établissement de la relation",
    'diamants': 'Diamants',
    'duree_live': 'Durée de LIVE',
    'jours_live': 'Jours de passage en LIVE valides',
    'statut_diplome': 'Statut du diplôme'
}

def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    for k, v in COLS.items():
        out[k] = df[v] if v in df.columns else (0 if k in ['diamants','jours_live'] else '')
    out['diamants'] = out['diamants'].apply(to_numeric_safe)
    out['jours_live'] = out['jours_live'].apply(lambda x: int(to_numeric_safe(x)))
    out['heures_live'] = df[COLS['duree_live']].apply(parse_duration_to_hours) if COLS['duree_live'] in df.columns else 0.0
    if 'ID créateur(trice)' in df.columns:
        out['creator_id'] = df['ID créateur(trice)'].astype(str)
    else:
        out['creator_id'] = out['creator_username'].astype(str)
    for extra in ['Diamants des matchs','Diamants du mode multi-invité']:
        if extra in df.columns:
            out['diamants'] = out['diamants'] + df[extra].apply(to_numeric_safe)
    for c in ['creator_username','groupe','agent','statut_diplome','periode']:
        out[c] = out[c].astype(str)
    return out

DEFAULT_CFG = {
    'activation': {
        'beginner': {'days': 7, 'hours': 15},
        'confirmed': {'days': 12, 'hours': 25},
        'second': {'days': 20, 'hours': 80}
    },
    'confirmed_threshold_diamants': 150000,
    'beginner_bonuses': {
        'days_window': 90,
        'milestones': [
            {'min': 75000, 'max': 149999, 'bonus': 500, 'code':'B1'},
            {'min': 150000, 'max': 499999, 'bonus': 1088, 'code':'B2'},
            {'min': 500000, 'max': 2000000, 'bonus': 3000, 'code':'B3'}
        ]
    }
}

P1_TABLE = [
    (35000, 74999, 1000),
    (75000, 149999, 2500),
    (150000, 199999, 5000),
    (200000, 299999, 6000),
    (300000, 399999, 7999),
    (400000, 499999, 12000),
    (500000, 599999, 15000),
    (600000, 699999, 18000),
    (700000, 799999, 21000),
    (800000, 899999, 24000),
    (900000, 999999, 26999),
    (1000000, 1499999, 30000),
    (1500000, 1999999, 44999),
    (2000000, None, 'PCT4')
]

P2_TABLE = [
    (35000, 74999, 1000),
    (75000, 149999, 2500),
    (150000, 199999, 6000),
    (200000, 299999, 7999),
    (300000, 399999, 12000),
    (400000, 499999, 15000),
    (500000, 599999, 20000),
    (600000, 699999, 24000),
    (700000, 799999, 26999),
    (800000, 899999, 30000),
    (900000, 999999, 35000),
    (1000000, 1499999, 39999),
    (1500000, 1999999, 59999),
    (2000000, None, 'PCT4')
]

def select_fixed_reward(amount: float, table):
    for lo, hi, val in table:
        if (hi is None and amount >= lo) or (amount >= lo and amount <= hi):
            return round(amount * 0.04, 2) if val == 'PCT4' else float(val)
    return 0.0

def creator_type(row, hist, cfg):
    thr = cfg.get('confirmed_threshold_diamants', 150000)
    ever = False
    if hist is not None and not hist.empty:
        h = hist[hist['creator_id'] == row['creator_id']]
        if not h.empty and h['diamants'].max() >= thr: ever = True
    if not ever:
        stat = str(row.get('statut_diplome','')).lower()
        if 'confirmé' in stat: ever = True
    return 'confirmé' if ever else 'débutant'

def activity_ok(row, ctype, cfg):
    d = int(row.get('jours_live',0) or 0)
    h = float(row.get('heures_live',0) or 0.0)
    if ctype == 'débutant':
        need_d = cfg['activation']['beginner']['days']; need_h = cfg['activation']['beginner']['hours']
    else:
        need_d = cfg['activation']['confirmed']['days']; need_h = cfg['activation']['confirmed']['hours']
    ok1 = (d >= need_d) and (h >= need_h)
    ok2 = (d >= cfg['activation']['second']['days']) and (h >= cfg['activation']['second']['hours'])
    reason = []
    if not ok1:
        if d < need_d: reason.append('Pas assez de jours')
        if h < need_h: reason.append("Pas assez d'heures")
    return ok1, ok2, ', '.join(reason)

def beginner_bonus(row, ctype, cfg, hist):
    if ctype != 'débutant': return 0.0, ''
    amount = float(row['diamants'])
    if hist is not None and not hist.empty:
        h = hist[hist['creator_id'] == row['creator_id']]
        if 'bonus_code' in h.columns and h['bonus_code'].astype(str).str.len().max() > 0:
            return 0.0, ''
    for m in cfg['beginner_bonuses']['milestones']:
        if amount >= m['min'] and amount <= m['max']:
            return float(m['bonus']), m['code']
    return 0.0, ''

def compute_creators(df_norm, hist_norm, cfg):
    rows = []
    thr = cfg.get('confirmed_threshold_diamants',150000)
    for _, row in df_norm.iterrows():
        ctype = creator_type(row, hist_norm, cfg)
        ok1, ok2, why = activity_ok(row, ctype, cfg)
        amount = float(row['diamants'])
        requires_second = amount >= thr
        eligible_p1 = ok1 and (not requires_second or (requires_second and not ok2))
        eligible_p2 = ok2
        p1_val = select_fixed_reward(amount, P1_TABLE) if eligible_p1 else 0.0
        p2_val = select_fixed_reward(amount, P2_TABLE) if (requires_second and ok2) else 0.0
        if requires_second and ok2:
            p1_val = 0.0
        bval, bcode = beginner_bonus(row, ctype, cfg, hist_norm)
        eligible = (p1_val>0) or (p2_val>0)
        etat = '✅ Actif' if eligible else '⚠️ Inactif'
        reason = '' if eligible else (why if why else ('Second palier non validé (20j/80h)' if requires_second and not ok2 else ''))
        total = p1_val + p2_val + bval
        rows.append({
            'creator_id': row['creator_id'],
            'creator_username': row['creator_username'],
            'groupe': row['groupe'],
            'agent': row['agent'],
            'periode': row['periode'],
            'diamants': amount,
            'jours_live': int(row['jours_live']),
            'heures_live': float(row['heures_live']),
            'type_createur': ctype.capitalize(),
            'etat_activite': etat,
            'raison_ineligibilite': reason,
            'recompense_palier_1': p1_val,
            'recompense_palier_2': p2_val,
            'bonus_debutant': bval,
            'bonus_code': bcode,
            'total_createur': total
        })
    return pd.DataFrame(rows)
