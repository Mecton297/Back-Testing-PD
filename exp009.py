import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-009 / V1.0", layout="centered")
st.title("🧪 EXP-009 / V1.0 — Choc de VIX sur SPY")
st.caption("Choc relatif du VIX (+20% sur 5 séances) → rendement futur de SPY — aucune règle de sortie, aucune optimisation")

TICKER_ASSET = "SPY"
TICKER_VIX = "^VIX"
K = 5          # verrouillé
SEUIL = 0.20   # verrouillé
START = "2006-01-01"
END = "2026-01-01"

# ================================================================
# Choc VIX relatif, franchissement strict — formule verrouillée
# Choc_t = VIX_t / VIX_(t-k) - 1
# Signal_t = Choc_t >= seuil ET Choc_(t-1) < seuil
# Rendement mesuré sur SPY, pas sur le VIX
# ================================================================
def compute_signal(spy_close, vix_close, k=K, seuil=SEUIL):
    choc = vix_close / vix_close.shift(k) - 1
    above = choc >= seuil
    prev_below = choc.shift(1) < seuil
    signal = (above & prev_below).fillna(False)
    df = pd.DataFrame({"close": spy_close, "vix": vix_close, "choc_vix": choc, "Signal": signal})
    return df


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


st.write(f"**Univers verrouillé** : {TICKER_ASSET} (rendement mesuré) + {TICKER_VIX} (signal)")
st.write(f"**Période** : {START} → {END}")
st.write(f"**Choc** : VIX_t / VIX_(t-{K}) - 1 ≥ {int(SEUIL*100)}%, franchissement strict")

if st.button("Lancer EXP-009 / V1.0"):
    with st.spinner("Téléchargement des données..."):
        spy_raw = yf.Ticker(TICKER_ASSET).history(start=START, end=END, auto_adjust=False)
        spy_raw.columns = [c.lower() for c in spy_raw.columns]
        spy_raw.index = spy_raw.index.tz_localize(None)

        vix_raw = yf.Ticker(TICKER_VIX).history(start=START, end=END, auto_adjust=False)
        vix_raw.columns = [c.lower() for c in vix_raw.columns]
        vix_raw.index = vix_raw.index.tz_localize(None)

    if spy_raw.empty or vix_raw.empty:
        st.error("Téléchargement incomplet (SPY ou VIX vide).")
        st.stop()

    st.write(f"SPY : {len(spy_raw)} séances, {spy_raw.index.min().date()} → {spy_raw.index.max().date()}")
    st.write(f"^VIX : {len(vix_raw)} séances, {vix_raw.index.min().date()} → {vix_raw.index.max().date()}")

    # Alignement sur le calendrier commun
    common = spy_raw.index.intersection(vix_raw.index)
    spy_close = spy_raw.loc[common, "close"]
    vix_close = vix_raw.loc[common, "close"]

    data = compute_signal(spy_close, vix_close)
    ev = data["Signal"]

    st.subheader(f"Résultats — {TICKER_ASSET} (rendement) suite à un choc de {TICKER_VIX}")
    st.caption(f"{len(common)} séances communes utilisées")

    rets, n_ev = forward_returns(data["close"], ev)
    st.write(f"Nombre total de signaux : **{n_ev}**")
    st.dataframe(summarize(rets), hide_index=True)

    st.info(
        "Aucune règle de sortie, aucun stop, aucun take-profit n'a été appliqué. "
        "Mesure brute de la valeur prédictive du choc de VIX sur le rendement futur de SPY."
    )

    log = build_event_log(data["close"], ev, TICKER_ASSET, "ChocVIX_k5_20pct")

    st.download_button(
        "⬇️ Télécharger le journal des signaux (CSV)",
        data=log.to_csv(index=False).encode("utf-8"),
        file_name="exp009_journal_SPY.csv",
        mime="text/csv",
    )

    prices_out = data[["close"]].reset_index()
    prices_out.columns = ["date", "close"]
    prices_out["date"] = prices_out["date"].dt.strftime("%Y-%m-%d")
    prices_out["ticker"] = TICKER_ASSET

    st.download_button(
        "⬇️ Télécharger les prix quotidiens SPY (CSV)",
        data=prices_out.to_csv(index=False).encode("utf-8"),
        file_name="exp009_prix_SPY.csv",
        mime="text/csv",
    )

    with st.expander("🔒 Identification de l'expérience"):
        st.code(
            f"EXP-009 / V1.0 — Choc de VIX sur SPY\n"
            f"Choc_t = VIX_t / VIX_(t-{K}) - 1\n"
            f"Signal = Choc_t >= {SEUIL} ET Choc_(t-1) < {SEUIL} (franchissement strict)\n"
            f"Rendement mesuré sur SPY, aucun filtre de régime\n"
            f"Période = {START} à {END}\n"
            f"Aucune règle de sortie · Aucune optimisation post-résultats"
        )
