import math
from datetime import date

import pandas as pd
import streamlit as st
import yfinance as yf


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Backtest 2 Chandelles",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    /* Mobile / compact layout */
    .block-container {
        padding-top: 0.15rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.35rem !important;
        padding-right: 0.35rem !important;
        max-width: 100% !important;
    }

    h1 {
        font-size: 1.05rem !important;
        margin: 0 0 0.15rem 0 !important;
    }

    h2, h3 {
        font-size: 0.9rem !important;
        margin: 0.25rem 0 0.15rem 0 !important;
    }

    div[data-testid="stMetric"] {
        padding: 0 !important;
    }

    div[data-testid="stDataFrame"] {
        font-size: 0.72rem !important;
    }

    div[data-testid="stDataFrame"] table {
        font-size: 0.72rem !important;
    }

    .stButton button, .stDownloadButton button {
        min-height: 2rem !important;
        padding: 0.15rem 0.45rem !important;
    }

    div[data-baseweb="input"] input {
        font-size: 0.8rem !important;
    }

    label {
        font-size: 0.75rem !important;
    }

    /* Keep the result table horizontally scrollable on phones */
    div[data-testid="stDataFrame"] > div {
        overflow-x: auto !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

DEFAULT_TICKERS = ["XEG.TO", "ZMT.TO", "XST.TO", "ZEB.TO", "CHPS.TO", "DATA.TO"]


def pct_text(value):
    if pd.isna(value):
        return "—"
    return f"{round(value):.0f}%"


def dollar_text(value):
    if pd.isna(value):
        return "—"
    return f"{round(value):,.0f} $".replace(",", " ")


def max_drawdown(values):
    if len(values) == 0:
        return 0.0
    s = pd.Series(values, dtype=float)
    peak = s.cummax()
    dd = (s / peak - 1.0) * 100.0
    return float(dd.min())


@st.cache_data(ttl=3600, show_spinner=False)
def download_prices(ticker, start, end):
    # Add one day to include the requested end date.
    end_plus = pd.Timestamp(end) + pd.Timedelta(days=1)
    df = yf.download(
        ticker,
        start=pd.Timestamp(start),
        end=end_plus,
        auto_adjust=False,
        progress=False,
    )

    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    needed = ["High", "Low", "Close"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        return pd.DataFrame()

    out = df[needed].copy().dropna()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out


def run_backtest(df, capital, ach_pct, st_init_pct, st_suiv_pct):
    """
    Two-candle breakout strategy.

    Entry:
      trigger = highest High of the previous 2 candles * (1 + Ach%)
      if today's High reaches trigger, enter at trigger.

    Initial stop:
      entry_price * (1 - StInit%)

    Trailing stop:
      candidate = lowest Low of the previous 2 candles * (1 - StSuiv%)
      stop can only move upward.

    Shares:
      floor(available capital / entry price)

    Exit:
      if today's Low reaches the stop, sell at the stop.

    Same-day entry/stop ambiguity:
      A newly opened position is not stopped on the same candle.
      Stop checking begins on the following trading day.
    """
    if df.empty or len(df) < 3:
        return None

    data = df.copy()
    cash = float(capital)
    shares = 0
    entry_price = None
    stop_price = None
    equity_curve = []
    trades = []

    for i in range(len(data)):
        today = data.index[i]
        high = float(data.iloc[i]["High"])
        low = float(data.iloc[i]["Low"])
        close = float(data.iloc[i]["Close"])

        # Manage an existing position first.
        if shares > 0:
            # Raise trailing stop using the lows of the two previous candles.
            if i >= 2:
                prev_two_low = float(data.iloc[i - 2:i]["Low"].min())
                trailing_candidate = prev_two_low * (1.0 - st_suiv_pct / 100.0)
                stop_price = max(stop_price, trailing_candidate)

            # Stop execution.
            if low <= stop_price:
                exit_price = stop_price
                cash += shares * exit_price
                trades.append(
                    {
                        "Entrée": entry_price,
                        "Sortie": exit_price,
                        "Date sortie": today,
                    }
                )
                shares = 0
                entry_price = None
                stop_price = None

        # Look for a new entry only when flat.
        if shares == 0 and i >= 2:
            prev_two_high = float(data.iloc[i - 2:i]["High"].max())
            trigger = prev_two_high * (1.0 + ach_pct / 100.0)

            if high >= trigger:
                qty = math.floor(cash / trigger)

                if qty > 0:
                    entry_price = trigger
                    shares = qty
                    cash -= qty * entry_price
                    stop_price = entry_price * (1.0 - st_init_pct / 100.0)

        equity = cash + shares * close
        equity_curve.append(equity)

    # Liquidate at the final close only for final portfolio value.
    # This does not create a strategy trade; it is only the mark-to-market value.
    final_equity = cash + shares * float(data.iloc[-1]["Close"])
    initial_equity = float(capital)

    strategy_return = (final_equity / initial_equity - 1.0) * 100.0
    dd = max_drawdown(equity_curve)

    return {
        "final_equity": final_equity,
        "return_pct": strategy_return,
        "gain": final_equity - initial_equity,
        "drawdown_pct": dd,
        "equity_curve": equity_curve,
        "trades": trades,
    }


def buy_hold(df, capital):
    if df.empty:
        return None

    first_close = float(df.iloc[0]["Close"])
    closes = df["Close"].astype(float)

    shares = math.floor(capital / first_close)
    cash = capital - shares * first_close
    equity = cash + shares * closes

    final_value = float(equity.iloc[-1])
    ret = (final_value / capital - 1.0) * 100.0
    dd = max_drawdown(equity)

    return {
        "final_equity": final_value,
        "return_pct": ret,
        "gain": final_value - capital,
        "drawdown_pct": dd,
    }


def get_reference_ndx(start, end):
    df = download_prices("^NDX", start, end)
    if df.empty:
        return None
    first = float(df["Close"].iloc[0])
    last = float(df["Close"].iloc[-1])
    return (last / first - 1.0) * 100.0


# ============================================================
# TITLE
# ============================================================

st.title("📈 Backtest 2 Chandelles")


# ============================================================
# GLOBAL CONTROLS — kept compact and above the table only for
# the per-ETF settings; capital/date/mode are deliberately below.
# ============================================================

st.markdown("**⚙️ Réglages FNB**")

# Six ETF columns. The two configurable ETFs are always last.
cols = st.columns(6, gap="small")

ticker_defaults = []
params = []

for i in range(6):
    with cols[i]:
        if i < 4:
            ticker = st.text_input(
                f"FNB {i+1}",
                value=DEFAULT_TICKERS[i],
                key=f"ticker_{i}",
                label_visibility="visible",
            )
        else:
            ticker = st.text_input(
                f"FNB {i+1} ✏️",
                value=DEFAULT_TICKERS[i],
                key=f"ticker_{i}",
                label_visibility="visible",
            )

        ach = st.number_input(
            "Ach%",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=0.1,
            key=f"ach_{i}",
        )
        st_init = st.number_input(
            "StInit%",
            min_value=0.0,
            max_value=100.0,
            value=5.0,
            step=0.1,
            key=f"stinit_{i}",
        )
        st_suiv = st.number_input(
            "StSuiv%",
            min_value=0.0,
            max_value=100.0,
            value=3.0,
            step=0.1,
            key=f"stsuiv_{i}",
        )

        ticker_defaults.append(ticker.strip().upper())
        params.append(
            {
                "ticker": ticker.strip().upper(),
                "ach": ach,
                "st_init": st_init,
                "st_suiv": st_suiv,
            }
        )


# ============================================================
# RESULT TABLE — FIRST STRONG VISUAL ELEMENT
# ============================================================

st.markdown("### Résultats")

capital = st.session_state.get("capital", 10000.0)
start_year = st.session_state.get("start_year", 2015)
end_year = st.session_state.get("end_year", date.today().year)

# Read current global controls if already created below.
# Initial display is still a valid placeholder until the user presses Run.
if "results" not in st.session_state:
    empty = pd.DataFrame(
        {
            "Métrique": ["% Test", "% Hold", "Gain $", "DD %"],
            **{t if t else f"FNB{i+1}": ["—"] * 4 for i, t in enumerate(ticker_defaults)},
        }
    )
    # Force exactly four rows.
    empty = pd.DataFrame(
        [
            ["% Test"] + ["—"] * 6,
            ["% Hold"] + ["—"] * 6,
            ["Gain $"] + ["—"] * 6,
            ["DD %"] + ["—"] * 6,
        ],
        columns=["Métrique"] + ticker_defaults,
    )
    st.dataframe(
        empty,
        hide_index=True,
        use_container_width=True,
        height=185,
    )
else:
    st.dataframe(
        st.session_state["results"],
        hide_index=True,
        use_container_width=True,
        height=185,
    )


# ============================================================
# GLOBAL SETTINGS — deliberately below the main table
# ============================================================

st.markdown("### Paramètres")

c1, c2, c3 = st.columns(3, gap="small")

with c1:
    capital = st.number_input(
        "Capital à investir ($)",
        min_value=1.0,
        value=10000.0,
        step=500.0,
        key="capital",
    )

with c2:
    start_year = st.number_input(
        "Année début",
        min_value=1990,
        max_value=date.today().year,
        value=2015,
        step=1,
        key="start_year",
    )

with c3:
    end_year = st.number_input(
        "Année fin",
        min_value=1990,
        max_value=date.today().year,
        value=date.today().year,
        step=1,
        key="end_year",
    )

mode = st.radio(
    "Mode de répartition",
    ["100 % par FNB", "Répartition %"],
    horizontal=True,
    key="mode",
)


# ============================================================
# CUSTOM ALLOCATION — only visible in allocation mode
# ============================================================

allocations = [0.0] * 6
active = [True] * 6

if mode == "Répartition %":
    st.markdown("**Répartition du capital**")

    alloc_cols = st.columns(6, gap="small")
    for i in range(6):
        with alloc_cols[i]:
            active[i] = st.checkbox(
                ticker_defaults[i] or f"FNB {i+1}",
                value=True,
                key=f"active_{i}",
            )
            allocations[i] = st.number_input(
                "%",
                min_value=0.0,
                max_value=100.0,
                value=16.67,
                step=1.0,
                key=f"alloc_{i}",
            )

    total_alloc = sum(
        allocations[i] for i in range(6) if active[i]
    )

    st.markdown(
        f"**Total actif : {total_alloc:.0f}%**"
        + (" ✅" if abs(total_alloc - 100.0) < 0.001 else " ⚠️ Le total doit être 100 %")
    )


# ============================================================
# RUN
# ============================================================

run = st.button("▶️ Lancer le backtest", type="primary", use_container_width=True)

if run:
    if end_year < start_year:
        st.error("L'année de fin doit être supérieure ou égale à l'année de début.")
        st.stop()

    if mode == "Répartition %":
        selected = [i for i in range(6) if active[i]]
        if not selected:
            st.error("Sélectionne au moins un FNB.")
            st.stop()

        total_alloc = sum(allocations[i] for i in selected)
        if abs(total_alloc - 100.0) > 0.01:
            st.error(f"Le total des pourcentages doit être 100 %. Actuellement : {total_alloc:.2f} %.")
            st.stop()

    results_rows = {
        "% Test": [],
        "% Hold": [],
        "Gain $": [],
        "DD %": [],
    }

    result_columns = []
    errors = []

    for i, p in enumerate(params):
        ticker = p["ticker"]

        if not ticker:
            errors.append(f"FNB {i+1}: ticker vide.")
            result_columns.append(f"FNB {i+1}")
            for key in results_rows:
                results_rows[key].append("—")
            continue

        # Determine capital assigned to this ETF.
        if mode == "100 % par FNB":
            if not ticker:
                continue
            etf_capital = float(capital)
            include = True
        else:
            include = active[i]
            etf_capital = float(capital) * allocations[i] / 100.0

        result_columns.append(ticker)

        if not include:
            for key in results_rows:
                results_rows[key].append("—")
            continue

        start_date = date(int(start_year), 1, 1)
        end_date = date(int(end_year), 12, 31)

        with st.spinner(f"Téléchargement et backtest de {ticker}..."):
            df = download_prices(ticker, start_date, end_date)

        if df.empty:
            errors.append(f"{ticker}: aucune donnée disponible.")
            for key in results_rows:
                results_rows[key].append("—")
            continue

        test = run_backtest(
            df,
            etf_capital,
            p["ach"],
            p["st_init"],
            p["st_suiv"],
        )
        hold = buy_hold(df, etf_capital)

        if test is None or hold is None:
            errors.append(f"{ticker}: pas assez de données.")
            for key in results_rows:
                results_rows[key].append("—")
            continue

        results_rows["% Test"].append(pct_text(test["return_pct"]))
        results_rows["% Hold"].append(pct_text(hold["return_pct"]))
        results_rows["Gain $"].append(dollar_text(test["gain"]))
        results_rows["DD %"].append(pct_text(test["drawdown_pct"]))

    result_df = pd.DataFrame(
        [
            ["% Test"] + results_rows["% Test"],
            ["% Hold"] + results_rows["% Hold"],
            ["Gain $"] + results_rows["Gain $"],
            ["DD %"] + results_rows["DD %"],
        ],
        columns=["Métrique"] + result_columns,
    )

    st.session_state["results"] = result_df

    if errors:
        for err in errors:
            st.warning(err)

    # Refresh so the newly calculated table appears at the top.
    st.rerun()


# ============================================================
# NASDAQ REFERENCE — bottom
# ============================================================

st.markdown("---")

if st.button("📊 Actualiser la référence Nasdaq ^NDX", use_container_width=True):
    with st.spinner("Calcul du Nasdaq..."):
        ndx = get_reference_ndx(
            date(int(start_year), 1, 1),
            date(int(end_year), 12, 31),
        )

    if ndx is None:
        st.warning("Données ^NDX indisponibles pour cette période.")
    else:
        st.caption(f"Référence Nasdaq (^NDX) — Buy & Hold sur la période : {ndx:.0f}%")
else:
    st.caption("Référence Nasdaq (^NDX) — Buy & Hold affichée ici après actualisation.")
