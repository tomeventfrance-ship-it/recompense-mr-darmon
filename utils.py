def compute_agents_table_from_creators(crea_table: pd.DataFrame) -> pd.DataFrame:
    """Agrège par Agent : diamants actifs/totaux, pertes, commission et bonus agent.
       Bonus agent : +1000 si un créateur atteint palier 2 ce mois, +15000 si palier 3 (pas cumulés)."""
    # Actifs = créateurs dont "Actif" == "Validé"
    active_mask = crea_table["Actif"].eq("Validé")

    g = crea_table.groupby("Agent", dropna=False)

    actives = g.apply(lambda x: x.loc[active_mask.reindex(x.index, fill_value=False), "Diamants"].sum()) \
               .rename("Diamants actifs")
    totals  = g["Diamants"].sum().rename("Diamants totaux")
    perte   = (totals - actives).astype(int)

    # Commission palierisée (identique à ta logique existante)
    def _agent_comm(sum_active: int) -> int:
        if sum_active < 200_000:
            return 0
        if sum_active < 4_000_000:
            return round(sum_active * 0.02)
        return round(sum_active * 0.03)

    commission = actives.apply(_agent_comm).astype(int)

    # Bonus agent : +1000 si palier 2, +15000 si palier 3 (par créateur, non cumulés)
    def _agent_bonus_block(df: pd.DataFrame) -> int:
        tiers = df["Palier bonus (1/2/3)"].fillna(0).astype(int)
        return int((tiers == 2).sum() * 1000 + (tiers == 3).sum() * 15000)

    bonus_agent = g.apply(_agent_bonus_block).rename("Bonus agent").astype(int)

    out = pd.concat(
        [actives.astype(int), totals.astype(int), perte,
         commission.rename("Commission").astype(int),
         bonus_agent],
        axis=1
    ).fillna(0)

    out["Récompense totale agent"] = (out["Commission"] + out["Bonus agent"]).astype(int)
    out = out.reset_index().sort_values(
        ["Diamants actifs", "Diamants totaux"], ascending=False
    ).reset_index(drop=True)
    return out


def compute_managers_table_from_creators(crea_table: pd.DataFrame) -> pd.DataFrame:
    """Agrège par Manager/Groupe : diamants actifs/totaux, pertes, commission et bonus manager.
       Bonus manager : +1000 si palier 2, +5000 si palier 3 (pas cumulés)."""
    active_mask = crea_table["Actif"].eq("Validé")

    g = crea_table.groupby("Groupe/Manager", dropna=False)

    actives = g.apply(lambda x: x.loc[active_mask.reindex(x.index, fill_value=False), "Diamants"].sum()) \
               .rename("Diamants actifs")
    totals  = g["Diamants"].sum().rename("Diamants totaux")
    perte   = (totals - actives).astype(int)

    # Commission identique à Agent (si tu as une règle différente, adapte ici)
    def _mgr_comm(sum_active: int) -> int:
        if sum_active < 200_000:
            return 0
        if sum_active < 4_000_000:
            return round(sum_active * 0.02)
        return round(sum_active * 0.03)

    commission = actives.apply(_mgr_comm).astype(int)

    # Bonus manager : +1000 si palier 2, +5000 si palier 3 (par créateur, non cumulés)
    def _mgr_bonus_block(df: pd.DataFrame) -> int:
        tiers = df["Palier bonus (1/2/3)"].fillna(0).astype(int)
        return int((tiers == 2).sum() * 1000 + (tiers == 3).sum() * 5000)

    bonus_mgr = g.apply(_mgr_bonus_block).rename("Bonus manager").astype(int)

    out = pd.concat(
        [actives.astype(int), totals.astype(int), perte,
         commission.rename("Commission").astype(int),
         bonus_mgr],
        axis=1
    ).fillna(0)

    out["Récompense totale manager"] = (out["Commission"] + out["Bonus manager"]).astype(int)
    out = out.reset_index().rename(columns={"Groupe/Manager": "Manager/Groupe"}) \
             .sort_values(["Diamants actifs", "Diamants totaux"], ascending=False) \
             .reset_index(drop=True)
    return out
