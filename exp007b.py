import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-007B / V1.0", layout="centered")
st.title("🧪 EXP-007B / V1.0 — Réplication transversale")
st.caption("Pullback -5% en tendance établie, 21 actifs diversifiés, 2016-2026 — signal strictement identique à EXP-006")

TICKERS = [
    "IWM", "EFA", "EEM", "XIC.TO",
    "XLV", "XLI", "XLP", "XLY", "XLE", "XLB", "XLU",
    "MTUM", "VLUE", "USMV",
    "TLT", "IEF", "HYG", "XBB.TO",
    "GLD", "SLV", "USO",
    "EWJ", "EWG", "EWC", "XMD.TO",
]
SEUIL = 0.05  # verrouillé, identique à EXP-006

def compute_signal(df, seuil=SEUIL, n_sma=200, n_retr=20):
    sma200 = df["close"].rolling(n_sma).mean()
    regime_on = df["close"] > sma200
    upper_close = df["close"].shift(1).rolling(n_retr).max()
    D = df["close"] / upper_close - 1
    breakout = D > -seuil
    prev_below = D.shift(1) <= -seuil
    trigger = (breakout & prev_below).fillna(False)
    combined = (trigger & regime_on).fillna(False)
    out = df.copy()
    out["SMA200"] = sma200
    out["D"] = D
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


st.write(f"**Univers verrouillé** : {len(TICKERS)} actifs — {', '.join(TICKERS)}")
years = st.slider("Historique à télécharger (années)", 5, 15, 10)

if st.button("Lancer EXP-007B / V1.0"):
    all_logs = []
    all_prices = []
    coverage_rows = []
    progress = st.progress(0.0)
    status = st.empty()

    for i, ticker in enumerate(TICKERS):
        status.write(f"Traitement de **{ticker}**...")
        try:
            raw = yf.Ticker(ticker).history(period=f"{years}y", auto_adjust=False)
            raw.columns = [c.lower() for c in raw.columns]
            raw.index = raw.index.tz_localize(None)
        except Exception as e:
            st.error(f"{ticker} : échec du téléchargement ({e})")
            coverage_rows.append({"Ticker": ticker, "Séances": 0, "Début": None, "Fin": None, "SMA200 valide": False})
            progress.progress((i + 1) / len(TICKERS))
            continue

        if raw.empty:
            st.error(f"{ticker} : aucune donnée trouvée.")
            coverage_rows.append({"Ticker": ticker, "Séances": 0, "Début": None, "Fin": None, "SMA200 valide": False})
            progress.progress((i + 1) / len(TICKERS))
            continue

        sma200_valide = len(raw) >= 200
        coverage_rows.append({
            "Ticker": ticker, "Séances": len(raw),
            "Début": raw.index.min().date().isoformat(),
            "Fin": raw.index.max().date().isoformat(),
            "SMA200 valide": sma200_valide,
        })

        data = compute_signal(raw[["close"]].copy())
        ev = data["Signal_Combined"]

        rets, n_ev = forward_returns(data["close"], ev)
        with st.expander(f"📊 {ticker} — {n_ev} signaux"):
            st.dataframe(summarize(rets), hide_index=True)

        log = build_event_log(data["close"], ev, ticker, "Pullback5_Transversal")
        all_logs.append(log)

        prices_out = data[["close"]].reset_index()
        prices_out.columns = ["date", "close"]
        prices_out["date"] = prices_out["date"].dt.strftime("%Y-%m-%d")
        prices_out["ticker"] = ticker
        all_prices.append(prices_out)

        progress.progress((i + 1) / len(TICKERS))

    status.write("✅ Terminé.")

    st.markdown("### 🔍 Couverture des données par actif (documentée avant les résultats)")
    st.dataframe(pd.DataFrame(coverage_rows), hide_index=True)

    if all_logs:
        combined = pd.concat(all_logs, ignore_index=True)
        prices_combined = pd.concat(all_prices, ignore_index=True)
        st.success(f"{len(combined)} signaux au total sur {len(TICKERS)} actifs.")

        st.download_button(
            "⬇️ Télécharger le journal combiné — 21 actifs (CSV)",
            data=combined.to_csv(index=False).encode("utf-8"),
            file_name="exp007b_journal_ALL.csv",
            mime="text/csv",
        )
        st.download_button(
            "⬇️ Télécharger les prix quotidiens — 21 actifs (CSV)",
            data=prices_combined.to_csv(index=False).encode("utf-8"),
            file_name="exp007b_prix_ALL.csv",
            mime="text/csv",
        )

        with st.expander("🔒 Identification de l'expérience"):
            st.code(
                f"EXP-007B / V1.0 — Réplication transversale\n"
                f"Signal identique à EXP-006 V1.0 (Pullback -5%, filtre SMA200)\n"
                f"Univers = {len(TICKERS)} actifs : {', '.join(TICKERS)}\n"
                f"Historique = {years} ans\n"
                f"Aucune règle de sortie · Aucune optimisation post-résultats"
            )
