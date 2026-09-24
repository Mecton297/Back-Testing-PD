import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-005 / V1.0", layout="centered")
st.title("🧪 EXP-005 / V1.0 — SMA200 (filtre) + Donchian 20 (déclencheur)")
st.caption("Architecture conditionnelle — aucune règle de sortie, aucune optimisation")

# ================================================================
# Filtre de régime : Close_t > SMA200_t (SMA200 inclut Close_t)
# Déclencheur : Donchian N=20, franchissement strict (identique EXP-002)
# Combinaison : déclencheur ET filtre actif le même jour
# ================================================================
def compute_signal(df, n_donchian=20, n_sma=200):
    sma200 = df["close"].rolling(n_sma).mean()
    regime_on = df["close"] > sma200

    upper = df["high"].shift(1).rolling(n_donchian).max()
    breakout = df["close"] > upper
    prev_breakout = df["close"].shift(1) <= upper.shift(1)
    donchian_signal = (breakout & prev_breakout).fillna(False)

    combined = (donchian_signal & regime_on).fillna(False)

    out = df.copy()
    out["SMA200"] = sma200
    out["RegimeOn"] = regime_on
    out["Donchian_signal"] = donchian_signal
    out["Signal_Combined"] = combined
    return out


def build_event_log(close, event_mask, ticker, subset_label, horizons=(5, 10, 20, 60)):
    event_mask = event_mask.reindex(close.index, fill_value=False)
    event_dates = close.index[event_mask]
    idx_map = {date: i for i, date in enumerate(close.index)}
    n = len(close)
    rows = []
    for d in event_dates:
        i = idx_map[d]
        row = {"date": d.strftime("%Y-%m-%d"), "ticker": ticker, "sous_ensemble": subset_label}
        for h in horizons:
            if i + h < n:
                row[f"ret_{h}"] = round((close.iloc[i + h] / close.iloc[i] - 1) * 100, 4)
            else:
                row[f"ret_{h}"] = None
        rows.append(row)
    return pd.DataFrame(rows)


def forward_returns(close, event_mask, horizons=(5, 10, 20, 60)):
    event_mask = event_mask.reindex(close.index, fill_value=False)
    event_dates = close.index[event_mask]
    idx_map = {date: i for i, date in enumerate(close.index)}
    n = len(close)
    results = {}
    for h in horizons:
        rets = []
        for d in event_dates:
            i = idx_map[d]
            if i + h < n:
                rets.append((close.iloc[i + h] / close.iloc[i] - 1) * 100)
        results[h] = pd.Series(rets, dtype=float)
    return results, len(event_dates)


def summarize(rets_dict):
    rows = []
    for h, rets in rets_dict.items():
        if len(rets) == 0:
            rows.append({"Horizon (séances)": h, "N exploitables": 0,
                         "Rendement moyen %": None, "Rendement médian %": None,
                         "% positifs": None, "Meilleur %": None, "Pire %": None,
                         "Écart-type %": None})
            continue
        rows.append({
            "Horizon (séances)": h, "N exploitables": len(rets),
            "Rendement moyen %": round(rets.mean(), 2),
            "Rendement médian %": round(rets.median(), 2),
            "% positifs": round((rets > 0).mean() * 100, 1),
            "Meilleur %": round(rets.max(), 2), "Pire %": round(rets.min(), 2),
            "Écart-type %": round(rets.std(), 2),
        })
    return pd.DataFrame(rows)


# ================================================================
# INTERFACE — traitement par lot des 8 actifs en une seule passe
# ================================================================
default_tickers = "XEG.TO\nXIT.TO\nTEC.TO\nXFN.TO\nXUT.TO\nSPY\nQQQ\nXIU.TO"
tickers_text = st.text_area("Symboles (un par ligne)", value=default_tickers, height=180)
years = st.slider("Historique à télécharger (années)", 5, 15, 10)

if st.button("Lancer EXP-005 / V1.0 sur tous les symboles"):
    ticker_list = [t.strip() for t in tickers_text.splitlines() if t.strip()]
    all_logs = []
    retention_rows = []
    progress = st.progress(0.0)
    status = st.empty()

    for i, ticker in enumerate(ticker_list):
        status.write(f"Traitement de **{ticker}**...")
        try:
            raw = yf.Ticker(ticker).history(period=f"{years}y", auto_adjust=False)
            raw.columns = [c.lower() for c in raw.columns]
            raw.index = raw.index.tz_localize(None)
        except Exception as e:
            st.error(f"{ticker} : échec du téléchargement ({e})")
            progress.progress((i + 1) / len(ticker_list))
            continue

        if raw.empty:
            st.error(f"{ticker} : aucune donnée trouvée.")
            progress.progress((i + 1) / len(ticker_list))
            continue

        data = compute_signal(raw[["high", "low", "close"]].copy())

        # Taux de rétention du filtre — statistique descriptive uniquement,
        # aucun rendement futur consulté ici.
        valid_regime = data["RegimeOn"].dropna()
        retention_pct = valid_regime.mean() * 100
        n_donchian_raw = int(data["Donchian_signal"].sum())
        n_combined_raw = int(data["Signal_Combined"].sum())
        retention_rows.append({
            "Ticker": ticker,
            "% jours Close>SMA200": round(retention_pct, 1),
            "Signaux Donchian bruts": n_donchian_raw,
            "Signaux combinés (filtrés)": n_combined_raw,
            "% signaux conservés": round(100 * n_combined_raw / n_donchian_raw, 1) if n_donchian_raw else None,
        })

        ev = data["Signal_Combined"]
        rets, n_ev = forward_returns(data["close"], ev)
        with st.expander(f"📊 {ticker} — {n_ev} signaux combinés"):
            st.dataframe(summarize(rets), hide_index=True)

        log = build_event_log(data["close"], ev, ticker, "SMA200+Donchian20")
        all_logs.append(log)

        progress.progress((i + 1) / len(ticker_list))

    status.write("✅ Terminé.")

    st.markdown("### 🔍 Taux de rétention du filtre (avant tout résultat de rendement)")
    st.dataframe(pd.DataFrame(retention_rows), hide_index=True)

    if all_logs:
        combined = pd.concat(all_logs, ignore_index=True)
        st.success(f"{len(combined)} signaux combinés au total sur {len(ticker_list)} actifs.")

        st.info(
            "Aucune règle de sortie, aucun stop, aucun take-profit n'a été appliqué. "
            "Mesure brute de la valeur prédictive du signal combiné sur horizons fixes."
        )

        st.download_button(
            "⬇️ Télécharger le journal combiné — tous les actifs (CSV)",
            data=combined.to_csv(index=False).encode("utf-8"),
            file_name="exp005_journal_ALL.csv",
            mime="text/csv",
        )

        with st.expander("🔒 Identification de l'expérience"):
            st.code(
                f"EXP-005 / V1.0 — Filtre SMA200 + Déclencheur Donchian N=20\n"
                f"Filtre = Close_t > SMA200_t (SMA200 inclut Close_t)\n"
                f"Déclencheur = Close_t > Upper_20_t ET Close_(t-1) <= Upper_20_(t-1)\n"
                f"Combiné = Déclencheur ET Filtre actif le même jour\n"
                f"Actifs = {', '.join(ticker_list)}\n"
                f"Historique = {years} ans\n"
                f"Aucune règle de sortie · Aucune optimisation post-résultats"
            )
