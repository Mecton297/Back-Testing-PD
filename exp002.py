import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-002 / V1.0", layout="centered")
st.title("🧪 EXP-002 / V1.0 — Donchian Breakout")
st.caption("Étude événementielle du signal de cassure Donchian — aucune règle de sortie, aucune optimisation")

# ================================================================
# Signal Donchian — formule verrouillée avant tout test
# Upper_t = max(High[t-1..t-N])  (aujourd'hui exclu, zéro look-ahead)
# Signal_t = Close_t > Upper_t  ET  Close_{t-1} <= Upper_{t-1}
# (franchissement strict, pas de re-déclenchement en cassure continue)
# ================================================================
def compute_donchian_signal(df, n=20):
    upper = df["high"].shift(1).rolling(n).max()
    breakout = df["close"] > upper
    prev_breakout = df["close"].shift(1) <= upper.shift(1)
    signal = (breakout & prev_breakout).fillna(False)
    out = df.copy()
    out["Upper"] = upper
    out["Signal_Donchian"] = signal
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
N = st.radio("Largeur du canal N (choisir selon l'expérience à générer)",
             options=[20, 55], format_func=lambda x: f"N={x} ({'EXP-002' if x==20 else 'EXP-002b'})")

if st.button("Lancer EXP-002 / V1.0 sur tous les symboles"):
    ticker_list = [t.strip() for t in tickers_text.splitlines() if t.strip()]
    all_logs = []
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

        data = compute_donchian_signal(raw[["high", "low", "close"]].copy(), n=N)
        ev = data["Signal_Donchian"]

        rets, n_ev = forward_returns(data["close"], ev)
        with st.expander(f"📊 {ticker} — {n_ev} signaux"):
            st.dataframe(summarize(rets), hide_index=True)

        subset_label = f"Donchian N{N}"
        log = build_event_log(data["close"], ev, ticker, subset_label)
        all_logs.append(log)

        progress.progress((i + 1) / len(ticker_list))

    status.write("✅ Terminé.")

    if all_logs:
        combined = pd.concat(all_logs, ignore_index=True)
        st.success(f"{len(combined)} signaux au total sur {len(ticker_list)} actifs.")

        st.info(
            "Aucune règle de sortie, aucun stop, aucun take-profit n'a été appliqué. "
            "Mesure brute de la valeur prédictive du signal d'entrée sur horizons fixes."
        )

        st.download_button(
            f"⬇️ Télécharger le journal combiné — tous les actifs, N={N} (CSV)",
            data=combined.to_csv(index=False).encode("utf-8"),
            file_name=f"exp002_journal_ALL_N{N}.csv",
            mime="text/csv",
        )

        with st.expander("🔒 Identification de l'expérience"):
            st.code(
                f"EXP-002{'b' if N==55 else ''} / V1.0 — Donchian Breakout\n"
                f"Upper_t = max(High[t-1..t-{N}]) · Signal = Close_t > Upper_t ET Close_(t-1) <= Upper_(t-1)\n"
                f"Actifs = {', '.join(ticker_list)}\n"
                f"N = {N} · Historique = {years} ans\n"
                f"Aucune règle de sortie · Aucune optimisation post-résultats"
            )
