"""
exp014a_baseline_excess.py
EXP-014 — Mécanisme 014a : ÉTAPE 1 SEULEMENT du pipeline statistique.

Consensus GPT/Gemini/Claude : étape par étape, avec point de contrôle
vérifiable après chacune. Cette étape fait UNIQUEMENT :
  1. Baseline inconditionnelle par paire et par horizon
  2. Excess return = rendement du signal − baseline
  3. N brut vs N effectif après déduplication (déjà connu, réaffiché ici
     pour traçabilité complète dans cet artefact)

PAS de permutation, PAS de p-value, PAS de Bonferroni ici — étapes suivantes,
une fois ce résultat vérifié.

Aucun paramètre du charter modifié. Aucune interprétation de performance
n'est faite : ces chiffres sont encore descriptifs (excess return brut,
avant test de significativité).
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import io

st.set_page_config(page_title="EXP-014a - Baseline & Excess Return", layout="wide")
st.title("🧪 EXP-014a — Étape 1 : Baseline & Excess Return")

UNIVERSE = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X"]
START_DATE = "2006-05-16"

DONCHIAN_N = 20
ATR_WINDOW = 14
ATR_SMA_WINDOW = 20
EXPANSION_THRESHOLD = 1.20
HOLE_THRESHOLD_DAYS = 5
DEDUP_MIN_SESSIONS = 5
HORIZONS = [1, 5, 10, 20]


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


def mark_invalid_windows(df: pd.DataFrame, max_window: int, hole_threshold: int) -> pd.Series:
    gap_days = df["Date"].diff().dt.days
    has_big_gap = gap_days > hole_threshold
    invalid = has_big_gap.rolling(window=max_window, min_periods=1).max().fillna(0).astype(bool)
    return invalid


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

    max_window_used = max(DONCHIAN_N, ATR_WINDOW + ATR_SMA_WINDOW)
    invalid_mask = mark_invalid_windows(df, max_window_used, HOLE_THRESHOLD_DAYS)
    df.loc[invalid_mask, "signal_014a"] = 0
    df["fenetre_invalide"] = invalid_mask

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


def has_hole_in_range(dates: pd.Series, start_idx: int, end_idx: int, threshold: int) -> bool:
    if start_idx < 0 or end_idx >= len(dates):
        return True
    segment = dates.iloc[start_idx:end_idx + 1].reset_index(drop=True)
    gaps = segment.diff().dt.days
    return bool((gaps > threshold).any())


def compute_trade_returns(df: pd.DataFrame, horizons: list, hole_threshold: int) -> pd.DataFrame:
    """Rendements des trades du signal (identique à exp014a_returns.py)."""
    rows = []
    signal_indices = df.index[df["signal_kept"] != 0].tolist()

    for sig_idx in signal_indices:
        entry_idx = sig_idx + 1
        direction = df.at[sig_idx, "signal_kept"]
        if entry_idx >= len(df):
            continue
        entry_price = df.at[entry_idx, "Open"]
        row = {"date_signal": df.at[sig_idx, "Date"], "direction": int(direction)}

        for h in horizons:
            exit_idx = entry_idx + h
            col_ret, col_valid = f"ret_{h}d", f"valid_{h}d"
            if exit_idx >= len(df) or has_hole_in_range(df["Date"], sig_idx, exit_idx, hole_threshold):
                row[col_ret], row[col_valid] = None, False
                continue
            exit_price = df.at[exit_idx, "Close"]
            row[col_ret] = direction * (exit_price / entry_price - 1)
            row[col_valid] = True

        rows.append(row)

    return pd.DataFrame(rows)


def compute_baseline(df: pd.DataFrame, horizons: list, hole_threshold: int) -> dict:
    """
    Baseline inconditionnelle par horizon : rendement moyen de TOUS les jours
    valides (pas seulement les jours de signal), Close-to-Close sur H jours,
    sans notion de direction (on prend le rendement brut, pas signé, puisqu'il
    n'y a pas de "signal" à orienter la baseline).

    On exclut toute fenêtre qui chevauche un trou > hole_threshold jours,
    exactement comme pour les trades du signal (D-001 appliqué uniformément).
    """
    baseline = {}
    n = len(df)
    for h in horizons:
        rets = []
        for i in range(n - h):
            j = i + h
            if has_hole_in_range(df["Date"], i, j, hole_threshold):
                continue
            entry_price = df.at[i, "Close"]
            exit_price = df.at[j, "Close"]
            if entry_price == 0 or pd.isna(entry_price) or pd.isna(exit_price):
                continue
            rets.append(exit_price / entry_price - 1)
        baseline[h] = {
            "baseline_mean_return": (sum(rets) / len(rets)) if rets else None,
            "baseline_n": len(rets),
        }
    return baseline


def main():
    st.markdown(
        "**Étape 1 seulement** : baseline inconditionnelle + excess return. "
        "Pas de permutation, pas de p-value, pas de Bonferroni ici — "
        "ce sera l'étape 2, une fois ce résultat vérifié."
    )

    summary_rows = []

    with st.spinner("Calcul en cours (la baseline est plus lente, elle regarde tous les jours)..."):
        for ticker in UNIVERSE:
            df = load_data(ticker, START_DATE)
            if df.empty:
                st.error(f"⚠️ Échec de téléchargement pour {ticker}")
                continue

            df_signal = compute_signal_014a(df)
            df_dedup = apply_dedup(df_signal, DEDUP_MIN_SESSIONS)
            df_trades = compute_trade_returns(df_dedup, HORIZONS, HOLE_THRESHOLD_DAYS)
            baseline = compute_baseline(df_dedup, HORIZONS, HOLE_THRESHOLD_DAYS)

            n_raw = int((df_signal["signal_014a"] != 0).sum())
            n_kept = int((df_dedup["signal_kept"] != 0).sum())

            row = {
                "Paire": ticker,
                "Signaux bruts": n_raw,
                "Signaux après dédup": n_kept,
            }

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

    st.header("📊 Résultat étape 1 : Baseline & Excess Return par paire")
    st.markdown(
        "**Rappel :** un excess return positif ou négatif ici n'est PAS "
        "encore une preuve de quoi que ce soit — c'est juste la mesure brute, "
        "avant test de significativité (étape 2 et 3)."
    )
    st.dataframe(summary_df, use_container_width=True)

    st.header("⬇️ Télécharger (CSV, artefact vérifiable de l'étape 1)")
    buffer = io.StringIO()
    summary_df.to_csv(buffer, index=False)
    st.download_button(
        label="📥 Télécharger exp014a_baseline_excess.csv",
        data=buffer.getvalue(),
        file_name="exp014a_baseline_excess.csv",
        mime="text/csv",
    )

    st.caption(
        "Consigne du labo respectée : aucun paramètre du charter modifié, "
        "aucune interprétation de performance. Prochaine étape (après "
        "vérification humaine) : permutation circulaire synchronisée sur "
        "les 6 paires, pour obtenir les p-values non corrigées."
    )


if __name__ == "__main__":
    main()
