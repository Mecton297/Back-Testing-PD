import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-013 / V1.0", layout="centered")
st.title("🧪 EXP-013 / V1.0 — Credit Spreads Stress Proxy (HYG/LQD)")
st.caption("Ratio HYG/LQD, choc sur 20j, deux seuils verrouillés a priori — SPY comme actif post-signal")

START = "2007-04-01"
END = "2026-01-01"
WINDOW = 20
SEUILS = [-3.0, -5.0]  # EXP-013a, EXP-013b — verrouillés

def compute_signal(ratio, seuil_pct):
    seuil = seuil_pct / 100
    shock = ratio / ratio.shift(WINDOW) - 1
    condition = shock <= seuil
    prev_condition = condition.shift(1).fillna(False).astype(bool)
    signal = condition & (~prev_condition)
    return signal.fillna(False), shock


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


st.write(f"**Formule** : Ratio_t = HYG_t / LQD_t · Choc_t = Ratio_t/Ratio_(t-20) - 1")
st.write(f"**Signal** : Choc_t ≤ Seuil ET Choc_(t-1) > Seuil (franchissement à la baisse)")
st.write(f"**Seuils verrouillés** : EXP-013a = {SEUILS[0]}% · EXP-013b = {SEUILS[1]}%")
st.write(f"**Actif post-signal** : SPY · **Période** : {START} → {END}")

if "exp013_data" not in st.session_state:
    st.session_state.exp013_data = None

if st.button("Lancer EXP-013 / V1.0"):
    with st.spinner("Téléchargement HYG, LQD, SPY..."):
        hyg = yf.Ticker("HYG").history(start=START, end=END, auto_adjust=False)
        hyg.columns = [c.lower() for c in hyg.columns]
        hyg.index = hyg.index.tz_localize(None)

        lqd = yf.Ticker("LQD").history(start=START, end=END, auto_adjust=False)
        lqd.columns = [c.lower() for c in lqd.columns]
        lqd.index = lqd.index.tz_localize(None)

        spy = yf.Ticker("SPY").history(start=START, end=END, auto_adjust=False)
        spy.columns = [c.lower() for c in spy.columns]
        spy.index = spy.index.tz_localize(None)

    if hyg.empty or lqd.empty or spy.empty:
        st.error("Téléchargement incomplet.")
        st.stop()

    common = hyg.index.intersection(lqd.index).intersection(spy.index)
    st.write(f"{len(common)} séances communes, {common.min().date()} → {common.max().date()}")

    ratio = hyg.loc[common, "close"] / lqd.loc[common, "close"]
    spy_close = spy.loc[common, "close"]

    all_logs = []
    for label, seuil in [("EXP-013a (S=-3.0%)", SEUILS[0]), ("EXP-013b (S=-5.0%)", SEUILS[1])]:
        ev, shock = compute_signal(ratio, seuil)
        rets, n_ev = forward_returns(spy_close, ev)
        with st.expander(f"📊 {label} — {n_ev} signaux"):
            st.dataframe(summarize(rets), hide_index=True)
        log = build_event_log(spy_close, ev, "SPY", label)
        all_logs.append(log)

    combined = pd.concat(all_logs, ignore_index=True)

    prices_out = spy_close.reset_index()
    prices_out.columns = ["date", "close"]
    prices_out["date"] = prices_out["date"].dt.strftime("%Y-%m-%d")
    prices_out["ticker"] = "SPY"

    st.session_state.exp013_data = {"journal": combined, "prices": prices_out}

if st.session_state.exp013_data is not None:
    d = st.session_state.exp013_data
    st.success(f"{len(d['journal'])} signaux au total (a+b combinés).")

    st.download_button(
        "⬇️ Télécharger le journal combiné (CSV)",
        data=d["journal"].to_csv(index=False).encode("utf-8"),
        file_name="exp013_journal_ALL.csv", mime="text/csv", key="dl_journal",
    )
    st.download_button(
        "⬇️ Télécharger les prix SPY (CSV)",
        data=d["prices"].to_csv(index=False).encode("utf-8"),
        file_name="exp013_prix_SPY.csv", mime="text/csv", key="dl_prices",
    )

    st.markdown("### 📋 Alternative : copier-coller le texte brut")
    with st.expander("Voir le journal (CSV en texte)"):
        st.text_area("Journal", d["journal"].to_csv(index=False), height=300, key="txt_journal")
    with st.expander("Voir les prix SPY (CSV en texte)"):
        st.text_area("Prix", d["prices"].to_csv(index=False), height=300, key="txt_prices")

    with st.expander("🔒 Identification de l'expérience"):
        st.code(
            f"EXP-013 / V1.0 — Credit Spreads Stress Proxy (HYG/LQD)\n"
            f"Ratio_t = HYG_t/LQD_t · Choc_t = Ratio_t/Ratio_(t-{WINDOW})-1\n"
            f"Signal = franchissement a la baisse (Choc_t <= S ET Choc_(t-1) > S)\n"
            f"Seuils S = {SEUILS} (verrouilles a priori, apres diagnostic neutre)\n"
            f"Actif post-signal = SPY · Période = {START} à {END}\n"
            f"Blocs a analyser separement: avril 2007-2015 et 2016-2026\n"
            f"Proxy de stress relatif du credit (pas une mesure directe du spread OAS)\n"
            f"Aucune règle de sortie · Aucune optimisation post-résultats"
        )
