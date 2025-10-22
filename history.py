# -*- coding: utf-8 -*-
"""
history.py
----------
Gestion de l’historique “à vie” des créateurs :
- quels paliers débutant ont déjà été payés (b1/b2/b3)
- statut confirmé_150k (True si le créateur a déjà atteint 150k un mois)
- mémorisation d’infos utiles (première date de relation observée)

Utilisation typique :
    from history import (
        empty_history, load_history_from_uploaded, merge_histories,
        apply_updates_from_creators, to_csv_bytes
    )

1) Charger un historique existant (CSV optionnel) avec load_history_from_uploaded()
   sinon créer empty_history()
2) Après calcul du tableau créateurs (utils.compute_creators_table),
   appeler apply_updates_from_creators() pour mettre à jour l’historique.
3) Sauvegarder l’historique à jour : to_csv_bytes(updated_history)

Format CSV attendu/produit :
columns = [
  "username", "b1_used", "b2_used", "b3_used",
  "confirmed_150k", "first_relation_date"
]
"""

from __future__ import annotations
from typing import Optional, Tuple
import io
import pandas as pd

HISTORY_COLUMNS = [
    "username", "b1_used", "b2_used", "b3_used",
    "confirmed_150k", "first_relation_date"
]


def empty_history() -> pd.DataFrame:
    """Historique vide avec le schéma standard."""
    return pd.DataFrame(columns=HISTORY_COLUMNS)


def _coerce_bool(s: pd.Series) -> pd.Series:
    """Convertit en booléen tolérant True/False/1/0/yes/no…"""
    return s.astype(str).str.strip().str.lower().map(
        {"true": True, "1": True, "yes": True, "y": True, "t": True,
         "false": False, "0": False, "no": False, "n": False, "f": False}
    ).fillna(False)


def _normalize_history(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoie/force le schéma de l’historique."""
    base = df.copy()
    # Colonnes manquantes -> création
    for col in HISTORY_COLUMNS:
        if col not in base.columns:
            base[col] = None

    base = base[HISTORY_COLUMNS]
    base["username"] = base["username"].astype(str).str.strip()

    for bcol in ["b1_used", "b2_used", "b3_used", "confirmed_150k"]:
        base[bcol] = _coerce_bool(base[bcol])

    base["first_relation_date"] = pd.to_datetime(
        base["first_relation_date"], errors="coerce", utc=False
    )

    # Unicité par username (on garde la première ligne)
    base = base.drop_duplicates(subset=["username"], keep="first").reset_index(drop=True)
    return base


def load_history_from_uploaded(uploaded_file) -> pd.DataFrame:
    """
    Charge un CSV d’historique depuis un fichier streamlit (UploadedFile).
    Retourne un DataFrame normalisé (schéma HISTORY_COLUMNS).
    """
    if uploaded_file is None:
        return empty_history()

    name = getattr(uploaded_file, "name", "history.csv")
    if not name.lower().endswith(".csv"):
        # On tolère .xlsx (au cas où), mais on recommande CSV.
        data = uploaded_file.read()
        try:
            df = pd.read_excel(io.BytesIO(data))
        except Exception as e:
            raise ValueError(f"Historique : format non supporté ({name})") from e
    else:
        data = uploaded_file.read()
        df = pd.read_csv(io.BytesIO(data), encoding="utf-8")

    return _normalize_history(df)


def merge_histories(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """
    Fusionne deux historiques (priorité au plus “vrai” = True pour flags, plus ancienne date relation).
    """
    if old is None or old.empty:
        return _normalize_history(new if new is not None else empty_history())
    if new is None or new.empty:
        return _normalize_history(old)

    a = _normalize_history(old).set_index("username", drop=False)
    b = _normalize_history(new).set_index("username", drop=False)

    all_users = sorted(set(a.index) | set(b.index))
    rows = []
    for u in all_users:
        ra = a.loc[u] if u in a.index else None
        rb = b.loc[u] if u in b.index else None

        def pick_bool(col):
            va = bool(ra[col]) if ra is not None else False
            vb = bool(rb[col]) if rb is not None else False
            return va or vb

        def pick_date(col):
            da = ra[col] if (ra is not None) else pd.NaT
            db = rb[col] if (rb is not None) else pd.NaT
            # on garde la plus ANCIENNE connue
            if pd.isna(da):
                return db
            if pd.isna(db):
                return da
            return min(da, db)

        rows.append({
            "username": u,
            "b1_used": pick_bool("b1_used"),
            "b2_used": pick_bool("b2_used"),
            "b3_used": pick_bool("b3_used"),
            "confirmed_150k": pick_bool("confirmed_150k"),
            "first_relation_date": pick_date("first_relation_date"),
        })

    out = pd.DataFrame(rows)
    return _normalize_history(out)


def apply_updates_from_creators(
    creators_table: pd.DataFrame,
    history_df: Optional[pd.DataFrame]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Met à jour l’historique à partir du tableau créateurs (issu de utils.compute_creators_table).
    - Marque b1_used/b2_used/b3_used si “Code bonus payé” vaut b1/b2/b3
    - confirmed_150k si “Confirmé 150k” True
    - Enregistre first_relation_date si plus ancienne trouvée.

    Retourne (history_updated, delta_log)
      delta_log = petites lignes indiquant les changements effectués.
    """
    hist = _normalize_history(history_df if history_df is not None else empty_history())
    hist = hist.set_index("username", drop=False)

    logs = []
    for _, r in creators_table.iterrows():
        user = str(r.get("Nom d’utilisateur du/de la créateur(trice)","")).strip()
        if not user:
            continue

        code = r.get("Code bonus payé", None)  # b1/b2/b3/None
        confirmed = bool(r.get("Confirmé 150k", False))
        rel_date = r.get("Date d’établissement de la relation", pd.NaT)

        if user not in hist.index:
            hist.loc[user, "username"] = user
            hist.loc[user, ["b1_used","b2_used","b3_used","confirmed_150k"]] = [False, False, False, False]
            hist.loc[user, "first_relation_date"] = pd.NaT

        # Bonus consommé (une seule fois à vie)
        if code in ("b1","b2","b3"):
            col = f"{code}_used"
            if not bool(hist.loc[user, col]):
                hist.loc[user, col] = True
                logs.append({"username": user, "update": f"{col}=True"})

        # Confirmé 150k (à vie)
        if confirmed and not bool(hist.loc[user, "confirmed_150k"]):
            hist.loc[user, "confirmed_150k"] = True
            logs.append({"username": user, "update": "confirmed_150k=True"})

        # Première date de relation (garder la plus ancienne)
        try:
            rel_dt = pd.to_datetime(rel_date, errors="coerce", utc=False)
        except Exception:
            rel_dt = pd.NaT

        old_dt = hist.loc[user, "first_relation_date"]
        if pd.isna(old_dt) and not pd.isna(rel_dt):
            hist.loc[user, "first_relation_date"] = rel_dt
        elif (not pd.isna(old_dt)) and (not pd.isna(rel_dt)) and rel_dt < old_dt:
            hist.loc[user, "first_relation_date"] = rel_dt

    hist = hist.reset_index(drop=True)
    delta = pd.DataFrame(logs, columns=["username","update"])
    return _normalize_history(hist), delta


def to_csv_bytes(history_df: pd.DataFrame) -> bytes:
    """Export CSV (UTF-8) prêt pour un bouton de téléchargement Streamlit."""
    buf = io.StringIO()
    _normalize_history(history_df).to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")
