import io, re, yaml
from typing import Optional
import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

st.set_page_config(page_title="Récompenses TCE", layout="wide")

@st.cache_data(show_spinner=False)
def read_any(file) -> pd.DataFrame:
    name = file.name.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(file)
    return pd.read_csv(file)

def to_numeric_safe(x):
    if pd.isna(x):
        return 0.0
    s = str(x).strip().replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0

def parse_duration_to_hours(x) -> float:
    if pd.isna(x):
        return 0.0
    s = str(x).strip().lower()
    try:
        return float(s.replace(",", "."))
    except Exception:
        pass
    import re as _re
    if _re.match(r"^\d{1,2}:\d{1,2}(:\d{1,2})?$", s):
        parts = [int(p) for p in s.split(":")]
        h = parts[0]; m = parts[1] if len(parts)>1 else 0; sec = parts[2] if len(parts)>2 else 0
        return h + m/60 + sec/3600
    h = _re.search(r"(\d+)\s*h", s); m = _re.search(r"(\d+)\s*m", s)
    if h or m:
        hh = int(h.group(1)) if h else 0; mm = int(m.group(1)) if m else 0
        return hh + mm/60
    mm = _re.search(r"(\d+)\s*min", s)
    if mm: return int(mm.group(1))/60
    return 0.0

COLS = {
    "periode": "Période des données",
    "creator_username": "Nom d'utilisateur du/de la créateur(trice)",
    "groupe": "Groupe",
    "agent": "Agent",
    "date_relation": "Date d'établissement de la relation",
    "diamants": "Diamants",
    "duree_live": "Durée de LIVE",
    "jours_live": "Jours de passage en LIVE valides",
    "statut_diplome": "Statut du diplôme",
}

def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    for k, v in COLS.items():
        out[k] = df[v] if v in df.columns else (0 if k in ["diamants","jours_live"] else "")
    out["diamants"] = out["diamants"].apply(to_numeric_safe)
    out["jours_live"] = out["jours_live"].apply(lambda x: int(to_numeric_safe(x)))
    out["heures_live"] = df[COLS["duree_live"]].apply(parse_duration_to_hours) if COLS["duree_live"] in df.columns else 0.0
    if "ID créateur(trice)" in df.columns:
        out["creator_id"] = df["ID créateur(trice)"].astype(str)
    else:
        out["creator_id"] = out["creator_username"].astype(str)
    for c in ["creator_username","groupe","agent","statut_diplome","periode"]:
        out[c] = out[c].astype(str)
    return out

DEFAULT_CFG = {
    "activation": {
        "beginner": {"days": 7, "hours": 15},
        "confirmed": {"days": 12, "hours": 25},
        "second": {"days": 20, "hours": 80},
    },
    "confirmed_threshold_diamants": 150000,
    "beginner_bonuses": {
        "days_window": 90,
        "milestones": [
            {"min": 75000, "max": 149999, "bonus": 500, "code": "B1"},
            {"min": 150000, "max": 499999, "bonus": 1088, "code": "B2"},
            {"min": 500000, "max": 2000000, "bonus": 3000, "code": "B3"},
        ],
    },
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
    (2000000, None, "PCT4"),
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
    (2000000, None, "PCT4"),
]

def select_fixed_reward(amount: float, table):
    for lo, hi, val in table:
        if (hi is None and amount >= lo) or (amount >= lo and amount <= hi):
            return round(amount * 0.04, 2) if val == "PCT4" else float(val)
    return 0.0

def creator_type(row, hist, cfg):
    thr = cfg.get("confirmed_threshold_diamants", 150000)
    ever = False
    if hist is not None and not hist.empty:
        h = hist[hist["creator_id"] == row["creator_id"]]
        if not h.empty and h["diamants"].max() >= thr:
            ever = True
    if not ever:
        stat = str(row.get("statut_diplome","")).lower()
        if "confirmé" in stat:
            ever = True
    return "confirmé" if ever else "débutant"

def activity_ok(row, ctype, cfg):
    d = int(row.get("jours_live",0) or 0)
    h = float(row.get("heures_live",0) or 0.0)
    if ctype == "débutant":
        need_d = cfg["activation"]["beginner"]["days"]; need_h = cfg["activation"]["beginner"]["hours"]
    else:
        need_d = cfg["activation"]["confirmed"]["days"]; need_h = cfg["activation"]["confirmed"]["hours"]
    ok1 = (d >= need_d) and (h >= need_h)
    ok2 = (d >= cfg["activation"]["second"]["days"]) and (h >= cfg["activation"]["second"]["hours"])
    reason = []
    if not ok1:
        if d < need_d: reason.append("Pas assez de jours")
        if h < need_h: reason.append("Pas assez d'heures")
    return ok1, ok2, ", ".join(reason)

def beginner_bonus(row, ctype, cfg, hist):
    if ctype != "débutant":
        return 0.0, ""
    amount = float(row["diamants"])
    if hist is not None and not hist.empty:
        h = hist[hist["creator_id"] == row["creator_id"]]
        if "bonus_code" in h.columns and h["bonus_code"].astype(str).str.len().max() > 0:
            return 0.0, ""
    for m in cfg["beginner_bonuses"]["milestones"]:
        if amount >= m["min"] and amount <= m["max"]:
            return float(m["bonus"]), m["code"]
    return 0.0, ""

def compute_creators(df_norm, hist_norm, cfg):
    rows = []
    thr = cfg.get("confirmed_threshold_diamants",150000)
    for _, row in df_norm.iterrows():
        ctype = creator_type(row, hist_norm, cfg)
        ok1, ok2, why = activity_ok(row, ctype, cfg)
        amount = float(row["diamants"])

        requires_second = amount >= thr
        eligible_p1 = ok1 and (not requires_second or (requires_second and not ok2))
        p1_val = select_fixed_reward(amount, P1_TABLE) if eligible_p1 else 0.0

        p2_val = select_fixed_reward(amount, P2_TABLE) if (requires_second and ok2) else 0.0
        if requires_second and ok2:
            p1_val = 0.0

        bval, bcode = beginner_bonus(row, ctype, cfg, hist_norm)
        eligible = (p1_val>0) or (p2_val>0)
        etat = "✅ Actif" if eligible else "⚠️ Inactif"
        reason = "" if eligible else (why if why else ("Second palier non validé (20j/80h)" if requires_second and not ok2 else ""))

        total = p1_val + p2_val + bval
        rows.append({
            "creator_id": row["creator_id"],
            "creator_username": row["creator_username"],
            "groupe": row["groupe"],
            "agent": row["agent"],
            "periode": row["periode"],
            "diamants": amount,
            "jours_live": int(row["jours_live"]),
            "heures_live": float(row["heures_live"]),
            "type_createur": ctype.capitalize(),
            "etat_activite": etat,
            "raison_ineligibilite": reason,
            "recompense_palier_1": p1_val,
            "recompense_palier_2": p2_val,
            "bonus_debutant": bval,
            "bonus_code": bcode,
            "total_createur": total,
        })
    return pd.DataFrame(rows)

def totals_active_by(group_field: str, creators_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if creators_df is None or creators_df.empty:
        return pd.DataFrame(columns=[group_field, "diamants_actifs"])
    base = creators_df[creators_df["etat_activite"].eq("✅ Actif")]
    grp = base.groupby(group_field, dropna=False)["diamants"].sum().reset_index()
    grp.rename(columns={"diamants":"diamants_actifs"}, inplace=True)
    return grp

def percent_reward(total: float) -> float:
    if total >= 4000000: return total * 0.03
    if total >= 200000: return total * 0.02
    return 0.0

def agent_manager_bonus(crea_df: pd.DataFrame, group_field: str, b2_amt: float, b3_amt: float) -> pd.DataFrame:
    if crea_df is None or crea_df.empty:
        return pd.DataFrame(columns=[group_field,"bonus_additionnel"])
    tmp = crea_df.copy()
    tmp["b2"] = (tmp["bonus_code"]=="B2").astype(int)
    tmp["b3"] = (tmp["bonus_code"]=="B3").astype(int)
    agg = tmp.groupby(group_field)[["b2","b3"]].sum().reset_index()
    agg["bonus_additionnel"] = agg["b2"]*b2_amt + agg["b3"]*b3_amt
    return agg[[group_field,"bonus_additionnel"]]

def compute_agents(crea_cur):
    curr = totals_active_by("agent", crea_cur)
    if curr.empty:
        return pd.DataFrame(columns=["agent","diamants_mois","base_prime","bonus_additionnel","prime_agent"])
    df = curr.rename(columns={"diamants_actifs":"diamants_mois"}).copy()
    df["base_prime"] = df["diamants_mois"].apply(percent_reward)
    b = agent_manager_bonus(crea_cur, "agent", 1000, 15000)
    out = df.merge(b, on="agent", how="left").fillna({"bonus_additionnel":0})
    out["prime_agent"] = out["base_prime"] + out["bonus_additionnel"]
    return out[["agent","diamants_mois","base_prime","bonus_additionnel","prime_agent"]].sort_values("prime_agent", ascending=False)

def compute_managers(crea_cur):
    curr = totals_active_by("groupe", crea_cur)
    if curr.empty:
        return pd.DataFrame(columns=["groupe","diamants_mois","base_prime","bonus_additionnel","prime_manager"])
    df = curr.rename(columns={"diamants_actifs":"diamants_mois"}).copy()
    df["base_prime"] = df["diamants_mois"].apply(percent_reward)
    b = agent_manager_bonus(crea_cur, "groupe", 1000, 5000)
    out = df.merge(b, on="groupe", how="left").fillna({"bonus_additionnel":0})
    out["prime_manager"] = out["base_prime"] + out["bonus_additionnel"]
    return out[["groupe","diamants_mois","base_prime","bonus_additionnel","prime_manager"]].sort_values("prime_manager", ascending=False)

def make_pdf(title: str, df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    headers = list(df.columns)
    data = [headers] + df.astype(str).values.tolist()
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.black),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 9),
        ("FONTSIZE", (0,1), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey]),
    ]))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)
    return buf.read()

def safe_pdf_button(label, title, df, filename):
    if df is None or df.empty:
        st.button(label, disabled=True)
    else:
        pdf_bytes = make_pdf(title, df)
        st.download_button(label, pdf_bytes, filename, "application/pdf")

st.title("Logiciel Récompense Tom Consulting & Event")
st.caption("3 onglets indépendants • Base créateurs unique • Exports CSV & PDF")

col1, col2, col3 = st.columns(3)
with col1:
    f_current = st.file_uploader("Mois courant (XLSX/CSV)", type=["xlsx","xls","csv"], key="cur")
with col2:
    f_previous = st.file_uploader("Mois précédent = HISTORIQUE (optionnel)", type=["xlsx","xls","csv"], key="prev")
with col3:
    f_yaml = st.file_uploader("Seuils d’activité (YAML) — optionnel", type=["yml","yaml"], key="yaml")

cfg = DEFAULT_CFG.copy()
if f_yaml is not None:
    try:
        import yaml as _yaml
        cfg.update(_yaml.safe_load(f_yaml.read()) or {})
    except Exception:
        st.warning("YAML invalide. Seuils par défaut utilisés.")

if f_current is not None:
    raw_cur = read_any(f_current)
    norm_cur = normalize(raw_cur)
    hist_norm = normalize(read_any(f_previous)) if f_previous is not None else pd.DataFrame()

    tab_crea, tab_agents, tab_managers = st.tabs(["Créateurs", "Agents", "Managers"])

    with tab_crea:
        crea_df = compute_creators(norm_cur, hist_norm, cfg)
        st.subheader("Tableau créateurs")
        st.dataframe(crea_df, use_container_width=True)
        st.download_button("CSV Créateurs", crea_df.to_csv(index=False).encode("utf-8"),
                           "recompenses_createurs.csv", "text/csv")
        cols_pdf = ["creator_username","groupe","agent","periode","diamants",
                    "jours_live","heures_live","type_createur","etat_activite",
                    "recompense_palier_1","recompense_palier_2","bonus_debutant","total_createur"]
        safe_pdf_button("PDF Créateurs", "Récompenses Créateurs", crea_df[cols_pdf] if not crea_df.empty else crea_df,
                        "recompenses_createurs.pdf")

    with tab_agents:
        agents_df = compute_agents(crea_df)
        st.subheader("Tableau agents")
        st.dataframe(agents_df, use_container_width=True)
        st.download_button("CSV Agents", agents_df.to_csv(index=False).encode("utf-8"),
                           "recompenses_agents.csv", "text/csv")
        safe_pdf_button("PDF Agents", "Récompenses Agents", agents_df, "recompenses_agents.pdf")

    with tab_managers:
        man_df = compute_managers(crea_df)
        st.subheader("Tableau managers")
        st.dataframe(man_df, use_container_width=True)
        st.download_button("CSV Managers", man_df.to_csv(index=False).encode("utf-8"),
                           "recompenses_managers.csv", "text/csv")
        safe_pdf_button("PDF Managers", "Récompenses Managers", man_df, "recompenses_managers.pdf")
else:
    st.info("Charge le mois courant pour commencer.")
