# app_v7.py — app_v6 + filtrage par manager
import io, re, yaml, os, numpy as np, pandas as pd, streamlit as st
from math import floor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

st.set_page_config(page_title="Monsieur Darmon", layout="wide")

MD_ROLE = os.getenv("MD_ROLE", "")
MD_EMAIL = os.getenv("MD_EMAIL", "").lower()
MANAGER_GROUPS = st.secrets.get("MANAGER_GROUPS", {}) if hasattr(st, "secrets") else {}
ASSIGNED_GROUP = MANAGER_GROUPS.get(MD_EMAIL, "") if isinstance(MANAGER_GROUPS, dict) else ""

@st.cache_data(show_spinner=False)
def read_any(file_bytes: bytes, name: str) -> pd.DataFrame:
    bio = io.BytesIO(file_bytes); n = name.lower()
    if n.endswith((".xlsx", ".xls")): return pd.read_excel(bio)
    return pd.read_csv(bio)

def to_numeric_safe(x):
    if pd.isna(x): return 0.0
    s = str(x).strip().replace(" ", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def parse_duration_to_hours(x) -> float:
    if pd.isna(x): return 0.0
    s = str(x).strip().lower()
    try: return float(s.replace(",", "."))
    except: pass
    if re.match(r"^\d{1,2}:\d{1,2}(:\d{1,2})?$", s):
        h,m,*rest = [int(p) for p in s.split(":")]
        sec = rest[0] if rest else 0
        return h + m/60 + sec/3600
    h = re.search(r"(\\d+)\\s*h", s); m = re.search(r"(\\d+)\\s*m", s)
    if h or m:
        hh = int(h.group(1)) if h else 0; mm = int(m.group(1)) if m else 0
        return hh + mm/60
    mm = re.search(r"(\\d+)\\s*min", s)
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
    out["creator_id"] = df.get("ID créateur(trice)", out["creator_username"]).astype(str)
    for c in ["creator_username","groupe","agent","statut_diplome","periode"]:
        out[c] = out[c].astype(str)
    return out

THR_CONFIRMED = 150000
ACTIVITY = {"beginner":(7,15),"confirmed":(12,25),"second":(20,80)}
P1=[(35000,74999,1000),(75000,149999,2500),(150000,199999,5000),(200000,299999,6000),
    (300000,399999,7999),(400000,499999,12000),(500000,599999,15000),(600000,699999,18000),
    (700000,799999,21000),(800000,899999,24000),(900000,999999,26999),(1000000,1499999,30000),
    (1500000,1999999,44999),(2000000,None,"PCT4")]
P2=[(35000,74999,1000),(75000,149999,2500),(150000,199999,6000),(200000,299999,7999),
    (300000,399999,12000),(400000,499999,15000),(500000,599999,20000),(600000,699999,24000),
    (700000,799999,26999),(800000,899999,30000),(900000,999999,35000),(1000000,1499999,39999),
    (1500000,1999999,59999),(2000000,None,"PCT4")]
BONUS_CREATOR=[{"min":75000,"max":149999,"bonus":500,"code":"B1"},
               {"min":150000,"max":499999,"bonus":1088,"code":"B2"},
               {"min":500000,"max":2000000,"bonus":3000,"code":"B3"}]

def creator_type(row, hist):
    ever=False
    if hist is not None and not hist.empty:
        h=hist[hist["creator_id"]==row["creator_id"]]
        if not h.empty and h["diamants"].max()>=THR_CONFIRMED: ever=True
    if "confirmé" in str(row.get("statut_diplome","")).lower(): ever=True
    return "confirmé" if ever else "débutant"

def activity_ok(row, ctype):
    d=int(row.get("jours_live",0)); h=float(row.get("heures_live",0))
    need_d,need_h = ACTIVITY["beginner"] if ctype=="débutant" else ACTIVITY["confirmed"]
    ok1=(d>=need_d and h>=need_h)
    ok2=(d>=ACTIVITY["second"][0] and h>=ACTIVITY["second"][1])
    reason=[]
    if not ok1:
        if d<need_d: reason.append("Pas assez de jours")
        if h<need_h: reason.append("Pas assez d'heures")
    return ok1,ok2,", ".join(reason)

def reward(amount,table):
    for lo,hi,val in table:
        if (hi is None and amount>=lo) or (amount>=lo and amount<=hi):
            return round(amount*0.04,2) if val=="PCT4" else float(val)
    return 0.0

def eligible_beginner_status(statut: str) -> bool:
    s=(statut or "").lower()
    return ("débutant" in s) and (("non diplôm" in s) or ("90" in s))

def has_historical_bonus(hist: pd.DataFrame, creator_id: str) -> bool:
    if hist is None or hist.empty: return False
    h=hist[hist.get("creator_id","").astype(str)==str(creator_id)]
    if h.empty: return False
    if "bonus_code" in h.columns:
        codes=h["bonus_code"].astype(str).str.upper().tolist()
        return any(c in {"B1","B2","B3"} for c in codes)
    return False

def compute_creators(df,hist):
    rows=[]
    for _,r in df.iterrows():
        ctype=creator_type(r,hist)
        ok1,ok2,why=activity_ok(r,ctype)
        amount=float(r["diamants"])
        requires_second = amount>=THR_CONFIRMED
        p1 = reward(amount,P1) if ok1 and (not requires_second or (requires_second and not ok2)) else 0.0
        p2 = reward(amount,P2) if (requires_second and ok2) else 0.0
        if requires_second and ok2: p1=0.0
        bval,bcode=0.0,""
        if ctype=="débutant" and eligible_beginner_status(r.get("statut_diplome","")) and not has_historical_bonus(hist,r["creator_id"]):
            for b in BONUS_CREATOR:
                if amount>=b["min"] and amount<=b["max"]: bval,bcode=b["bonus"],b["code"]
        total=p1+p2+bval
        if amount>=2_000_000: total=float(np.floor(total/1000)*1000)
        etat="✅ Actif" if (p1>0 or p2>0) else "⚠️ Inactif"
        reason="" if etat=="✅ Actif" else why
        rows.append({"creator_id":r["creator_id"],"creator_username":r["creator_username"],"groupe":r["groupe"],"agent":r["agent"],
                     "periode":r["periode"],"diamants":amount,"jours_live":r["jours_live"],"heures_live":r["heures_live"],
                     "type_createur":ctype.capitalize(),"etat_activite":etat,"raison_ineligibilite":reason,
                     "recompense_palier_1":p1,"recompense_palier_2":p2,"bonus_debutant":bval,"bonus_code":bcode,"total_createur":total})
    return pd.DataFrame(rows)

def totals_active_by(field,crea):
    if crea is None or crea.empty: return pd.DataFrame(columns=[field,"diamants_actifs"])
    act=crea[crea["etat_activite"]=="✅ Actif"]
    return act.groupby(field)["diamants"].sum().reset_index().rename(columns={"diamants":"diamants_actifs"})

def percent_reward(total):
    if total>=4_000_000:return total*0.03
    if total>=200_000:return total*0.02
    return 0.0

def sum_bonus_for(group_col,crea,map_amount):
    if crea is None or crea.empty: return pd.DataFrame(columns=[group_col,"bonus_additionnel"])
    tmp=crea[["creator_id",group_col,"bonus_code"]].copy()
    order={"B3":3,"B2":2,"B1":1,"":0}
    tmp["rank"]=tmp["bonus_code"].astype(str).str.upper().map(order).fillna(0)
    tmp=tmp.sort_values(["creator_id","rank"],ascending=[True,False]).drop_duplicates("creator_id")
    tmp["bonus_amount"]=tmp["bonus_code"].astype(str).str.upper().map(map_amount).fillna(0)
    return tmp.groupby(group_col)["bonus_amount"].sum().reset_index().rename(columns={"bonus_amount":"bonus_additionnel"})

def compute_agents(crea):
    base=totals_active_by("agent",crea)
    if base.empty:return pd.DataFrame(columns=["agent","diamants_mois","base_prime","bonus_additionnel","prime_agent"])
    base["base_prime"]=base["diamants_actifs"].apply(percent_reward)
    b=sum_bonus_for("agent",crea,{"B2":1000,"B3":15000})
    out=base.merge(b,on="agent",how="left").fillna({"bonus_additionnel":0})
    out["prime_agent"]=out["base_prime"]+out["bonus_additionnel"]
    out["prime_agent"]=(np.floor(out["prime_agent"]/1000)*1000).astype(int)
    out.rename(columns={"diamants_actifs":"diamants_mois"},inplace=True)
    return out

def compute_managers(crea):
    base=totals_active_by("groupe",crea)
    if base.empty:return pd.DataFrame(columns=["groupe","diamants_mois","base_prime","bonus_additionnel","prime_manager"])
    base["base_prime"]=base["diamants_actifs"].apply(percent_reward)
    b=sum_bonus_for("groupe",crea,{"B2":1000,"B3":5000})
    out=base.merge(b,on="groupe",how="left").fillna({"bonus_additionnel":0})
    out["prime_manager"]=out["base_prime"]+out["bonus_additionnel"]
    out["prime_manager"]=(np.floor(out["prime_manager"]/1000)*1000).astype(int)
    out.rename(columns={"diamants_actifs":"diamants_mois"},inplace=True)
    return out

def make_pdf(title,df):
    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=landscape(A4),leftMargin=18,rightMargin=18,topMargin=18,bottomMargin=18)
    styles=getSampleStyleSheet()
    els=[Paragraph(title,styles["Title"]),Spacer(1,12)]
    data=[list(df.columns)]+df.astype(str).values.tolist()
    t=Table(data,repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.black),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("GRID",(0,0),(-1,-1),0.25,colors.grey),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.whitesmoke,colors.lightgrey])]))
    els.append(t); doc.build(els); buf.seek(0); return buf.read()

def safe_pdf(label,title,df,file):
    if df is None or df.empty: st.button(label,disabled=True)
    else: st.download_button(label,make_pdf(title,df),file,"application/pdf")

st.title("Monsieur Darmon")
st.caption("3 onglets indépendants • Filtrage automatique par rôle")

c1,c2,c3,c4=st.columns(4)
with c1:
    f_cur=st.file_uploader("Mois courant (XLSX/CSV)",type=["xlsx","xls","csv"],key="cur")
with c2:
    f_prev=st.file_uploader("Mois N-1 (historique)",type=["xlsx","xls","csv"],key="prev")
with c3:
    f_prev2=st.file_uploader("Mois N-2 (historique)",type=["xlsx","xls","csv"],key="prev2")
with c4:
    if st.button("Forcer relecture"):
        st.cache_data.clear(); st.rerun()

if f_cur:
    cur=normalize(read_any(f_cur.getvalue(),f_cur.name))
    hist=pd.DataFrame()
    if f_prev: hist=normalize(read_any(f_prev.getvalue(),f_prev.name))
    if f_prev2:
        hist2=normalize(read_any(f_prev2.getvalue(),f_prev2.name))
        hist=pd.concat([hist,hist2],ignore_index=True) if not hist.empty else hist2

    if MD_ROLE=="MANAGER":
        if ASSIGNED_GROUP:
            cur = cur[cur["groupe"]==ASSIGNED_GROUP]
        else:
            st.error("Aucun groupe assigné à votre email dans MANAGER_GROUPS."); st.stop()

    t1,t2,t3=st.tabs(["Créateurs","Agents","Managers"])

    with t1:
        crea=compute_creators(cur,hist)
        st.dataframe(crea,use_container_width=True)
        st.download_button("CSV Créateurs",crea.to_csv(index=False).encode("utf-8"),"recompenses_createurs.csv","text/csv")
        safe_pdf("PDF Créateurs","Récompenses Créateurs",crea,"recompenses_createurs.pdf")

    with t2:
        ag=compute_agents(crea)
        st.dataframe(ag,use_container_width=True)
        st.download_button("CSV Agents",ag.to_csv(index=False).encode("utf-8"),"recompenses_agents.csv","text/csv")
        safe_pdf("PDF Agents","Récompenses Agents",ag,"recompenses_agents.pdf")

    with t3:
        man=compute_managers(crea)
        st.dataframe(man,use_container_width=True)
        st.download_button("CSV Managers",man.to_csv(index=False).encode("utf-8"),"recompenses_managers.csv","text/csv")
        safe_pdf("PDF Managers","Récompenses Managers",man,"recompenses_managers.pdf")

st.markdown(\"\"\"
<style>
footer {visibility:hidden;} #MainMenu {visibility:hidden;}
.app-footer {position: fixed; left: 0; right: 0; bottom: 0;
padding: 6px 12px; text-align: center; background: rgba(0,0,0,0.05); font-size: 12px;}
</style>
<div class='app-footer'>logiciels récompense by tom Consulting & Event</div>
\"\"\", unsafe_allow_html=True)
