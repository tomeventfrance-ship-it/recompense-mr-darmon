import pandas as pd

def compute_creators_table(df_source: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule les récompenses Créateurs uniquement à partir de :
    - Jours de passage en live (J)
    - Durée totale (heures)
    - Diamants générés
    """

    df = df_source.copy()

    # --- Vérification minimale ---
    required_cols = ["Diamants générés", "Durée totale (heures)", "Jours de passage en live"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Colonne manquante dans le fichier importé : '{col}'")

    # Conversion numérique
    df["Diamants générés"] = pd.to_numeric(df["Diamants générés"], errors="coerce").fillna(0)
    df["Durée totale (heures)"] = pd.to_numeric(df["Durée totale (heures)"], errors="coerce").fillna(0)
    df["Jours de passage en live"] = pd.to_numeric(df["Jours de passage en live"], errors="coerce").fillna(0)

    # --- Calcul des paliers ---
    df["Palier 1 atteint"] = df["Diamants générés"] >= 50_000
    df["Palier 2 atteint"] = df["Diamants générés"] >= 150_000

    # --- Récompense de base ---
    df["Récompense (base)"] = 0
    df.loc[df["Palier 1 atteint"], "Récompense (base)"] = 1_000
    df.loc[df["Palier 2 atteint"], "Récompense (base)"] = 3_000

    # --- Bonus basé sur le nombre de jours de live ---
    df["Bonus Jours Live"] = 0
    df.loc[df["Jours de passage en live"] >= 10, "Bonus Jours Live"] = 500

    # --- Bonus de durée ---
    df["Bonus Temps"] = 0
    df.loc[df["Durée totale (heures)"] >= 20, "Bonus Temps"] = 500

    # --- Total et statut final ---
    df["Total Récompense"] = df["Récompense (base)"] + df["Bonus Jours Live"] + df["Bonus Temps"]
    df["Statut"] = df["Total Récompense"].apply(lambda x: "Validé" if x > 0 else "Non validé")

    return df
