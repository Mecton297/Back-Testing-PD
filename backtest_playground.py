import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import math

st.set_page_config(page_title="Backtest 2 Chandelles", layout="centered")
st.title("📈 Backtest 2 Chandelles")

DEFAULT_TICKERS = {
    "FNB1": "XEG.TO",
    "FNB2": "ZMT.TO",
    "FNB3": "XST.TO",
    "FNB4": "ZEB.TO",
    "FNB5": "XIC.TO",
    "FNB6": "VCN.TO",
}
NDX_TICKER = "^NDX"

# ---------------------------------------------------------------
# MOTEUR DE BACKTEST (logique validée : gap, floor, stop monotone,
# pas de re-entrée le jour même, liquidation finale)
# ---------------------------------------------------------------

def run_backtest(df, capital, ach_pct, stinit_pct, stsuiv_pct):
    """
    df : DataFrame avec colonnes Open, High, Low, Close (index = dates, triées)
    Retourne : (capital_final, gain_dollars, drawdown_pct, journal_df, valeur_finale_position)
    """
    df = df.copy().reset_index(drop=True)
    n = len(df)
    if n < 3:
        return capital, 0.0, 0.0, pd.DataFrame(), capital

    cash = float(capital)
    shares = 0
    entry_price = None
    stop = None
    journal = []
    equity_curve = [cash]
    blocked_today = False  # empeche re-entree le jour d'une sortie

    for i in range(2, n):
        c1_high, c2_high = df.loc[i-1, "High"], df.loc[i-2, "High"]
        c1_low, c2_low = df.loc[i-1, "Low"], df.loc[i-2, "Low"]
        prev2_high = max(c1_high, c2_high)
        prev2_low = min(c1_low, c2_low)

        today_high = df.loc[i, "High"]
        today_low = df.loc[i, "Low"]
        today_close = df.loc[i, "Close"]
        today_date = df.loc[i, "Date"] if "Date" in df.columns else i

        exited_today = False

        if shares > 0:
            # 1. Mise a jour du stop suiveur AVANT le test du jour
            potential_stop = prev2_low * (1 - stsuiv_pct / 100)
            stop = max(stop, potential_stop)

            # 2. Test de sortie (gap-aware : si Low < stop, sortie au Low)
            if today_low <= stop:
                exit_price = today_low if today_low < stop else stop
                proceeds = shares * exit_price
                cash += proceeds
                journal.append({
                    "date": today_date, "action": "SORTIE", "prix": round(exit_price, 4),
                    "actions": shares, "cash_apres": round(cash, 2),
                    "raison": "trailing_stop" if today_low >= stop - 1e-9 else "trailing_stop_gap"
                })
                shares = 0
                entry_price = None
                stop = None
                exited_today = True

        if shares == 0 and not exited_today:
            # Test d'entree (pas de re-entree le jour meme d'une sortie, garanti par exited_today)
            trigger = prev2_high * (1 + ach_pct / 100)
            if today_high >= trigger:
                entry_price = trigger
                n_shares = math.floor(cash / entry_price) if entry_price > 0 else 0
                if n_shares > 0:
                    cost = n_shares * entry_price
                    cash -= cost
                    shares = n_shares
                    stop = entry_price * (1 - stinit_pct / 100)
                    journal.append({
                        "date": today_date, "action": "ENTREE", "prix": round(entry_price, 4),
                        "actions": shares, "cash_apres": round(cash, 2), "raison": "signal_entree"
                    })
                    # Meme jour : test du stop initial (scenario prudent)
                    if today_low <= stop:
                        exit_price = today_low if today_low < stop else stop
                        proceeds = shares * exit_price
                        cash += proceeds
                        journal.append({
                            "date": today_date, "action": "SORTIE", "prix": round(exit_price, 4),
                            "actions": shares, "cash_apres": round(cash, 2),
                            "raison": "stop_meme_jour"
                        })
                        shares = 0
                        entry_price = None
                        stop = None
                # si n_shares == 0 : capital insuffisant, aucun trade journalise

        equity = cash + shares * today_close
        equity_curve.append(equity)

    # Liquidation finale si position encore ouverte
    if shares > 0:
        final_close = df.loc[n-1, "Close"]
        proceeds = shares * final_close
        cash += proceeds
        journal.append({
            "date": df.loc[n-1, "Date"] if "Date" in df.columns else n-1,
            "action": "LIQUIDATION", "prix": round(final_close, 4),
            "actions": shares, "cash_apres": round(cash, 2), "raison": "end_of_period"
        })
        shares = 0

    equity_curve.append(cash)
    equity_arr = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity_arr)
    drawdowns = (equity_arr - running_max) / running_max
    max_dd = drawdowns.min() * 100 if len(drawdowns) else 0.0

    gain = cash - capital
    journal_df = pd.DataFrame(journal)
    return cash, gain, max_dd, journal_df, cash


def buy_and_hold(df, capital):
    if len(df) < 2:
        return capital, 0.0
    first_close = df["Close"].iloc[0]
    last_close = df["Close"].iloc[-1]
    final_value = capital * (last_close / first_close)
    return final_value, final_value - capital


@st.cache_data(ttl=3600)
def download_data(ticker, start, end):
    raw = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
    if raw.empty:
        return None
    raw = raw.reset_index()
    raw = raw.rename(columns={"Date": "Date"})
    raw["Date"] = pd.to_datetime(raw["Date"]).dt.tz_localize(None)
    return raw[["Date", "Open", "High", "Low", "Close"]].dropna()


# ---------------------------------------------------------------
# INTERFACE
# ---------------------------------------------------------------

if "tickers" not in st.session_state:
    st.session_state.tickers = dict(DEFAULT_TICKERS)
if "params" not in st.session_state:
    st.session_state.params = {k: {"ach": 1.0, "stinit": 3.0, "stsuiv": 3.0} for k in DEFAULT_TICKERS}

results_placeholder = st.empty()

with st.expander("⚙️ Réglages des 6 FNB", expanded=False):
    for key in DEFAULT_TICKERS:
        st.markdown(f"**{key}**")
        cols = st.columns(4)
        st.session_state.tickers[key] = cols[0].text_input(
            f"Ticker ({key})", value=st.session_state.tickers[key], key=f"tk_{key}", label_visibility="collapsed")
        st.session_state.params[key]["ach"] = cols[1].number_input(
            "Ach%", value=st.session_state.params[key]["ach"], step=0.1, key=f"ach_{key}")
        st.session_state.params[key]["stinit"] = cols[2].number_input(
            "StInit%", value=st.session_state.params[key]["stinit"], step=0.1, key=f"si_{key}")
        st.session_state.params[key]["stsuiv"] = cols[3].number_input(
            "StSuiv%", value=st.session_state.params[key]["stsuiv"], step=0.1, key=f"ss_{key}")

st.markdown("### Paramètres globaux")
capital_total = st.number_input("Capital à investir ($)", value=10000, step=500, min_value=100)
col_a, col_b = st.columns(2)
annee_debut = col_a.number_input("Année début", value=2015, min_value=2000, max_value=2026)
annee_fin = col_b.number_input("Année fin", value=2026, min_value=2000, max_value=2026)

mode = st.radio("Mode de répartition", ["Mode A — 100% par FNB", "Mode B — Répartition %"])

allocations = {}
if mode.startswith("Mode B"):
    st.markdown("#### Répartition du capital")
    total_pct = 0
    for key in DEFAULT_TICKERS:
        c1, c2 = st.columns([1, 2])
        active = c1.checkbox(key, value=True, key=f"active_{key}")
        pct = c2.number_input(f"% {key}", value=round(100/6, 1), min_value=0.0, max_value=100.0,
                               step=1.0, key=f"pct_{key}", disabled=not active, label_visibility="collapsed")
        allocations[key] = pct if active else 0.0
        total_pct += allocations[key]
    if abs(total_pct - 100) > 0.01:
        st.warning(f"⚠️ La somme des allocations est {total_pct:.1f}%, pas 100%. Ajuste avant de lancer.")

lancer = st.button("🚀 Lancer le backtest", type="primary")

if lancer:
    start_str = f"{int(annee_debut)}-01-01"
    end_str = f"{int(annee_fin)}-12-31"

    rows = {"% Test": [], "% Hold": [], "Gain $": [], "DD %": []}
    col_labels = []
    journals = {}

    with st.spinner("Téléchargement et calcul en cours..."):
        for key, ticker in st.session_state.tickers.items():
            data = download_data(ticker, start_str, end_str)
            col_labels.append(ticker)
            if data is None or len(data) < 5:
                rows["% Test"].append("N/A")
                rows["% Hold"].append("N/A")
                rows["Gain $"].append("N/A")
                rows["DD %"].append("N/A")
                continue

            if mode.startswith("Mode A"):
                cap_ticker = capital_total
            else:
                cap_ticker = capital_total * allocations.get(key, 0) / 100
                if cap_ticker <= 0:
                    rows["% Test"].append("—")
                    rows["% Hold"].append("—")
                    rows["Gain $"].append("—")
                    rows["DD %"].append("—")
                    continue

            p = st.session_state.params[key]
            final_cash, gain, dd, journal_df, _ = run_backtest(
                data, cap_ticker, p["ach"], p["stinit"], p["stsuiv"])
            hold_final, hold_gain = buy_and_hold(data, cap_ticker)

            pct_test = (final_cash / cap_ticker - 1) * 100
            pct_hold = (hold_final / cap_ticker - 1) * 100

            rows["% Test"].append(f"{round(pct_test)}%")
            rows["% Hold"].append(f"{round(pct_hold)}%")
            rows["Gain $"].append(f"{round(gain)} $")
            rows["DD %"].append(f"{round(dd)}%")
            journals[ticker] = journal_df

    result_table = pd.DataFrame(rows, index=col_labels).T
    with results_placeholder.container():
        st.markdown("### Résultats")
        st.dataframe(result_table, use_container_width=True)

    with st.expander("📜 Journal des trades (par FNB)"):
        for ticker, jdf in journals.items():
            st.write(f"**{ticker}**")
            if len(jdf) > 0:
                st.dataframe(jdf, hide_index=True, use_container_width=True)
            else:
                st.caption("Aucun trade sur la période.")

    # Reference Nasdaq
    st.markdown("---")
    st.markdown("### 📊 Référence — Nasdaq 100 (^NDX)")
    ndx_data = download_data(NDX_TICKER, start_str, end_str)
    if ndx_data is not None and len(ndx_data) > 1:
        ndx_first = ndx_data["Close"].iloc[0]
        ndx_last = ndx_data["Close"].iloc[-1]
        ndx_pct = (ndx_last / ndx_first - 1) * 100
        st.write(f"Buy & Hold ^NDX sur la période : **{round(ndx_pct)}%**")
    else:
        st.caption("Données NDX indisponibles pour cette période.")

with st.expander("ℹ️ Notes méthodologiques"):
    st.markdown("""
- **Prix utilisés** : ajustés par yfinance (`auto_adjust=True`), ce qui corrige les splits **et** les dividendes.
  Le "Buy & Hold — prix seul" demandé n'exclut donc pas complètement l'effet des dividendes réinvestis :
  c'est une limite technique connue, pas un choix arbitraire — à garder en tête pour l'interprétation.
- **Entrée** : franchissement du plus haut des 2 chandelles précédentes × (1 + Ach%), exécutée au prix de déclenchement.
- **Stop initial** : prix d'entrée × (1 - StInit%).
- **Stop suiveur** : basé sur le plus bas des 2 chandelles précédentes × (1 - StSuiv%), ne redescend jamais.
- **Entrée + stop même jour** : sortie prudente le jour même, au stop (ou au Low si gap sous le stop).
- **Gap sous le stop** : si le Low de la journée est sous le niveau du stop, sortie au Low (pas au stop) — réaliste.
- **Capital insuffisant** (`floor(cash/prix) == 0`) : aucun trade, pas de ligne au journal.
- **Position ouverte en fin de période** : liquidée au dernier Close, inscrite au journal (`end_of_period`).
    """)
