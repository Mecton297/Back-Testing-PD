import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Diagnostic HYG/LQD", layout="centered")
st.title("📐 Diagnostic neutre — Ratio HYG/LQD")
st.caption("Caractérisation de la distribution du choc sur 20 jours. Aucune donnée SPY, aucun rendement futur, aucun test de performance.")

START = "2007-04-01"
END = "2026-01-01"
WINDOW = 20

if st.button("Lancer le diagnostic"):
    with st.spinner("Téléchargement HYG et LQD..."):
        hyg = yf.Ticker("HYG").history(start=START, end=END, auto_adjust=False)
        hyg.columns = [c.lower() for c in hyg.columns]
        hyg.index = hyg.index.tz_localize(None)

        lqd = yf.Ticker("LQD").history(start=START, end=END, auto_adjust=False)
        lqd.columns = [c.lower() for c in lqd.columns]
        lqd.index = lqd.index.tz_localize(None)

    if hyg.empty or lqd.empty:
        st.error("Téléchargement échoué.")
        st.stop()

    st.write(f"HYG : {len(hyg)} séances, {hyg.index.min().date()} → {hyg.index.max().date()}")
    st.write(f"LQD : {len(lqd)} séances, {lqd.index.min().date()} → {lqd.index.max().date()}")

    common = hyg.index.intersection(lqd.index)
    ratio = hyg.loc[common, "close"] / lqd.loc[common, "close"]
    shock = ratio / ratio.shift(WINDOW) - 1
    shock = shock.dropna()

    st.subheader("Statistiques descriptives du choc (variation du ratio sur 20 séances)")
    st.write(f"**Nombre d'observations** : {len(shock)}")
    st.write(f"**Période couverte** : {common.min().date()} → {common.max().date()}")

    stats = {
        "Moyenne": shock.mean(),
        "Écart-type": shock.std(),
        "Minimum": shock.min(),
        "Maximum": shock.max(),
        "Percentile 1%": shock.quantile(0.01),
        "Percentile 2.5%": shock.quantile(0.025),
        "Percentile 5%": shock.quantile(0.05),
        "Percentile 10%": shock.quantile(0.10),
        "Percentile 25%": shock.quantile(0.25),
        "Médiane (50%)": shock.quantile(0.50),
        "Percentile 75%": shock.quantile(0.75),
        "Percentile 90%": shock.quantile(0.90),
        "Percentile 95%": shock.quantile(0.95),
    }
    stats_df = pd.DataFrame([{"Statistique": k, "Valeur (%)": round(v*100, 3)} for k, v in stats.items()])
    st.dataframe(stats_df, hide_index=True)

    st.subheader("Nombre d'observations sous différents seuils candidats (franchissement, pas juste 'sous le seuil')")
    candidats = [-1, -2, -3, -4, -5, -6, -7, -8, -10]
    rows = []
    for s in candidats:
        seuil = s / 100
        below = shock <= seuil
        prev_above = shock.shift(1) > seuil
        n_franchissements = (below & prev_above.fillna(False)).sum()
        n_jours_sous_seuil = below.sum()
        rows.append({"Seuil (%)": s, "Jours sous le seuil": int(n_jours_sous_seuil),
                     "Franchissements (événements)": int(n_franchissements)})
    st.dataframe(pd.DataFrame(rows), hide_index=True)

    st.subheader("Répartition temporelle brute (comptage par bloc, seuils candidats)")
    shockA = shock[shock.index <= "2015-12-31"]
    shockB = shock[shock.index >= "2016-01-01"]
    rows2 = []
    for s in candidats:
        seuil = s / 100
        belowA = shockA <= seuil
        prevA = shockA.shift(1) > seuil
        nA = (belowA & prevA.fillna(False)).sum()
        belowB = shockB <= seuil
        prevB = shockB.shift(1) > seuil
        nB = (belowB & prevB.fillna(False)).sum()
        rows2.append({"Seuil (%)": s, "Événements Bloc A (2007-2015)": int(nA),
                      "Événements Bloc B (2016-2025)": int(nB)})
    st.dataframe(pd.DataFrame(rows2), hide_index=True)

    with st.expander("🔒 Rappel du périmètre"):
        st.code(
            "Ce diagnostic ne contient aucune donnée SPY, aucun rendement futur,\n"
            "aucun test de permutation, aucune p-value. Il caractérise uniquement\n"
            "la distribution du signal candidat HYG/LQD, avant verrouillage des seuils."
        )
