import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-007A / V1.0", layout="centered")
st.title("🧪 EXP-007A / V1.0 — Réplication OOS temporelle")
st.caption("Pullback -5% en tendance établie, fenêtre 2001-2015, 6 actifs — signal strictement identique à EXP-006")

TICKERS = ["SPY", "QQQ", "XIU.TO", "XEG.TO", "XIT.TO", "XFN.TO"]
START = "2001-01-01"
END = "2016-01-01"
SEUIL = 0.05  # verrouillé, identique à EXP-006

# ================================================================
# Signal identique à EXP-006 V1.0 — aucune modification de paramètre
# ================================================================
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


# ================================================================
# INTERFACE — univers et période verrouillés, non modifiables
# ================================================================
st.write(f"**Univers verrouillé** : {', '.join(TICKERS)}")
st.write(f"**Période** : {START} → {END} (fenêtre non chevauchante avec EXP-006, 2016-2026)")
st.write(f"**Seuil de repli** : -{int(SEUIL*100)}% (identique à EXP-006 V1.0, aucune modification)")

if st.button("Lancer EXP-007A / V1.0"):
    all_logs = []
    all_prices = []
    progress = st.progress(0.0)
    status = st.empty()

    for i, ticker in enumerate(TICKERS):
        status.write(f"Traitement de **{ticker}**...")
        try:
            raw = yf.Ticker(ticker).history(start=START, end=END, auto_adjust=False)
            raw.columns = [c.lower() for c in raw.columns]
            raw.index = raw.index.tz_localize(None)
        except Exception as e:
            st.error(f"{ticker} : échec du téléchargement ({e})")
            progress.progress((i + 1) / len(TICKERS))
            continue

        if raw.empty:
            st.error(f"{ticker} : aucune donnée trouvée sur cette période.")
            progress.progress((i + 1) / len(TICKERS))
            continue

        st.write(f"{ticker} : {len(raw)} séances, du {raw.index.min().date()} au {raw.index.max().date()}")

        data = compute_signal(raw[["close"]].copy())
        ev = data["Signal_Combined"]

        rets, n_ev = forward_returns(data["close"], ev)
        with st.expander(f"📊 {ticker} — {n_ev} signaux"):
            st.dataframe(summarize(rets), hide_index=True)

        log = build_event_log(data["close"], ev, ticker, "Pullback5_OOS")
        all_logs.append(log)

        prices_out = data[["close"]].reset_index()
        prices_out.columns = ["date", "close"]
        prices_out["date"] = prices_out["date"].dt.strftime("%Y-%m-%d")
        prices_out["ticker"] = ticker
        all_prices.append(prices_out)

        progress.progress((i + 1) / len(TICKERS))

    status.write("✅ Terminé.")

    if all_logs:
        combined = pd.concat(all_logs, ignore_index=True)
        prices_combined = pd.concat(all_prices, ignore_index=True)

        st.success(f"{len(combined)} signaux au total sur {len(TICKERS)} actifs.")

        st.download_button(
            "⬇️ Télécharger le journal des signaux OOS (CSV)",
            data=combined.to_csv(index=False).encode("utf-8"),
            file_name="exp007a_journal_ALL.csv",
            mime="text/csv",
        )
        st.download_button(
            "⬇️ Télécharger les prix quotidiens OOS 2001-2016 (CSV)",
            data=prices_combined.to_csv(index=False).encode("utf-8"),
            file_name="exp007a_prix_ALL.csv",
            mime="text/csv",
        )

        with st.expander("🔒 Identification de l'expérience"):
            st.code(
                f"EXP-007A / V1.0 — Réplication OOS temporelle\n"
                f"Signal identique à EXP-006 V1.0 (Pullback -5%, filtre SMA200)\n"
                f"Univers = {', '.join(TICKERS)} (XUT.TO et TEC.TO exclus, historique insuffisant)\n"
                f"Période = {START} à {END}\n"
                f"Aucune règle de sortie · Aucune optimisation post-résultats"
            )
