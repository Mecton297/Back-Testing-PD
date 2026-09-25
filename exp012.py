import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-012 / V1.0", layout="centered")
st.title("🧪 EXP-012 / V1.0 — Volume Climax (SPY)")
st.caption("Capitulation par pic de volume + rendement négatif — deux seuils pré-enregistrés, aucun filtre de régime")

TICKER = "SPY"
START = "2006-01-01"
END = "2026-01-01"
VOL_WINDOW = 20
RET_SEUIL = -0.02
SEUILS_VOL = [2.0, 2.5]  # EXP-012a et EXP-012b

def compute_signal(df, seuil_vol, ret_seuil=RET_SEUIL, window=VOL_WINDOW):
    sma_vol = df["volume"].shift(1).rolling(window).mean()  # jour t exclu
    ratio = df["volume"] / sma_vol
    rendement = df["close"].pct_change()

    condition = (ratio >= seuil_vol) & (rendement <= ret_seuil)
    prev_condition = condition.shift(1).fillna(False).astype(bool)
    signal = condition & (~prev_condition)
    return signal.fillna(False), ratio, rendement


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


st.write(f"**Actif** : {TICKER} · **Période** : {START} → {END}")
st.write(f"**Signal** : Volume_t / SMA20(Volume, t-1..t-20) ≥ S ET Rendement_t ≤ {RET_SEUIL*100:.0f}%, franchissement")
st.write(f"**Seuils pré-enregistrés** : S={SEUILS_VOL[0]} (EXP-012a) et S={SEUILS_VOL[1]} (EXP-012b)")

if "exp012_data" not in st.session_state:
    st.session_state.exp012_data = None

if st.button("Lancer EXP-012 / V1.0"):
    with st.spinner("Téléchargement des données..."):
        raw = yf.Ticker(TICKER).history(start=START, end=END, auto_adjust=False)
        raw.columns = [c.lower() for c in raw.columns]
        raw.index = raw.index.tz_localize(None)

    if raw.empty or "volume" not in raw.columns:
        st.error("Téléchargement incomplet (prix ou volume manquant).")
        st.stop()

    st.write(f"{len(raw)} séances téléchargées, {raw.index.min().date()} → {raw.index.max().date()}")

    all_logs = []
    for label, seuil in [("EXP-012a (S=2.0)", 2.0), ("EXP-012b (S=2.5)", 2.5)]:
        ev, ratio, rendement = compute_signal(raw, seuil)
        rets, n_ev = forward_returns(raw["close"], ev)
        with st.expander(f"📊 {label} — {n_ev} signaux"):
            st.dataframe(summarize(rets), hide_index=True)
        log = build_event_log(raw["close"], ev, TICKER, label)
        all_logs.append(log)

    combined = pd.concat(all_logs, ignore_index=True)

    prices_out = raw[["close"]].reset_index()
    prices_out.columns = ["date", "close"]
    prices_out["date"] = prices_out["date"].dt.strftime("%Y-%m-%d")
    prices_out["ticker"] = TICKER

    st.session_state.exp012_data = {"journal": combined, "prices": prices_out}

if st.session_state.exp012_data is not None:
    d = st.session_state.exp012_data
    st.success(f"{len(d['journal'])} signaux au total (a+b combinés).")

    st.download_button(
        "⬇️ Télécharger le journal combiné (CSV)",
        data=d["journal"].to_csv(index=False).encode("utf-8"),
        file_name="exp012_journal_ALL.csv", mime="text/csv", key="dl_journal",
    )
    st.download_button(
        "⬇️ Télécharger les prix quotidiens (CSV)",
        data=d["prices"].to_csv(index=False).encode("utf-8"),
        file_name="exp012_prix_SPY.csv", mime="text/csv", key="dl_prices",
    )

    st.markdown("### 📋 Alternative : copier-coller le texte brut")
    with st.expander("Voir le journal (CSV en texte)"):
        st.text_area("Journal", d["journal"].to_csv(index=False), height=300, key="txt_journal")
    with st.expander("Voir les prix (CSV en texte)"):
        st.text_area("Prix", d["prices"].to_csv(index=False), height=300, key="txt_prices")

    with st.expander("🔒 Identification de l'expérience"):
        st.code(
            f"EXP-012 / V1.0 — Volume Climax\n"
            f"SMA20_Volume_t = moyenne(Volume_(t-1)..Volume_(t-20))\n"
            f"Ratio_Volume_t = Volume_t / SMA20_Volume_t\n"
            f"Condition_t = Ratio_Volume_t >= S ET Rendement_t <= -2.0%\n"
            f"Signal_t = Condition_t ET NON Condition_(t-1) (franchissement)\n"
            f"Seuils S = {SEUILS_VOL}\n"
            f"Actif = {TICKER} · Période = {START} à {END}\n"
            f"Blocs a analyser separement: 2006-2015 et 2016-2026\n"
            f"Aucune règle de sortie · Aucune optimisation post-résultats"
        )
