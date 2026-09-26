"""
exp014b_step3_bonferroni_blocks.py
EXP-014 — Mécanisme 014b : ÉTAPE FINALE — Bonferroni + Blocs A/B.

Méthode strictement identique à celle déjà validée pour 014a
(exp014a_step3_bonferroni_blocks.py). Date de fin gelée : 2026-09-25.

Seuil Bonferroni pré-enregistré (charter section 14, famille complète
014a+014b = 48 cellules) : α = 0,05/48 = 0,0010417. Ce seuil est fixe et
s'applique tel quel à 014b, indépendamment du résultat de 014a.
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import io

st.set_page_config(page_title="EXP-014b - Étape finale", layout="wide")
st.title("🧪 EXP-014b — Étape finale : Bonferroni + Blocs A/B (date gelée)")

UNIVERSE = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X"]
START_DATE = "2006-05-16"
FROZEN_END_DATE = "2026-09-25"

BLOCK_A_END = "2015-12-31"
BLOCK_B_START = "2016-01-01"

SMA_WINDOW = 20
ZSCORE_WINDOW = 20
ZSCORE_THRESHOLD = 2.0
HOLE_THRESHOLD_DAYS = 5
DEDUP_MIN_SESSIONS = 5
HORIZONS = [1, 5, 10, 20]
N_PERMUTATIONS = 999
RANDOM_SEED = 2026

BONFERRONI_ALPHA = 0.05 / 48  # famille complète 014a+014b, pré-enregistrée


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


def test_block(block_df: pd.DataFrame, seed_offset: int):
    block_df = block_df.reset_index(drop=True)
    n = len(block_df)
    if n < 60:
        return {h: {"obs_excess": None, "obs_n": 0, "p_value": None, "n_perm_valid": 0} for h in HORIZONS}

    opens = block_df["Open"].values.astype(float)
    closes = block_df["Close"].values.astype(float)
    prefix = compute_biggap_prefix(block_df["Date"], HOLE_THRESHOLD_DAYS)
    signal_array = block_df["signal_kept"].values.astype(int)

    rng = np.random.default_rng(RANDOM_SEED + seed_offset)
    results = {}

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
            k_local = int(k) % n
            shifted = np.roll(signal_array, k_local)
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


def process_pair(ticker: str):
    df = load_data(ticker, START_DATE, FROZEN_END_DATE)
    if df.empty:
        return None

    df_signal = compute_signal_014b(df)
    df_dedup = apply_dedup(df_signal, DEDUP_MIN_SESSIONS)

    block_a = df_dedup[df_dedup["Date"] <= BLOCK_A_END]
    block_b = df_dedup[df_dedup["Date"] >= BLOCK_B_START]

    results_a = test_block(block_a, seed_offset=1)
    results_b = test_block(block_b, seed_offset=2)

    return results_a, results_b


def main():
    st.markdown(f"**Date de fin gelée : {FROZEN_END_DATE}** (identique à 014a).")
    st.markdown(
        f"**Seuil Bonferroni pré-enregistré : α = {BONFERRONI_ALPHA:.7f}** "
        "(famille complète 014a+014b = 48 cellules)"
    )

    rows = []
    progress = st.progress(0.0, text="Calcul en cours (2 blocs x 6 paires)...")

    for i, ticker in enumerate(UNIVERSE):
        out = process_pair(ticker)
        progress.progress((i + 1) / len(UNIVERSE), text=f"{ticker} terminé...")

        if out is None:
            st.error(f"⚠️ Échec de téléchargement pour {ticker}")
            continue

        results_a, results_b = out

        for h in HORIZONS:
            ra, rb = results_a[h], results_b[h]

            pass_a = (ra["p_value"] is not None) and (ra["p_value"] < BONFERRONI_ALPHA)
            pass_b = (rb["p_value"] is not None) and (rb["p_value"] < BONFERRONI_ALPHA)
            same_sign = (
                ra["obs_excess"] is not None and rb["obs_excess"] is not None
                and np.sign(ra["obs_excess"]) == np.sign(rb["obs_excess"])
            )
            passes_both_blocks = pass_a and pass_b and same_sign

            rows.append({
                "Paire": ticker,
                "Horizon": h,
                "Bloc A - N": ra["obs_n"],
                "Bloc A - Excess (%)": round(ra["obs_excess"] * 100, 4) if ra["obs_excess"] is not None else None,
                "Bloc A - p-value": round(ra["p_value"], 5) if ra["p_value"] is not None else None,
                "Bloc A < seuil?": pass_a,
                "Bloc B - N": rb["obs_n"],
                "Bloc B - Excess (%)": round(rb["obs_excess"] * 100, 4) if rb["obs_excess"] is not None else None,
                "Bloc B - p-value": round(rb["p_value"], 5) if rb["p_value"] is not None else None,
                "Bloc B < seuil?": pass_b,
                "Même signe A/B?": same_sign,
                "PASSE LES 2 BLOCS": passes_both_blocks,
            })

    progress.empty()
    result_df = pd.DataFrame(rows)

    st.header("📊 Résultat final : Bonferroni + Blocs A/B (014b, 24 cellules)")
    n_passing = result_df["PASSE LES 2 BLOCS"].sum()
    if n_passing == 0:
        st.warning("⚠️ Aucune cellule ne passe le seuil Bonferroni dans les deux blocs.")
    else:
        st.info(f"{n_passing} cellule(s) passent le seuil dans les deux blocs.")

    st.dataframe(result_df, use_container_width=True)

    st.header("⬇️ Télécharger (CSV)")
    buffer = io.StringIO()
    result_df.to_csv(buffer, index=False)
    st.download_button(
        label="📥 Télécharger exp014b_step3_bonferroni_blocks.csv",
        data=buffer.getvalue(),
        file_name="exp014b_step3_bonferroni_blocks.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
