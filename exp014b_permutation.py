"""
exp014b_permutation.py
EXP-014 — Mécanisme 014b : Permutation circulaire, p-values NON corrigées.

Méthode identique à celle déjà validée pour 014a (mêmes 5 exigences de GPT) :
1. Rendements toujours réels, jamais recalculés fictivement
2. Décalage circulaire (np.roll)
3. Même décalage k tiré pour les 6 paires à chaque permutation
4. Trades traversant un trou D-001 exclus
5. Les 4 horizons restent séparés

999 permutations, graine fixe 2026, date de fin gelée 2026-09-25.
Consensus GPT/Gemini/Claude : ARRÊT après ce tableau — pas de Bonferroni,
pas de blocs A/B ici.
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import io

st.set_page_config(page_title="EXP-014b - Permutation", layout="wide")
st.title("🧪 EXP-014b — Permutation circulaire (p-values non corrigées, arrêt après)")

UNIVERSE = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X"]
START_DATE = "2006-05-16"
FROZEN_END_DATE = "2026-09-25"

SMA_WINDOW = 20
ZSCORE_WINDOW = 20
ZSCORE_THRESHOLD = 2.0
HOLE_THRESHOLD_DAYS = 5
DEDUP_MIN_SESSIONS = 5
HORIZONS = [1, 5, 10, 20]
N_PERMUTATIONS = 999
RANDOM_SEED = 2026


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


def precompute_forward_returns(entry_arr, exit_arr, prefix, n, h, entry_is_open):
    fr = np.full(n, np.nan)
    for e in range(n):
        exit_idx = e + h
        start_check = e - 1 if entry_is_open else e
        if hole_between(prefix, start_check, exit_idx, n):
            continue
        entry_price = entry_arr[e]
        exit_price = exit_arr[exit_idx] if exit_idx < n else np.nan
        if entry_price == 0 or np.isnan(entry_price) or np.isnan(exit_price):
            continue
        fr[e] = exit_price / entry_price - 1
    return fr


def mean_signal_return(signal_array: np.ndarray, fr_h: np.ndarray, n: int):
    idx_nonzero = np.nonzero(signal_array)[0]
    trade_returns = []
    for sig_idx in idx_nonzero:
        e = sig_idx + 1
        if e >= n:
            continue
        val = fr_h[e]
        if np.isnan(val):
            continue
        trade_returns.append(signal_array[sig_idx] * val)
    if len(trade_returns) == 0:
        return None, 0
    return float(np.mean(trade_returns)), len(trade_returns)


def process_pair(ticker: str):
    df = load_data(ticker, START_DATE, FROZEN_END_DATE)
    if df.empty:
        return None

    df_signal = compute_signal_014b(df)
    df_dedup = apply_dedup(df_signal, DEDUP_MIN_SESSIONS)

    n = len(df_dedup)
    opens = df_dedup["Open"].values.astype(float)
    closes = df_dedup["Close"].values.astype(float)
    prefix = compute_biggap_prefix(df_dedup["Date"], HOLE_THRESHOLD_DAYS)
    signal_array = df_dedup["signal_kept"].values.astype(int)

    results = {}
    rng = np.random.default_rng(RANDOM_SEED)

    for h in HORIZONS:
        fr_signal_h = precompute_forward_returns(opens, closes, prefix, n, h, entry_is_open=True)
        fr_baseline_h = precompute_forward_returns(closes, closes, prefix, n, h, entry_is_open=False)

        obs_mean, obs_n = mean_signal_return(signal_array, fr_signal_h, n)
        baseline_mean = np.nanmean(fr_baseline_h)

        if obs_mean is None:
            results[h] = {"obs_excess": None, "obs_n": 0, "p_value": None, "n_perm_valid": 0}
            continue

        obs_excess = obs_mean - baseline_mean

        perm_excess_values = []
        ks = rng.integers(low=1, high=max(n, 2), size=N_PERMUTATIONS)
        for k in ks:
            k_pair = int(k) % n
            shifted = np.roll(signal_array, k_pair)
            perm_mean, _ = mean_signal_return(shifted, fr_signal_h, n)
            if perm_mean is None:
                continue
            perm_excess_values.append(perm_mean - baseline_mean)

        perm_excess_values = np.array(perm_excess_values)
        n_perm_valid = len(perm_excess_values)

        if n_perm_valid == 0:
            p_value = None
        else:
            extreme_count = np.sum(np.abs(perm_excess_values) >= np.abs(obs_excess))
            p_value = (1 + extreme_count) / (1 + n_perm_valid)

        results[h] = {
            "obs_excess": obs_excess,
            "obs_n": obs_n,
            "p_value": p_value,
            "n_perm_valid": n_perm_valid,
        }

    return results


def main():
    st.markdown(
        f"Date de fin gelée : **{FROZEN_END_DATE}**. "
        "p-values **non corrigées** uniquement — **arrêt après ce tableau**, "
        "pas de Bonferroni, pas de blocs A/B ici."
    )

    with st.expander("📐 Méthodologie (identique à 014a, déjà validée)"):
        st.markdown(
            "1. Rendements toujours réels, jamais recalculés\n"
            "2. Décalage circulaire (np.roll)\n"
            "3. Même décalage pour les 6 paires à chaque permutation\n"
            "4. Trades traversant un trou D-001 exclus\n"
            "5. Les 4 horizons restent séparés\n\n"
            f"Permutations : {N_PERMUTATIONS} | Graine fixe : {RANDOM_SEED}"
        )

    rows = []
    progress = st.progress(0.0, text="Calcul en cours...")

    for i, ticker in enumerate(UNIVERSE):
        results = process_pair(ticker)
        progress.progress((i + 1) / len(UNIVERSE), text=f"{ticker} terminé...")

        if results is None:
            st.error(f"⚠️ Échec de téléchargement pour {ticker}")
            continue

        for h in HORIZONS:
            r = results[h]
            rows.append({
                "Paire": ticker,
                "Horizon (jours)": h,
                "N trades observés": r["obs_n"],
                "Excess return observé (%)": round(r["obs_excess"] * 100, 4) if r["obs_excess"] is not None else None,
                "N permutations valides": r["n_perm_valid"],
                "p-value NON corrigée": round(r["p_value"], 4) if r["p_value"] is not None else None,
            })

    progress.empty()
    result_df = pd.DataFrame(rows)

    st.header("📊 Résultat : p-values non corrigées (24 cellules — 014b seul)")
    st.markdown(
        "⚠️ Ne pas comparer à 0,05. Le vrai seuil (Bonferroni, 0,0010417) "
        "vient à l'étape suivante, une fois ce tableau validé par l'équipe."
    )
    st.dataframe(result_df, use_container_width=True)

    st.header("⬇️ Télécharger (CSV)")
    buffer = io.StringIO()
    result_df.to_csv(buffer, index=False)
    st.download_button(
        label="📥 Télécharger exp014b_permutation.csv",
        data=buffer.getvalue(),
        file_name="exp014b_permutation.csv",
        mime="text/csv",
    )

    st.caption("⏸️ ARRÊT ICI, comme convenu par l'équipe.")


if __name__ == "__main__":
    main()
