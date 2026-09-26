"""
exp014b_signal.py
EXP-014 — Mécanisme 014b SEUL (mean-reversion / étirement extrême, Z-score).

Étape 1/plusieurs du pipeline, exactement comme pour 014a : on calcule et
affiche le signal, sans rendement ni test statistique. Objectif : vérifier
que le signal a du sens visuellement avant de construire la suite.

Paramètres verrouillés (CHARTER_EXP-014_v1.0_FINAL.md, section 6) :
- SMA : 20 jours
- Z-score : (Close - SMA20) / Écart-type 20 jours
- Seuil K : Z >= +2,0 (signal short) ou Z <= -2,0 (signal long)
- Entrée : Open du jour suivant le signal (T+1)
- Direction : Long & Short (symétrique)
- Signal binaire : -1 / 0 / +1 (section 7)

Date de fin GELÉE (décision du labo, 2026-09-26) : 2026-09-25 — identique à
014a, pour que toute réplication future donne le même résultat peu importe
quand ce script est relancé.

Gestion des trous (section 3, D-001) : inchangée — aucune interpolation,
seule la paire touchée est invalidée sur la zone concernée.
"""

import streamlit as st
import pandas as pd
import yfinance as yf
import io

st.set_page_config(page_title="EXP-014b - Signal seul", layout="wide")
st.title("🧪 EXP-014b — Signal de mean-reversion (isolé, pas encore de stats)")

UNIVERSE = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X"]
START_DATE = "2006-05-16"
FROZEN_END_DATE = "2026-09-25"  # GELÉE — même date que 014a

# Paramètres verrouillés — NE PAS MODIFIER sans nouvelle version du charter (V1.1)
SMA_WINDOW = 20
ZSCORE_WINDOW = 20
ZSCORE_THRESHOLD = 2.0
HOLE_THRESHOLD_DAYS = 5


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


def mark_invalid_windows(df: pd.DataFrame, max_window: int, hole_threshold: int) -> pd.Series:
    gap_days = df["Date"].diff().dt.days
    has_big_gap = gap_days > hole_threshold
    invalid = has_big_gap.rolling(window=max_window, min_periods=1).max().fillna(0).astype(bool)
    return invalid


def compute_signal_014b(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # SMA(20) et écart-type(20) — calculés sur le Close, jusqu'à la veille
    # (shift(1)) pour ne jamais inclure le jour même dans sa propre moyenne :
    # pas de look-ahead.
    df["sma20"] = df["Close"].shift(1).rolling(SMA_WINDOW).mean()
    df["std20"] = df["Close"].shift(1).rolling(ZSCORE_WINDOW).std()

    df["zscore"] = (df["Close"] - df["sma20"]) / df["std20"]

    # Z >= +2,0 : le prix est anormalement haut -> pari qu'il redescend (short)
    # Z <= -2,0 : le prix est anormalement bas -> pari qu'il remonte (long)
    df["signal_014b"] = 0
    df.loc[df["zscore"] >= ZSCORE_THRESHOLD, "signal_014b"] = -1
    df.loc[df["zscore"] <= -ZSCORE_THRESHOLD, "signal_014b"] = 1

    max_window_used = max(SMA_WINDOW, ZSCORE_WINDOW)
    invalid_mask = mark_invalid_windows(df, max_window_used, HOLE_THRESHOLD_DAYS)
    df.loc[invalid_mask, "signal_014b"] = 0
    df["fenetre_invalide"] = invalid_mask

    return df


def main():
    st.markdown(
        f"Date de fin gelée : **{FROZEN_END_DATE}** (identique à 014a). "
        "Ce script calcule **seulement** le signal 014b, paire par paire. "
        "Pas de rendement, pas de test statistique."
    )

    summary_rows = []
    all_signals = {}

    with st.spinner("Calcul en cours..."):
        for ticker in UNIVERSE:
            df = load_data(ticker, START_DATE, FROZEN_END_DATE)
            if df.empty:
                st.error(f"⚠️ Échec de téléchargement pour {ticker}")
                continue
            df_signal = compute_signal_014b(df)
            all_signals[ticker] = df_signal

            n_long = (df_signal["signal_014b"] == 1).sum()
            n_short = (df_signal["signal_014b"] == -1).sum()
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

    st.header("🔍 Détail d'une paire (aperçu à l'écran, pas besoin de télécharger séparément)")
    chosen = st.selectbox("Choisir une paire à inspecter", UNIVERSE)
    if chosen in all_signals:
        df_chosen = all_signals[chosen]
        signals_only = df_chosen[df_chosen["signal_014b"] != 0][
            ["Date", "Close", "sma20", "zscore", "signal_014b"]
        ]
        st.write(f"{len(signals_only)} signaux trouvés pour {chosen} :")
        st.dataframe(signals_only, use_container_width=True)

    st.header("⬇️ Télécharger TOUT en un seul fichier (résumé + les 6 paires)")
    buffer = io.StringIO()
    buffer.write("=== RÉSUMÉ PAR PAIRE ===\n")
    summary_df.to_csv(buffer, index=False)
    for ticker, df_sig in all_signals.items():
        buffer.write(f"\n=== DÉTAIL SIGNAUX — {ticker} ===\n")
        signals_only = df_sig[df_sig["signal_014b"] != 0][
            ["Date", "Close", "sma20", "zscore", "signal_014b"]
        ]
        signals_only.to_csv(buffer, index=False)

    st.download_button(
        label="📥 Télécharger exp014b_signal.csv (un seul fichier)",
        data=buffer.getvalue(),
        file_name="exp014b_signal.csv",
        mime="text/csv",
    )

    st.caption(
        "Prochaine étape (une fois ce signal validé visuellement) : "
        "ajouter le calcul de rendement aux horizons +1/+5/+10/+20 jours, "
        "exactement comme pour 014a."
    )


if __name__ == "__main__":
    main()
