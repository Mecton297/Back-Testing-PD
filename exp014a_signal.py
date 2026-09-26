"""
exp014a_signal.py
EXP-014 — Mécanisme 014a SEUL (breakout / expansion de volatilité).

Étape 1/plusieurs du pipeline : on calcule et affiche le signal, sans encore
mesurer de rendement ni faire de test statistique. Objectif : vérifier que le
signal a du sens avant de construire la suite.

Paramètres verrouillés (CHARTER_EXP-014_v1.0_FINAL.md, section 5) :
- Canal Donchian : N = 20
- ATR : fenêtre 14
- Seuil d'expansion : ATR(14) >= 1,20 x SMA20(ATR(14))
- Entrée : Open du jour suivant le signal (T+1)
- Direction : Long & Short (symétrique)
- Signal binaire : -1 / 0 / +1 (section 7)

Gestion des trous (section 3, D-001) : aucune interpolation. Une fenêtre de
calcul (Donchian/ATR/SMA) qui chevauche un trou > 5 jours calendaires est
invalidée pour cette paire, sur cette zone uniquement.
"""

import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="EXP-014a - Signal seul", layout="wide")
st.title("🧪 EXP-014a — Signal de breakout (isolé, pas encore de stats)")

UNIVERSE = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X"]
START_DATE = "2006-05-16"

# Paramètres verrouillés — NE PAS MODIFIER sans nouvelle version du charter (V1.1)
DONCHIAN_N = 20
ATR_WINDOW = 14
ATR_SMA_WINDOW = 20
EXPANSION_THRESHOLD = 1.20
HOLE_THRESHOLD_DAYS = 5


@st.cache_data(show_spinner=False)
def load_data(ticker: str, start: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, progress=False)
    if df.empty:
        return df
    df = df.reset_index()
    if "Date" not in df.columns:
        df = df.rename(columns={df.columns[0]: "Date"})
    df["Date"] = pd.to_datetime(df["Date"])
    # yfinance peut renvoyer des colonnes multi-niveaux selon la version ;
    # on aplatit si besoin pour retomber sur Open/High/Low/Close simples.
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
    """
    Retourne un masque booléen : True si la fenêtre de calcul se terminant à
    cette ligne (sur max_window jours précédents) chevauche un trou calendaire
    > hole_threshold jours. Ces lignes seront exclues du signal (D-001).
    """
    gap_days = df["Date"].diff().dt.days
    has_big_gap = gap_days > hole_threshold
    # Une ligne est invalide si un "gros trou" apparaît n'importe où dans les
    # max_window lignes précédentes (fenêtre glissante).
    invalid = has_big_gap.rolling(window=max_window, min_periods=1).max().fillna(0).astype(bool)
    return invalid


def compute_signal_014a(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Canal Donchian(20) : plus haut et plus bas des 20 jours précédents
    # (on décale de 1 pour ne pas inclure le jour même : pas de look-ahead)
    df["donchian_high"] = df["High"].shift(1).rolling(DONCHIAN_N).max()
    df["donchian_low"] = df["Low"].shift(1).rolling(DONCHIAN_N).min()

    # ATR(14)
    df["true_range"] = compute_true_range(df)
    df["atr14"] = df["true_range"].rolling(ATR_WINDOW).mean()

    # Expansion de volatilité : ATR14 vs sa propre moyenne mobile 20 jours
    df["atr14_sma20"] = df["atr14"].rolling(ATR_SMA_WINDOW).mean()
    df["expansion_ratio"] = df["atr14"] / df["atr14_sma20"]
    df["expansion_ok"] = df["expansion_ratio"] >= EXPANSION_THRESHOLD

    # Direction du breakout : Close au-dessus du plus haut Donchian = long ;
    # en dessous du plus bas Donchian = short.
    breakout_up = df["Close"] > df["donchian_high"]
    breakout_down = df["Close"] < df["donchian_low"]

    df["signal_014a"] = 0
    df.loc[breakout_up & df["expansion_ok"], "signal_014a"] = 1
    df.loc[breakout_down & df["expansion_ok"], "signal_014a"] = -1

    # Fenêtre la plus longue utilisée dans ce calcul : max(Donchian, ATR+SMA)
    max_window_used = max(DONCHIAN_N, ATR_WINDOW + ATR_SMA_WINDOW)
    invalid_mask = mark_invalid_windows(df, max_window_used, HOLE_THRESHOLD_DAYS)
    df.loc[invalid_mask, "signal_014a"] = 0
    df["fenetre_invalide"] = invalid_mask

    return df


def main():
    st.markdown(
        "Ce script calcule **seulement** le signal 014a, paire par paire. "
        "Pas de rendement, pas de test statistique — on vérifie d'abord "
        "que le signal a du sens visuellement."
    )

    summary_rows = []
    all_signals = {}

    with st.spinner("Calcul en cours..."):
        for ticker in UNIVERSE:
            df = load_data(ticker, START_DATE)
            if df.empty:
                st.error(f"⚠️ Échec de téléchargement pour {ticker}")
                continue
            df_signal = compute_signal_014a(df)
            all_signals[ticker] = df_signal

            n_long = (df_signal["signal_014a"] == 1).sum()
            n_short = (df_signal["signal_014a"] == -1).sum()
            n_invalid = df_signal["fenetre_invalide"].sum()

            summary_rows.append({
                "Paire": ticker,
                "Jours total": len(df_signal),
                "Signaux Long (+1)": int(n_long),
                "Signaux Short (-1)": int(n_short),
                "Jours en fenêtre invalide (trou)": int(n_invalid),
            })

    st.header("📊 Résumé par paire")
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, use_container_width=True)

    st.header("🔍 Détail d'une paire (pour vérifier visuellement)")
    chosen = st.selectbox("Choisir une paire à inspecter", UNIVERSE)
    if chosen in all_signals:
        df_chosen = all_signals[chosen]
        signals_only = df_chosen[df_chosen["signal_014a"] != 0][
            ["Date", "Close", "donchian_high", "donchian_low", "expansion_ratio", "signal_014a"]
        ]
        st.write(f"{len(signals_only)} signaux trouvés pour {chosen} :")
        st.dataframe(signals_only, use_container_width=True)

    st.caption(
        "Prochaine étape (une fois ce signal validé visuellement) : "
        "ajouter le calcul de rendement aux horizons +1/+5/+10/+20 jours."
    )


if __name__ == "__main__":
    main()
