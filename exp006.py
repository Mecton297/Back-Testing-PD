import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-006 / V1.0", layout="centered")
st.title("🧪 EXP-006 / V1.0 — Pullback en tendance établie")
st.caption("Filtre SMA200 + retracement de prix — aucune règle de sortie, aucune optimisation")

# ================================================================
# Filtre de régime : Close_t > SMA200_t (SMA200 inclut Close_t)
# Repli : D_t = Close_t / max(Close_t-1..t-20) - 1  (sommet exclut Close_t)
# Déclencheur : franchissement D_t > -seuil ET D_(t-1) <= -seuil
# Combiné : déclencheur ET filtre actif le même jour
# ================================================================
def compute_signal(df, seuil, n_sma=200, n_retr=20):
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
    out["RegimeOn"] = regime_on
    out["Trigger"] = trigger
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
seuil_pct = st.radio("Seuil de repli (choisir selon l'expérience à générer)",
                      options=[5, 10], format_func=lambda x: f"-{x}% ({'EXP-006' if x==5 else 'EXP-006b'})")
seuil = seuil_pct / 100

if st.button("Lancer EXP-006 / V1.0 sur tous les symboles"):
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

        data = compute_signal(raw[["close"]].copy(), seuil=seuil)

        n_trigger_raw = int(data["Trigger"].sum())
        n_combined_raw = int(data["Signal_Combined"].sum())
        retention_rows.append({
            "Ticker": ticker,
            "Déclencheurs bruts (repli seul)": n_trigger_raw,
            "Signaux combinés (filtrés)": n_combined_raw,
            "% conservés": round(100 * n_combined_raw / n_trigger_raw, 1) if n_trigger_raw else None,
        })

        ev = data["Signal_Combined"]
        rets, n_ev = forward_returns(data["close"], ev)
        with st.expander(f"📊 {ticker} — {n_ev} signaux combinés"):
            st.dataframe(summarize(rets), hide_index=True)

        subset_label = f"Pullback{seuil_pct}"
        log = build_event_log(data["close"], ev, ticker, subset_label)
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
            f"⬇️ Télécharger le journal combiné — seuil -{seuil_pct}% (CSV)",
            data=combined.to_csv(index=False).encode("utf-8"),
            file_name=f"exp006_journal_ALL_{seuil_pct}pct.csv",
            mime="text/csv",
        )

        with st.expander("🔒 Identification de l'expérience"):
            st.code(
                f"EXP-006{'b' if seuil_pct==10 else ''} / V1.0 — Pullback en tendance établie\n"
                f"Filtre = Close_t > SMA200_t (inclut Close_t)\n"
                f"UpperClose_t = max(Close_(t-1)..Close_(t-20)) (exclut Close_t)\n"
                f"D_t = Close_t / UpperClose_t - 1\n"
                f"Déclencheur = D_t > -{seuil_pct}% ET D_(t-1) <= -{seuil_pct}%\n"
                f"Combiné = Déclencheur ET Filtre actif le même jour\n"
                f"Actifs = {', '.join(ticker_list)}\n"
                f"Historique = {years} ans\n"
                f"Aucune règle de sortie · Aucune optimisation post-résultats"
            )
