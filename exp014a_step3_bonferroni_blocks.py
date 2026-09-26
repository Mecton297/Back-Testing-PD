"""
exp014a_step3_bonferroni_blocks.py
EXP-014 — Mécanisme 014a : ÉTAPE 3 — Date gelée + Bonferroni + Blocs A/B.

CORRECTION DE PROCÉDURE (consensus GPT/Gemini/Claude) :
La date de fin est maintenant GELÉE (FROZEN_END_DATE ci-dessous), au lieu de
retélécharger "jusqu'à aujourd'hui" à chaque exécution. Ce script produira
désormais EXACTEMENT le même résultat peu importe quand il est relancé.

Date choisie : 2026-09-25, correspondant à la "Dernière mise à jour" déjà
inscrite dans LAB_STATE.md AVANT le calcul de ces rendements — donc non
choisie en fonction des résultats (règle GPT respectée).

Ce script fait DEUX choses, dans l'ordre :
1. Applique le seuil Bonferroni pré-enregistré (α = 0,05/48 = 0,0010417) —
   ce seuil est fixe depuis le charter, indépendant du fait que 014b ne soit
   pas encore codé.
2. Réplique le test indépendamment sur Bloc A (2006-05-16 à 2015-12-31) et
   Bloc B (2016-01-01 à la date gelée), avec permutation confinée à
   l'intérieur de chaque bloc (aucune fuite d'un bloc vers l'autre pour le
   calcul des rendements ou de la distribution nulle).

⚠️ Ce script ne couvre que 014a (24 cellules sur les 48 prévus). Le verdict
de validation complet (charter section 17) exige aussi 014b — ce résultat
est donc un résultat INTERMÉDIAIRE et honnête, pas une conclusion finale.
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import io

st.set_page_config(page_title="EXP-014a - Étape 3", layout="wide")
st.title("🧪 EXP-014a — Étape 3 : Bonferroni + Blocs A/B (date gelée)")

UNIVERSE = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X"]
START_DATE = "2006-05-16"
FROZEN_END_DATE = "2026-09-25"  # GELÉE — voir justification dans le docstring

BLOCK_A_END = "2015-12-31"
BLOCK_B_START = "2016-01-01"

DONCHIAN_N = 20
ATR_WINDOW = 14
ATR_SMA_WINDOW = 20
EXPANSION_THRESHOLD = 1.20
HOLE_THRESHOLD_DAYS = 5
DEDUP_MIN_SESSIONS = 5
HORIZONS = [1, 5, 10, 20]
N_PERMUTATIONS = 999
RANDOM_SEED = 2026

# Seuil pré-enregistré, charter section 14 — famille complète = 48 cellules
# (2 mécanismes x 6 paires x 4 horizons), fixé AVANT tout résultat.
BONFERRONI_ALPHA = 0.05 / 48  # = 0.0010417


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


def compute_true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["Close"].shift(1)
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - prev_close).abs()
    tr3 = (df["Low"] - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def compute_signal_014a(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculé sur la SÉRIE COMPLÈTE (pas bloc par bloc) : un indicateur a le
    droit d'utiliser l'historique passé, même s'il chevauche un bloc voisin.
    Seul le RENDEMENT FUTUR (ce qu'on mesure) sera cloisonné par bloc plus
    bas, pour garantir l'indépendance réelle du test de réplication.
    """
    df = df.copy()
    df["donchian_high"] = df["High"].shift(1).rolling(DONCHIAN_N).max()
    df["donchian_low"] = df["Low"].shift(1).rolling(DONCHIAN_N).min()
    df["true_range"] = compute_true_range(df)
    df["atr14"] = df["true_range"].rolling(ATR_WINDOW).mean()
    df["atr14_sma20"] = df["atr14"].rolling(ATR_SMA_WINDOW).mean()
    df["expansion_ratio"] = df["atr14"] / df["atr14_sma20"]
    df["expansion_ok"] = df["expansion_ratio"] >= EXPANSION_THRESHOLD

    breakout_up = df["Close"] > df["donchian_high"]
    breakout_down = df["Close"] < df["donchian_low"]

    df["signal_014a"] = 0
    df.loc[breakout_up & df["expansion_ok"], "signal_014a"] = 1
    df.loc[breakout_down & df["expansion_ok"], "signal_014a"] = -1
    return df


def apply_dedup(df: pd.DataFrame, min_sessions: int) -> pd.DataFrame:
    df = df.copy()
    df["signal_kept"] = 0
    last_kept_idx = None
    for idx in df.index[df["signal_014a"] != 0]:
        if last_kept_idx is None or (idx - last_kept_idx) >= min_sessions:
            df.at[idx, "signal_kept"] = df.at[idx, "signal_014a"]
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
    """
    Applique le test complet (baseline, excess return, permutation) SUR CE
    BLOC SEUL — aucune donnée d'un autre bloc n'entre dans le calcul du
    rendement ou de la distribution nulle. C'est ce qui garantit une
    réplication réellement indépendante.
    """
    block_df = block_df.reset_index(drop=True)
    n = len(block_df)
    if n < 60:  # bloc trop court pour être exploitable (garde-fou minimal)
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

    df_signal = compute_signal_014a(df)
    df_dedup = apply_dedup(df_signal, DEDUP_MIN_SESSIONS)

    block_a = df_dedup[df_dedup["Date"] <= BLOCK_A_END]
    block_b = df_dedup[df_dedup["Date"] >= BLOCK_B_START]

    results_a = test_block(block_a, seed_offset=1)
    results_b = test_block(block_b, seed_offset=2)

    return results_a, results_b


def main():
    st.markdown(
        f"**Date de fin gelée : {FROZEN_END_DATE}** — ce script donne "
        "désormais toujours le même résultat, peu importe quand il est relancé."
    )
    st.markdown(
        f"**Seuil Bonferroni pré-enregistré : α = {BONFERRONI_ALPHA:.7f}** "
        "(0,05 / 48 cellules — famille complète 014a+014b, fixée avant tout résultat)"
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

    st.header("📊 Résultat étape 3 : Bonferroni + Blocs A/B (014a seul, 24 cellules)")
    n_passing = result_df["PASSE LES 2 BLOCS"].sum()
    if n_passing == 0:
        st.warning(
            "⚠️ Aucune cellule ne passe le seuil Bonferroni dans les DEUX blocs. "
            "Ce n'est pas un échec — c'est exactement ce que ce protocole est "
            "conçu pour détecter honnêtement."
        )
    else:
        st.info(f"{n_passing} cellule(s) passent le seuil dans les deux blocs — voir tableau, à examiner avec prudence.")

    st.dataframe(result_df, use_container_width=True)

    st.markdown(
        "⚠️ **Rappel important** : ce résultat ne couvre que 014a. La "
        "validation finale (charter section 17) exige aussi 014b, et "
        "l'absence d'explication post-hoc. Ceci reste un résultat "
        "intermédiaire, pas un verdict."
    )

    st.header("⬇️ Télécharger (CSV, artefact vérifiable de l'étape 3)")
    buffer = io.StringIO()
    result_df.to_csv(buffer, index=False)
    st.download_button(
        label="📥 Télécharger exp014a_step3_bonferroni_blocks.csv",
        data=buffer.getvalue(),
        file_name="exp014a_step3_bonferroni_blocks.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
