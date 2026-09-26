"""
exp014a_returns.py
EXP-014 — Mécanisme 014a : calcul des RENDEMENTS BRUTS aux 4 horizons.

Étape 2/plusieurs du pipeline. Toujours PAS de test statistique ici
(Bonferroni, permutation, blocs temporels = étape suivante).

Paramètres verrouillés (CHARTER_EXP-014_v1.0_FINAL.md) :
- Entrée : Open du jour suivant le signal (T+1)
- Sortie : Close à horizon H après l'entrée (section 8 : pas de sortie
  conditionnelle, horizon fixe uniquement)
- Horizons testés : +1, +5, +10, +20 jours (section 10)
- Déduplication (section 12) : un signal sur une même paire n'est conservé
  que s'il survient au moins 5 séances après le signal précédent (même paire)
- Rendement brut (formule Gemini) :
    trade_return = signal * (Close_sortie / Open_entrée - 1)
  où signal = +1 (long) ou -1 (short), donc un short profite d'une baisse.
- Une fenêtre de détention qui chevauche un trou calendaire > 5 jours
  (D-001) invalide ce trade précis pour cet horizon — exclu, pas interpolé.
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import io

st.set_page_config(page_title="EXP-014a - Rendements", layout="wide")
st.title("🧪 EXP-014a — Rendements bruts (toujours pas de stats)")

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
    """
    Charter section 12 : un signal n'est conservé que s'il est à au moins
    `min_sessions` séances du dernier signal CONSERVÉ sur cette même paire.
    """
    df = df.copy()
    df["signal_kept"] = 0
    last_kept_idx = None
    for idx in df.index[df["signal_014a"] != 0]:
        if last_kept_idx is None or (idx - last_kept_idx) >= min_sessions:
            df.at[idx, "signal_kept"] = df.at[idx, "signal_014a"]
            last_kept_idx = idx
    return df


def has_hole_in_range(dates: pd.Series, start_idx: int, end_idx: int, threshold: int) -> bool:
    """Vérifie si un trou > threshold jours calendaires existe entre start_idx et end_idx (inclus)."""
    if start_idx < 0 or end_idx >= len(dates):
        return True  # hors limites = pas de données = invalide
    segment = dates.iloc[start_idx:end_idx + 1].reset_index(drop=True)
    gaps = segment.diff().dt.days
    return bool((gaps > threshold).any())


def compute_returns(df: pd.DataFrame, horizons: list, hole_threshold: int) -> pd.DataFrame:
    """
    Pour chaque signal conservé (signal_kept != 0) :
    - Entrée = Open à l'index du signal + 1 (T+1)
    - Sortie = Close à l'index du signal + 1 + H
    - Trade invalide si la fenêtre [signal_idx, entrée+H] contient un trou > seuil,
      ou si les index sortent des données disponibles.
    """
    rows = []
    signal_indices = df.index[df["signal_kept"] != 0].tolist()

    for sig_idx in signal_indices:
        entry_idx = sig_idx + 1
        direction = df.at[sig_idx, "signal_kept"]
        signal_date = df.at[sig_idx, "Date"]

        if entry_idx >= len(df):
            continue  # pas assez de données pour entrer

        entry_price = df.at[entry_idx, "Open"]
        row = {
            "date_signal": signal_date,
            "direction": int(direction),
            "entry_idx": entry_idx,
            "entry_price": entry_price,
        }

        for h in horizons:
            exit_idx = entry_idx + h
            col_ret = f"ret_{h}d"
            col_valid = f"valid_{h}d"

            if exit_idx >= len(df):
                row[col_ret] = None
                row[col_valid] = False
                continue

            hole_found = has_hole_in_range(df["Date"], sig_idx, exit_idx, hole_threshold)
            if hole_found:
                row[col_ret] = None
                row[col_valid] = False
                continue

            exit_price = df.at[exit_idx, "Close"]
            trade_return = direction * (exit_price / entry_price - 1)
            row[col_ret] = trade_return
            row[col_valid] = True

        rows.append(row)

    return pd.DataFrame(rows)


def main():
    st.markdown(
        "Calcul des rendements bruts pour le signal 014a, aux horizons "
        "+1/+5/+10/+20 jours. **Toujours aucun test statistique** — "
        "juste les rendements individuels de chaque trade."
    )

    summary_rows = []
    all_returns = {}

    with st.spinner("Calcul en cours..."):
        for ticker in UNIVERSE:
            df = load_data(ticker, START_DATE)
            if df.empty:
                st.error(f"⚠️ Échec de téléchargement pour {ticker}")
                continue

            df_signal = compute_signal_014a(df)
            df_dedup = apply_dedup(df_signal, DEDUP_MIN_SESSIONS)
            df_returns = compute_returns(df_dedup, HORIZONS, HOLE_THRESHOLD_DAYS)
            all_returns[ticker] = df_returns

            n_signals_raw = (df_signal["signal_014a"] != 0).sum()
            n_signals_kept = (df_dedup["signal_kept"] != 0).sum()

            row = {
                "Paire": ticker,
                "Signaux bruts": int(n_signals_raw),
                "Signaux après dédup": int(n_signals_kept),
            }
            for h in HORIZONS:
                col = f"ret_{h}d"
                valid_col = f"valid_{h}d"
                if col in df_returns.columns:
                    n_valid = df_returns[valid_col].sum()
                    avg_ret = df_returns.loc[df_returns[valid_col], col].mean()
                    row[f"Trades valides {h}j"] = int(n_valid)
                    row[f"Rendement moyen {h}j"] = round(avg_ret * 100, 3) if pd.notna(avg_ret) else None
                else:
                    row[f"Trades valides {h}j"] = 0
                    row[f"Rendement moyen {h}j"] = None

            summary_rows.append(row)

    st.header("📊 Résumé par paire (descriptif — pas encore de test statistique)")
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, use_container_width=True)

    st.header("🔍 Détail d'une paire")
    chosen = st.selectbox("Choisir une paire", UNIVERSE)
    if chosen in all_returns and not all_returns[chosen].empty:
        st.dataframe(all_returns[chosen], use_container_width=True)
    else:
        st.write("Aucun trade pour cette paire.")

    st.header("⬇️ Télécharger tout (CSV, un seul fichier)")
    buffer = io.StringIO()
    buffer.write("=== RÉSUMÉ PAR PAIRE ===\n")
    summary_df.to_csv(buffer, index=False)
    for ticker, df_ret in all_returns.items():
        buffer.write(f"\n=== DÉTAIL TRADES — {ticker} ===\n")
        df_ret.to_csv(buffer, index=False)

    st.download_button(
        label="📥 Télécharger exp014a_returns.csv",
        data=buffer.getvalue(),
        file_name="exp014a_returns.csv",
        mime="text/csv",
    )

    st.caption(
        "Prochaine étape (après vérification de ces résultats) : baseline "
        "inconditionnelle, excess return, permutation circulaire, correction "
        "Bonferroni (α=0,0010417 sur 48 cellules), réplication Bloc A / Bloc B."
    )


if __name__ == "__main__":
    main()
