"""
exp014b_returns.py
EXP-014 — Mécanisme 014b : RENDEMENTS BRUTS SEULEMENT.

Consensus GPT/Gemini/Claude : on s'arrête ici pour contrôle visuel avant
de calculer baseline, excess return ou toute permutation. Ne pas ajuster
le seuil ±2,0 en fonction du nombre de signaux obtenus (règle explicite).

Paramètres verrouillés (charter section 6), identiques à ceux déjà validés :
- SMA 20, Z-score 20, seuil ±2,0
- Entrée : Open T+1
- Sortie : Close à horizon H (pas de sortie conditionnelle)
- Horizons : +1, +5, +10, +20 jours
- Déduplication : 5 séances minimum entre deux signaux conservés (même paire)
- D-001 : trou > 5 jours calendaires chevauchant la fenêtre = trade exclu
- Date de fin gelée : 2026-09-25 (identique à 014a, pour reproductibilité)
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import io

st.set_page_config(page_title="EXP-014b - Rendements bruts", layout="wide")
st.title("🧪 EXP-014b — Rendements bruts SEULEMENT (arrêt après ce tableau)")

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


def compute_returns(df: pd.DataFrame, horizons: list, hole_threshold: int) -> pd.DataFrame:
    n = len(df)
    opens = df["Open"].values.astype(float)
    closes = df["Close"].values.astype(float)
    prefix = compute_biggap_prefix(df["Date"], hole_threshold)

    rows = []
    signal_indices = df.index[df["signal_kept"] != 0].tolist()

    for sig_idx in signal_indices:
        entry_idx = sig_idx + 1
        direction = df.at[sig_idx, "signal_kept"]
        signal_date = df.at[sig_idx, "Date"]

        if entry_idx >= n:
            continue

        entry_price = opens[entry_idx]
        row = {
            "date_signal": signal_date,
            "direction": int(direction),
            "entry_price": entry_price,
        }

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

            trade_return = direction * (exit_price / entry_price - 1)
            row[col_ret] = trade_return
            row[col_valid] = True

        rows.append(row)

    return pd.DataFrame(rows)


def main():
    st.markdown(
        f"Date de fin gelée : **{FROZEN_END_DATE}**. "
        "Rendements bruts uniquement — **on s'arrête après ce tableau**, "
        "pas de baseline, pas d'excess return, pas de permutation ici."
    )

    summary_rows = []
    all_returns = {}

    with st.spinner("Calcul en cours..."):
        for ticker in UNIVERSE:
            df = load_data(ticker, START_DATE, FROZEN_END_DATE)
            if df.empty:
                st.error(f"⚠️ Échec de téléchargement pour {ticker}")
                continue

            df_signal = compute_signal_014b(df)
            df_dedup = apply_dedup(df_signal, DEDUP_MIN_SESSIONS)
            df_returns = compute_returns(df_dedup, HORIZONS, HOLE_THRESHOLD_DAYS)
            all_returns[ticker] = df_returns

            n_signals_raw = int((df_signal["signal_014b"] != 0).sum())
            n_signals_kept = int((df_dedup["signal_kept"] != 0).sum())

            row = {
                "Paire": ticker,
                "Signaux bruts": n_signals_raw,
                "Signaux après dédup": n_signals_kept,
            }
            for h in HORIZONS:
                col, valid_col = f"ret_{h}d", f"valid_{h}d"
                if col in df_returns.columns:
                    n_valid = int(df_returns[valid_col].sum())
                    avg_ret = df_returns.loc[df_returns[valid_col], col].mean()
                    row[f"Trades valides {h}j"] = n_valid
                    row[f"Rendement moyen {h}j (%)"] = round(avg_ret * 100, 4) if pd.notna(avg_ret) else None
                else:
                    row[f"Trades valides {h}j"] = 0
                    row[f"Rendement moyen {h}j (%)"] = None

            summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)

    st.header("📊 Résumé par paire (rendements bruts, pas encore de baseline)")
    st.dataframe(summary_df, use_container_width=True)

    st.header("⬇️ Télécharger TOUT (résumé + détail des 6 paires, un seul fichier)")
    buffer = io.StringIO()
    buffer.write("=== RÉSUMÉ PAR PAIRE ===\n")
    summary_df.to_csv(buffer, index=False)
    for ticker, df_ret in all_returns.items():
        buffer.write(f"\n=== DÉTAIL TRADES — {ticker} ===\n")
        df_ret.to_csv(buffer, index=False)

    st.download_button(
        label="📥 Télécharger exp014b_returns.csv",
        data=buffer.getvalue(),
        file_name="exp014b_returns.csv",
        mime="text/csv",
    )

    st.caption(
        "⏸️ ARRÊT ICI, comme convenu par l'équipe. Prochaine étape (après "
        "validation des 3) : baseline inconditionnelle + excess return."
    )


if __name__ == "__main__":
    main()
