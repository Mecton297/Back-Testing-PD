import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-014 Phase 0 — Diagnostic FX", layout="centered")
st.title("📐 EXP-014 Phase 0 — Diagnostic de faisabilité FX")
st.caption("Aucune variable cible, aucun rendement futur, aucun seuil de stratégie. Contrôle qualité des données uniquement.")

PAIRS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X"]
START = "2005-01-01"
END = "2026-01-01"

if st.button("Lancer le diagnostic FX"):
    raw_data = {}
    status = st.empty()
    progress = st.progress(0.0)

    for i, pair in enumerate(PAIRS):
        status.write(f"Téléchargement {pair}...")
        try:
            df = yf.Ticker(pair).history(start=START, end=END, auto_adjust=False)
            df.columns = [c.lower() for c in df.columns]
            df.index = df.index.tz_localize(None)
            if not df.empty:
                raw_data[pair] = df
        except Exception as e:
            st.error(f"{pair} : échec ({e})")
        progress.progress((i + 1) / len(PAIRS))

    status.write("✅ Téléchargements terminés.")

    if not raw_data:
        st.error("Aucune donnée récupérée.")
        st.stop()

    st.header("1-2. Première/dernière observation & nombre d'observations")
    rows_basic = []
    for pair, df in raw_data.items():
        rows_basic.append({
            "Paire": pair, "N observations": len(df),
            "Première date": df.index.min().date(), "Dernière date": df.index.max().date(),
        })
    st.dataframe(pd.DataFrame(rows_basic), hide_index=True)

    st.header("3-4. Doublons et dates dupliquées")
    rows_dup = []
    for pair, df in raw_data.items():
        n_dup_idx = df.index.duplicated().sum()
        n_dup_rows = df.duplicated().sum()
        rows_dup.append({"Paire": pair, "Dates dupliquées": int(n_dup_idx),
                          "Lignes entièrement dupliquées": int(n_dup_rows)})
    st.dataframe(pd.DataFrame(rows_dup), hide_index=True)

    st.header("5. Trous anormaux dans les jours de cotation")
    st.caption("FX cote ~24h/5j (dimanche soir à vendredi soir). On compare au calendrier des jours ouvrés (Mon-Ven) "
                "et on signale tout écart de plus de 3 jours calendaires consécutifs sans observation.")
    rows_gaps = []
    for pair, df in raw_data.items():
        dates = df.index.sort_values()
        deltas = dates.to_series().diff().dt.days.dropna()
        gaps_gt3 = deltas[deltas > 3]
        max_gap = int(deltas.max()) if len(deltas) else None
        max_gap_date = deltas.idxmax().strftime("%Y-%m-%d") if len(deltas) else None
        rows_gaps.append({
            "Paire": pair, "Écart max (jours calendaires)": max_gap,
            "Nb écarts > 3 jours": len(gaps_gt3),
            "Plus grand écart se termine le": max_gap_date
        })
    st.dataframe(pd.DataFrame(rows_gaps), hide_index=True)

    with st.expander("Détail des 10 plus grands écarts par paire"):
        for pair, df in raw_data.items():
            dates = df.index.sort_values()
            deltas = dates.to_series().diff().dt.days.dropna()
            top = deltas.sort_values(ascending=False).head(10)
            detail = pd.DataFrame({
                "Date (fin de l'écart)": [d.strftime("%Y-%m-%d") for d in top.index],
                "Écart (jours)": top.values.astype(int)
            })
            st.write(f"**{pair}**")
            st.dataframe(detail, hide_index=True)

    st.header("6. Valeurs nulles / négatives / manquantes")
    rows_null = []
    for pair, df in raw_data.items():
        n_null_close = df["close"].isna().sum()
        n_neg_close = (df["close"] <= 0).sum()
        rows_null.append({"Paire": pair, "Close NaN": int(n_null_close), "Close <= 0": int(n_neg_close)})
    st.dataframe(pd.DataFrame(rows_null), hide_index=True)

    st.header("7. Variations journalières aberrantes")
    st.caption("Rendement quotidien |>10%| signalé comme suspect pour une paire FX majeure (mouvement extrême, possible erreur de donnée).")
    rows_aberrant = []
    for pair, df in raw_data.items():
        ret = df["close"].pct_change().dropna()
        aberrant = ret[ret.abs() > 0.10]
        rows_aberrant.append({"Paire": pair, "N rendements |>10%|": len(aberrant),
                               "Max |rendement| observé (%)": round(ret.abs().max() * 100, 2) if len(ret) else None})
    st.dataframe(pd.DataFrame(rows_aberrant), hide_index=True)
    with st.expander("Détail des rendements aberrants (si présents)"):
        for pair, df in raw_data.items():
            ret = df["close"].pct_change().dropna()
            aberrant = ret[ret.abs() > 0.10]
            if len(aberrant) > 0:
                st.write(f"**{pair}**")
                st.dataframe(pd.DataFrame({"date": aberrant.index.strftime("%Y-%m-%d"),
                                            "rendement (%)": (aberrant.values * 100).round(2)}), hide_index=True)

    st.header("8. Fenêtre commune à toutes les paires")
    common_index = None
    for pair, df in raw_data.items():
        common_index = df.index if common_index is None else common_index.intersection(df.index)
    st.write(f"**Séances communes à toutes les paires** : {len(common_index)}")
    if len(common_index) > 0:
        st.write(f"**Période commune** : {common_index.min().date()} → {common_index.max().date()}")

    st.header("9. Corrélations entre paires (rendements quotidiens, fenêtre commune)")
    if len(common_index) > 10:
        ret_df = pd.DataFrame({pair: raw_data[pair].loc[common_index, "close"].pct_change()
                                for pair in raw_data})
        corr = ret_df.corr()
        st.dataframe(corr.round(3))
    else:
        st.warning("Fenêtre commune trop courte pour calculer les corrélations.")

    st.header("10. Statistiques descriptives des rendements quotidiens (par paire, historique complet)")
    rows_stats = []
    for pair, df in raw_data.items():
        ret = df["close"].pct_change().dropna() * 100
        rows_stats.append({
            "Paire": pair, "Moyenne (%)": round(ret.mean(), 4), "Écart-type (%)": round(ret.std(), 4),
            "Min (%)": round(ret.min(), 3), "Max (%)": round(ret.max(), 3),
            "Skewness": round(ret.skew(), 3), "Kurtosis": round(ret.kurt(), 3),
        })
    st.dataframe(pd.DataFrame(rows_stats), hide_index=True)

    with st.expander("🔒 Rappel du périmètre"):
        st.code(
            "EXP-014 Phase 0 — Diagnostic de faisabilité FX\n"
            "Aucune variable cible, aucun rendement futur, aucun seuil de signal,\n"
            "aucun test de permutation, aucune p-value.\n"
            "Objectif unique : qualifier les données disponibles avant tout verrouillage de protocole."
        )
