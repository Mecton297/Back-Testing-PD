"""
exp014b_baseline_excess.py
EXP-014 — Mécanisme 014b : Baseline & Excess Return SEULEMENT.

Consensus GPT/Gemini/Claude : on s'arrête ici pour contrôle avant la
permutation. Même méthode que pour 014a (déjà validée), appliquée à 014b.

Paramètres verrouillés (charter section 6) et date de fin gelée (2026-09-25,
identique à 014a) inchangés depuis les étapes précédentes.
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import io

st.set_page_config(page_title="EXP-014b - Baseline & Excess", layout="wide")
st.title("🧪 EXP-014b — Baseline & Excess Return (arrêt après ce tableau)")

UNIVERSE = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X"]
START_DATE = "2006-05-16"
FROZEN_END_DATE = "2026-09-25"

SMA_WINDOW = 20
ZSCORE_WINDOW = 20
ZSCORE_THRESHOLD = 2.0
HOLE_THRESHOLD_DAYS = 5
DEDUP_MIN_SESSIONS = 5
HORIZONS = [1, 5, 10, 20]


@st.cache_data(show_spinner=False)
def load_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, progress=False)
    if df.empty:
        return df
    df = df.reset_index()
    if "Date" not in df.columns:
        df = df.rename(columns={df.columns[0]: "Date"})
    df["Date"] = pd.to_datetime(df["Date"])
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def compute_signal_014b(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["sma20"] = df["Close"].shift(1).rolling(SMA_WINDOW).mean()
    df["std20"] = df["Close"].shift(1).rolling(ZSCORE_WINDOW).std()
    df["zscore"] = (df["Close"] - df["sma20"]) / df["std20"]

    df["signal_014b"] = 0
    df.loc[df["zscore"] >= ZSCORE_THRESHOLD, "signal_014b"] = -1
    df.loc[df["zscore"] <= -ZSCORE_THRESHOLD, "signal_014b"] = 1
    return df


def apply_dedup(df: pd.DataFrame, min_sessions: int) -> pd.DataFrame:
    df = df.copy()
    df["signal_kept"] = 0
    last_kept_idx = None
    for idx in df.index[df["signal_014b"] != 0]:
        if last_kept_idx is None or (idx - last_kept_idx) >= min_sessions:
            df.at[idx, "signal_kept"] = df.at[idx, "signal_014b"]
            last_kept_idx = idx
    return df


def compute_biggap_prefix(dates: pd.Series, threshold: int) -> np.ndarray:
    diffs = dates.diff().dt.days.fillna(0).values
    big_gap = (diffs > threshold).astype(int)
    return np.concatenate(([0], np.cumsum(big_gap)))


def hole_between(prefix: np.ndarray, start_idx: int, end_idx: int, n: int) -> bool:
    if end_idx >= n or start_idx < 0:
        return True
    return (prefix[end_idx + 1] - prefix[start_idx + 1]) > 0


def compute_trade_returns(df: pd.DataFrame, horizons: list, hole_threshold: int) -> pd.DataFrame:
    n = len(df)
    opens = df["Open"].values.astype(float)
    closes = df["Close"].values.astype(float)
    prefix = compute_biggap_prefix(df["Date"], hole_threshold)

    rows = []
    signal_indices = df.index[df["signal_kept"] != 0].tolist()

    for sig_idx in signal_indices:
        entry_idx = sig_idx + 1
        direction = df.at[sig_idx, "signal_kept"]
        if entry_idx >= n:
            continue
        entry_price = opens[entry_idx]
        row = {"date_signal": df.at[sig_idx, "Date"], "direction": int(direction)}

        for h in horizons:
            exit_idx = entry_idx + h
            col_ret, col_valid = f"ret_{h}d", f"valid_{h}d"
            if exit_idx >= n or hole_between(prefix, sig_idx, exit_idx, n):
                row[col_ret], row[col_valid] = None, False
                continue
            exit_price = closes[exit_idx]
            if entry_price == 0 or np.isnan(entry_price) or np.isnan(exit_price):
                row[col_ret], row[col_valid] = None, False
                continue
            row[col_ret] = direction * (exit_price / entry_price - 1)
            row[col_valid] = True

        rows.append(row)

    return pd.DataFrame(rows)


def compute_baseline(df: pd.DataFrame, horizons: list, hole_threshold: int) -> dict:
    """
    Identique à la méthode déjà validée pour 014a : baseline Close-to-Close,
    sur TOUS les jours (pas seulement les jours de signal).
    """
    n = len(df)
    closes = df["Close"].values.astype(float)
    prefix = compute_biggap_prefix(df["Date"], hole_threshold)

    baseline = {}
    for h in horizons:
        rets = []
        for i in range(n - h):
            j = i + h
            if hole_between(prefix, i, j, n):
                continue
            entry_price = closes[i]
            exit_price = closes[j]
            if entry_price == 0 or np.isnan(entry_price) or np.isnan(exit_price):
                continue
            rets.append(exit_price / entry_price - 1)
        baseline[h] = {
            "baseline_mean_return": (sum(rets) / len(rets)) if rets else None,
            "baseline_n": len(rets),
        }
    return baseline


def main():
    st.markdown(
        f"Date de fin gelée : **{FROZEN_END_DATE}** (identique à 014a). "
        "Baseline + excess return seulement — **arrêt après ce tableau**, "
        "pas de permutation ici."
    )

    summary_rows = []

    with st.spinner("Calcul en cours (la baseline regarde tous les jours, un peu plus lent)..."):
        for ticker in UNIVERSE:
            df = load_data(ticker, START_DATE, FROZEN_END_DATE)
            if df.empty:
                st.error(f"⚠️ Échec de téléchargement pour {ticker}")
                continue

            df_signal = compute_signal_014b(df)
            df_dedup = apply_dedup(df_signal, DEDUP_MIN_SESSIONS)
            df_trades = compute_trade_returns(df_dedup, HORIZONS, HOLE_THRESHOLD_DAYS)
            baseline = compute_baseline(df_dedup, HORIZONS, HOLE_THRESHOLD_DAYS)

            n_raw = int((df_signal["signal_014b"] != 0).sum())
            n_kept = int((df_dedup["signal_kept"] != 0).sum())

            row = {"Paire": ticker, "Signaux bruts": n_raw, "Signaux après dédup": n_kept}

            for h in HORIZONS:
                col, valid_col = f"ret_{h}d", f"valid_{h}d"
                if col in df_trades.columns:
                    signal_mean = df_trades.loc[df_trades[valid_col], col].mean()
                    n_valid_signal = int(df_trades[valid_col].sum())
                else:
                    signal_mean, n_valid_signal = None, 0

                base_mean = baseline[h]["baseline_mean_return"]
                base_n = baseline[h]["baseline_n"]
                excess = (signal_mean - base_mean) if (pd.notna(signal_mean) and base_mean is not None) else None

                row[f"N signal {h}j"] = n_valid_signal
                row[f"Rendement signal {h}j (%)"] = round(signal_mean * 100, 4) if pd.notna(signal_mean) else None
                row[f"N baseline {h}j"] = base_n
                row[f"Baseline {h}j (%)"] = round(base_mean * 100, 4) if base_mean is not None else None
                row[f"EXCESS RETURN {h}j (%)"] = round(excess * 100, 4) if excess is not None else None

            summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)

    st.header("📊 Résultat : Baseline & Excess Return par paire (014b)")
    st.markdown(
        "⚠️ Toujours descriptif, pas de test de significativité ici. "
        "Prochaine étape (après validation des 3) : permutation circulaire."
    )
    st.dataframe(summary_df, use_container_width=True)

    st.header("⬇️ Télécharger (CSV, un seul fichier)")
    buffer = io.StringIO()
    summary_df.to_csv(buffer, index=False)
    st.download_button(
        label="📥 Télécharger exp014b_baseline_excess.csv",
        data=buffer.getvalue(),
        file_name="exp014b_baseline_excess.csv",
        mime="text/csv",
    )

    st.caption("⏸️ ARRÊT ICI, comme convenu par l'équipe.")


if __name__ == "__main__":
    main()
