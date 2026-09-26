"""
exp014a_permutation.py
EXP-014 — Mécanisme 014a : ÉTAPE 2 SEULEMENT du pipeline statistique.

Consensus GPT/Gemini/Claude : permutation circulaire, p-values NON corrigées
uniquement. PAS de Bonferroni ici, PAS de blocs temporels A/B ici — ce sera
l'étape 3, une fois ce résultat vérifié.

Les 5 exigences méthodologiques de GPT, respectées comme suit :

1. "Conserve les rendements futurs réellement observés"
   -> On ne recalcule JAMAIS un prix ou un rendement fictif. On précalcule
   une seule fois, pour chaque position possible du calendrier, le rendement
   réel Open(T+1) -> Close(T+1+H) qui aurait résulté d'un signal formé à
   cette date. La permutation ne fait que changer QUELLE position on
   regarde dans ce tableau déjà réel — jamais sa valeur.

2. "Décale les événements de façon circulaire"
   -> np.roll() sur le tableau des signaux (position + direction ensemble).
   Un signal qui sort par la fin revient par le début (roll = circulaire).

3. "Même décalage pour les 6 paires"
   -> Un seul nombre aléatoire k est tiré PAR PERMUTATION (pas par paire).
   Ce même k est appliqué aux 6 paires (modulo leur propre longueur, qui
   diffère très légèrement selon la paire).

4. "Ne crée pas de rendement en traversant une zone invalidée par D-001"
   -> Exactement la même règle que pour les vrais trades (étape 1) :
   si la fenêtre [position du signal, sortie à horizon H] chevauche un
   trou calendaire > 5 jours, ce cas précis est écarté — jamais interpolé
   ou deviné.

5. "Conserve séparément les 4 horizons"
   -> Chaque horizon (1/5/10/20j) a son propre tableau de rendements
   précalculés et son propre test — jamais mélangés entre eux.

Nombre de permutations : 999 (+ le résultat réel = 1000 scénarios comparés).
Graine aléatoire fixée à 2026 pour que ce résultat soit reproductible
exactement par n'importe qui qui relance ce script.
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import io

st.set_page_config(page_title="EXP-014a - Permutation", layout="wide")
st.title("🧪 EXP-014a — Étape 2 : Permutation circulaire (p-values non corrigées)")

UNIVERSE = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X"]
START_DATE = "2006-05-16"

DONCHIAN_N = 20
ATR_WINDOW = 14
ATR_SMA_WINDOW = 20
EXPANSION_THRESHOLD = 1.20
HOLE_THRESHOLD_DAYS = 5
DEDUP_MIN_SESSIONS = 5
HORIZONS = [1, 5, 10, 20]
N_PERMUTATIONS = 999
RANDOM_SEED = 2026


@st.cache_data(show_spinner=False)
def load_data(ticker: str, start: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, progress=False)
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
    """prefix[k] = nombre de 'gros trous' calendaires parmi les positions 0..k-1."""
    diffs = dates.diff().dt.days.fillna(0).values
    big_gap = (diffs > threshold).astype(int)
    return np.concatenate(([0], np.cumsum(big_gap)))


def hole_between(prefix: np.ndarray, start_idx: int, end_idx: int, n: int) -> bool:
    """True si un trou > seuil existe entre start_idx et end_idx (inclus), ou hors limites."""
    if end_idx >= n or start_idx < 0:
        return True
    return (prefix[end_idx + 1] - prefix[start_idx + 1]) > 0


def precompute_forward_returns(opens: np.ndarray, closes: np.ndarray, prefix: np.ndarray,
                                n: int, h: int, entry_is_open: bool):
    """
    Précalcule, pour CHAQUE position possible e du calendrier, le rendement
    réel qui aurait résulté d'une entrée à cette position et une sortie à e+h.
    C'est ce tableau, déjà 100% réel, que la permutation va simplement
    "regarder à une autre position" — jamais recalculer.

    Retourne un tableau numpy de taille n, avec NaN où le trade est invalide
    (hors limites ou trou calendaire chevauché entre e-1 et e+h, pour rester
    cohérent avec la vérification faite sur le signal réel à l'étape 1).
    """
    fr = np.full(n, np.nan)
    for e in range(n):
        exit_idx = e + h
        start_check = e - 1 if entry_is_open else e  # e-1 = position du signal d'origine
        if hole_between(prefix, start_check, exit_idx, n):
            continue
        entry_price = opens[e] if entry_is_open else closes[e]
        exit_price = closes[exit_idx]
        if entry_price == 0 or np.isnan(entry_price) or np.isnan(exit_price):
            continue
        fr[e] = exit_price / entry_price - 1
    return fr


def mean_signal_return(signal_array: np.ndarray, fr_h: np.ndarray, n: int) -> tuple:
    """Rendement moyen du signal (avec direction appliquée), pour un tableau de signaux donné."""
    idx_nonzero = np.nonzero(signal_array)[0]
    trade_returns = []
    for sig_idx in idx_nonzero:
        e = sig_idx + 1  # entrée = Open du jour suivant (T+1)
        if e >= n:
            continue
        val = fr_h[e]
        if np.isnan(val):
            continue
        trade_returns.append(signal_array[sig_idx] * val)
    if len(trade_returns) == 0:
        return None, 0
    return float(np.mean(trade_returns)), len(trade_returns)


def process_pair(ticker: str, progress_callback=None):
    df = load_data(ticker, START_DATE)
    if df.empty:
        return None

    df_signal = compute_signal_014a(df)
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

        # --- Permutations ---
        # Un seul k tiré par permutation ; appliqué à CETTE paire modulo sa
        # propre longueur (le même k "logique" sera redemandé pour les 5
        # autres paires dans la boucle principale, garantissant la synchro).
        perm_excess_values = []
        ks = rng.integers(low=1, high=max(n, 2), size=N_PERMUTATIONS)
        for k in ks:
            k_pair = int(k) % n
            shifted = np.roll(signal_array, k_pair)
            perm_mean, perm_n = mean_signal_return(shifted, fr_signal_h, n)
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
        "**Étape 2 seulement** : permutation circulaire, p-values **non corrigées**. "
        "Toujours pas de Bonferroni, toujours pas de blocs A/B — ce sera l'étape 3."
    )

    with st.expander("📐 Méthodologie (les 5 points exigés par GPT)"):
        st.markdown(
            "1. Rendements toujours réels, jamais recalculés fictivement\n"
            "2. Décalage circulaire (np.roll)\n"
            "3. Même décalage pour les 6 paires à chaque permutation\n"
            "4. Trades traversant un trou D-001 exclus, jamais interpolés\n"
            "5. Les 4 horizons restent toujours séparés\n\n"
            f"Nombre de permutations : {N_PERMUTATIONS} | Graine aléatoire fixe : {RANDOM_SEED} "
            "(reproductible exactement)"
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

    st.header("📊 Résultat étape 2 : p-values non corrigées (24 cellules — 014a seul)")
    st.markdown(
        "⚠️ **Ne pas conclure à ce stade.** Le seuil Bonferroni (0,0010417) "
        "n'est PAS encore appliqué. Comparer ces p-values à 0,05 serait une "
        "erreur — c'est exactement ce que la correction multiple doit éviter."
    )
    st.dataframe(result_df, use_container_width=True)

    st.header("⬇️ Télécharger (CSV, artefact vérifiable de l'étape 2)")
    buffer = io.StringIO()
    result_df.to_csv(buffer, index=False)
    st.download_button(
        label="📥 Télécharger exp014a_permutation.csv",
        data=buffer.getvalue(),
        file_name="exp014a_permutation.csv",
        mime="text/csv",
    )

    st.caption(
        "Prochaine étape (après vérification humaine et des 2 autres IA) : "
        "appliquer le seuil Bonferroni global (α=0,05/48=0,0010417) sur "
        "l'ensemble de la famille statistique (014a + 014b, une fois 014b "
        "codé), puis vérifier la réplication indépendante Bloc A / Bloc B."
    )


if __name__ == "__main__":
    main()
