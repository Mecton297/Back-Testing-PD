import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-009B / V1.0", layout="centered")
st.title("🧪 EXP-009B / V1.0 — Réplication transversale du choc VIX")
st.caption("Même signal qu'EXP-009 (VIX choc +20% sur 5j), testé sur QQQ / IWM / EFA — aucun changement de paramètre")

TICKERS = ["QQQ", "IWM", "EFA"]
TICKER_VIX = "^VIX"
K = 5          # verrouillé, identique à EXP-009
SEUIL = 0.20   # verrouillé, identique à EXP-009
START = "2006-01-01"
END = "2026-01-01"

def compute_signal(vix_close):
    choc = vix_close / vix_close.shift(K) - 1
    above = choc >= SEUIL
    prev_below = choc.shift(1) < SEUIL
    signal = (above & prev_below).fillna(False)
    return signal


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


st.write(f"**Univers verrouillé** : {', '.join(TICKERS)} (rendements) + {TICKER_VIX} (signal, partagé)")
st.write(f"**Période** : {START} → {END}")
st.write(f"**Choc VIX** : VIX_t / VIX_(t-{K}) - 1 ≥ {int(SEUIL*100)}%, franchissement strict")

if "exp009b_combined" not in st.session_state:
    st.session_state.exp009b_combined = None
    st.session_state.exp009b_prices = None

if st.button("Lancer EXP-009B / V1.0"):
    with st.spinner("Téléchargement du VIX..."):
        vix_raw = yf.Ticker(TICKER_VIX).history(start=START, end=END, auto_adjust=False)
        vix_raw.columns = [c.lower() for c in vix_raw.columns]
        vix_raw.index = vix_raw.index.tz_localize(None)

    if vix_raw.empty:
        st.error("Téléchargement du VIX échoué.")
        st.stop()

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
            st.error(f"{ticker} : aucune donnée trouvée.")
            progress.progress((i + 1) / len(TICKERS))
            continue

        # Calendrier commun entre l'actif et le VIX
        common = raw.index.intersection(vix_raw.index)
        asset_close = raw.loc[common, "close"]
        vix_close = vix_raw.loc[common, "close"]

        ev = compute_signal(vix_close)

        rets, n_ev = forward_returns(asset_close, ev)
        with st.expander(f"📊 {ticker} — {n_ev} signaux"):
            st.write(f"{len(common)} séances communes, {common.min().date()} → {common.max().date()}")
            st.dataframe(summarize(rets), hide_index=True)

        log = build_event_log(asset_close, ev, ticker, "ChocVIX_k5_20pct")
        all_logs.append(log)

        prices_out = asset_close.reset_index()
        prices_out.columns = ["date", "close"]
        prices_out["date"] = prices_out["date"].dt.strftime("%Y-%m-%d")
        prices_out["ticker"] = ticker
        all_prices.append(prices_out)

        progress.progress((i + 1) / len(TICKERS))

    status.write("✅ Terminé.")

    if all_logs:
        combined = pd.concat(all_logs, ignore_index=True)
        prices_combined = pd.concat(all_prices, ignore_index=True)
        st.session_state.exp009b_combined = combined
        st.session_state.exp009b_prices = prices_combined

# --- Affichage des résultats et téléchargements, persistants entre les reruns ---
if st.session_state.exp009b_combined is not None:
    combined = st.session_state.exp009b_combined
    prices_combined = st.session_state.exp009b_prices

    st.success(f"{len(combined)} signaux au total sur {len(TICKERS)} actifs.")

    st.download_button(
        "⬇️ Télécharger le journal combiné (CSV)",
        data=combined.to_csv(index=False).encode("utf-8"),
        file_name="exp009b_journal_ALL.csv",
        mime="text/csv",
        key="dl_journal",
    )
    st.download_button(
        "⬇️ Télécharger les prix quotidiens combinés (CSV)",
        data=prices_combined.to_csv(index=False).encode("utf-8"),
        file_name="exp009b_prix_ALL.csv",
        mime="text/csv",
        key="dl_prices",
    )

    st.markdown("### 📋 Alternative : copier-coller le texte brut")
    st.caption("Si l'envoi de fichier ne fonctionne pas, sélectionne tout le texte ci-dessous et colle-le directement dans le chat.")
    with st.expander("Voir le journal (CSV en texte)"):
        st.text_area("Journal", combined.to_csv(index=False), height=300, key="txt_journal")
    with st.expander("Voir les prix (CSV en texte)"):
        st.text_area("Prix", prices_combined.to_csv(index=False), height=300, key="txt_prices")

    with st.expander("🔒 Identification de l'expérience"):
        st.code(
            f"EXP-009B / V1.0 — Réplication transversale du choc VIX\n"
            f"Signal identique à EXP-009 (VIX_t/VIX_(t-{K})-1 >= {SEUIL}, franchissement)\n"
            f"Actifs = {', '.join(TICKERS)}\n"
            f"Période = {START} à {END}\n"
            f"Aucune règle de sortie · Aucune optimisation post-résultats"
        )
