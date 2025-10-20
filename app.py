import streamlit as st
import pandas as pd

st.set_page_config(page_title="Logiciel Récompense - Tom Consulting & Event", layout="wide")

st.title("💎 Logiciel Récompense Tom Consulting & Event")
st.markdown("Automatisation des récompenses pour **Créateurs**, **Agents** et **Managers**.")

uploaded_file = st.file_uploader("📂 Importez votre fichier Excel (.xlsx ou .csv)", type=["xlsx", "csv"])

if uploaded_file:
    # Lecture du fichier
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.success("✅ Fichier importé avec succès !")

    # --- Nettoyage des colonnes utiles ---
    colonnes_conservees = ["Nom", "Diamants", "Durée de LIVE", "Jours de passage en LIVE valides",
                           "Statut du diplôme", "Agent", "Groupe"]
    df = df[[c for c in colonnes_conservees if c in df.columns]]

    # --- Détermination de l’activité du créateur ---
    def est_actif(row):
        if row["Diamants"] >= 150000 or row["Statut du diplôme"] == "Confirmé":
            return row["Durée de LIVE"] >= 25 and row["Jours de passage en LIVE valides"] >= 12
        return row["Durée de LIVE"] >= 15 and row["Jours de passage en LIVE valides"] >= 7

    df["Actif"] = df.apply(est_actif, axis=1)

    # --- Palier 2 ---
    df["Palier 2"] = df.apply(lambda x: "Validé" if x["Durée de LIVE"] >= 80 and x["Jours de passage en LIVE valides"] >= 20 else "Non validé", axis=1)

    # --- Récompenses Palier 1 ---
    def recompense_palier1(diamants):
        if diamants < 35000: return 0
        elif diamants < 75000: return 1000
        elif diamants < 150000: return 2500
        elif diamants < 200000: return 5000
        elif diamants < 300000: return 6000
        elif diamants < 400000: return 7999
        elif diamants < 500000: return 12000
        elif diamants < 600000: return 15000
        elif diamants < 700000: return 18000
        elif diamants < 800000: return 21000
        elif diamants < 900000: return 24000
        elif diamants < 1000000: return 26999
        elif diamants < 1500000: return 30000
        elif diamants < 2000000: return 44999
        else: return diamants * 0.04

    # --- Récompenses Palier 2 ---
    def recompense_palier2(diamants):
        if diamants < 35000: return 0
        elif diamants < 75000: return 1000
        elif diamants < 150000: return 2500
        elif diamants < 200000: return 6000
        elif diamants < 300000: return 7999
        elif diamants < 400000: return 12000
        elif diamants < 500000: return 15000
        elif diamants < 600000: return 20000
        elif diamants < 700000: return 24000
        elif diamants < 800000: return 26999
        elif diamants < 900000: return 30000
        elif diamants < 1000000: return 35000
        elif diamants < 1500000: return 39999
        elif diamants < 2000000: return 59999
        else: return diamants * 0.04

    # Application des récompenses
    df["Récompense Palier 1"] = df["Diamants"].apply(recompense_palier1)
    df["Récompense Palier 2"] = df["Diamants"].apply(recompense_palier2)

    # --- Bonus Débutant ---
    def bonus_debutant(row):
        if row["Statut du diplôme"] != "Débutant": return "Non validé"
        if row["Diamants"] >= 500000: return "Validé - Bonus 3"
        elif row["Diamants"] >= 150000: return "Validé - Bonus 2"
        elif row["Diamants"] >= 75000: return "Validé - Bonus 1"
        return "Non validé"

    df["Bonus débutant"] = df.apply(bonus_debutant, axis=1)

    # --- Récompense totale ---
    def total(row):
        total = row["Récompense Palier 2"] if row["Palier 2"] == "Validé" else row["Récompense Palier 1"]
        if "Bonus" in row["Bonus débutant"]:
            if "Bonus 1" in row["Bonus débutant"]: total += 500
            elif "Bonus 2" in row["Bonus débutant"]: total += 1088
            elif "Bonus 3" in row["Bonus débutant"]: total += 3000
        return int(total)

    df["Récompense totale"] = df.apply(total, axis=1)

    # --- Résultats ---
    st.subheader("📊 Tableau des créateurs (avec calculs automatiques)")
    st.dataframe(df, use_container_width=True)

    # --- Export ---
    st.download_button("📥 Télécharger le tableau (Excel)", df.to_csv(index=False).encode('utf-8'), "Récompense_Créateurs.csv", "text/csv")

else:
    st.info("⬆️ Importez votre fichier pour commencer le calcul automatique.")
