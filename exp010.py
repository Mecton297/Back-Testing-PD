import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-010 / V1.0", layout="centered")
st.title("🧪 EXP-010 / V1.0 — Structure par terme VIX/VIX3M")
st.caption("Backwardation (VIX/VIX3M ≥ 1.0) sur SPY — nouveau mécanisme, indépendant d'EXP-009")

TICKER_ASSET = "SPY"
TICKER_VIX = "^VIX"
TICKER_VIX3M = "^VIX3M"
SEUIL = 1.0
START = "2006-01-01"
END = "2026-01-01"

def compute_signal(vix_close, vix3m_close):
    ratio = vix_close / vix3m_close
    above = ratio >= SEUIL
    prev_below = ratio.shift(1) < SEUIL
    signal = (above & prev_below).fillna(False)
    return signal, ratio


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


st.write(f"**Univers verrouillé** : {TICKER_ASSET} (rendement) + {TICKER_VIX}/{TICKER_VIX3M} (signal)")
st.write(f"**Période** : {START} → {END}")
st.write(f"**Signal** : {TICKER_VIX}/{TICKER_VIX3M} ≥ {SEUIL}, franchissement strict (backwardation)")

if "exp010_log" not in st.session_state:
    st.session_state.exp010_log = None
    st.session_state.exp010_prices = None
    st.session_state.exp010_ratio = None

if st.button("Lancer EXP-010 / V1.0"):
    with st.spinner("Téléchargement des données..."):
        spy_raw = yf.Ticker(TICKER_ASSET).history(start=START, end=END, auto_adjust=False)
        spy_raw.columns = [c.lower() for c in spy_raw.columns]
        spy_raw.index = spy_raw.index.tz_localize(None)

        vix_raw = yf.Ticker(TICKER_VIX).history(start=START, end=END, auto_adjust=False)
        vix_raw.columns = [c.lower() for c in vix_raw.columns]
        vix_raw.index = vix_raw.index.tz_localize(None)

        vix3m_raw = yf.Ticker(TICKER_VIX3M).history(start=START, end=END, auto_adjust=False)
        vix3m_raw.columns = [c.lower() for c in vix3m_raw.columns]
        vix3m_raw.index = vix3m_raw.index.tz_localize(None)

    if spy_raw.empty or vix_raw.empty or vix3m_raw.empty:
        st.error(f"Téléchargement incomplet — SPY:{len(spy_raw)} VIX:{len(vix_raw)} VIX3M:{len(vix3m_raw)}")
        st.stop()

    st.write(f"SPY : {len(spy_raw)} séances")
    st.write(f"^VIX : {len(vix_raw)} séances, {vix_raw.index.min().date()} → {vix_raw.index.max().date()}")
    st.write(f"^VIX3M : {len(vix3m_raw)} séances, {vix3m_raw.index.min().date()} → {vix3m_raw.index.max().date()}")

    common = spy_raw.index.intersection(vix_raw.index).intersection(vix3m_raw.index)
    spy_close = spy_raw.loc[common, "close"]
    vix_close = vix_raw.loc[common, "close"]
    vix3m_close = vix3m_raw.loc[common, "close"]

    ev, ratio = compute_signal(vix_close, vix3m_close)

    st.subheader(f"Résultats — {TICKER_ASSET} suite à une backwardation VIX/VIX3M")
    st.caption(f"{len(common)} séances communes utilisées, {common.min().date()} → {common.max().date()}")

    rets, n_ev = forward_returns(spy_close, ev)
    st.write(f"Nombre total de signaux : **{n_ev}**")
    st.dataframe(summarize(rets), hide_index=True)

    log = build_event_log(spy_close, ev, TICKER_ASSET, "Backwardation_VIX3M")

    prices_out = spy_close.reset_index()
    prices_out.columns = ["date", "close"]
    prices_out["date"] = prices_out["date"].dt.strftime("%Y-%m-%d")
    prices_out["ticker"] = TICKER_ASSET

    st.session_state.exp010_log = log
    st.session_state.exp010_prices = prices_out

if st.session_state.exp010_log is not None:
    log = st.session_state.exp010_log
    prices_out = st.session_state.exp010_prices

    st.download_button(
        "⬇️ Télécharger le journal des signaux (CSV)",
        data=log.to_csv(index=False).encode("utf-8"),
        file_name="exp010_journal_SPY.csv",
        mime="text/csv",
        key="dl_journal",
    )
    st.download_button(
        "⬇️ Télécharger les prix quotidiens SPY (CSV)",
        data=prices_out.to_csv(index=False).encode("utf-8"),
        file_name="exp010_prix_SPY.csv",
        mime="text/csv",
        key="dl_prices",
    )

    st.markdown("### 📋 Alternative : copier-coller le texte brut")
    with st.expander("Voir le journal (CSV en texte)"):
        st.text_area("Journal", log.to_csv(index=False), height=300, key="txt_journal")
    with st.expander("Voir les prix (CSV en texte)"):
        st.text_area("Prix", prices_out.to_csv(index=False), height=300, key="txt_prices")

    with st.expander("🔒 Identification de l'expérience"):
        st.code(
            f"EXP-010 / V1.0 — Structure par terme VIX/VIX3M\n"
            f"Signal = VIX_t/VIX3M_t >= {SEUIL} ET VIX_(t-1)/VIX3M_(t-1) < {SEUIL} (franchissement)\n"
            f"Actif = {TICKER_ASSET}\n"
            f"Période = {START} à {END}\n"
            f"Blocs a analyser separement: 2006-2015 et 2016-2025\n"
            f"Aucune règle de sortie · Aucune optimisation post-résultats"
        )
