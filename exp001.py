import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-001 / V1.0", layout="centered")
st.title("🔬 EXP-001 / V1.0")
st.caption("Étude événementielle du signal d'entrée SMI — aucune règle de sortie, aucune optimisation")

# ================================================================
# SMI (10,3,3,EMA) + Signal EMA(10) — formule verrouillée et validée
# empiriquement le 24 sept 2026 contre les valeurs réelles du
# graphique Yahoo (Stch Mtm) pour XEG.TO, deux dates test.
# ================================================================
def compute_smi(df, n1=10, s1=3, s2=3, n2=10):
    """
    df: colonnes 'high','low','close', index = dates croissantes.
    SMI = 200 * EMA(EMA(d, s1), s2) / EMA(EMA(r, s1), s2)
    Signal = EMA(SMI, n2)
    """
    hh = df["high"].rolling(n1).max()
    ll = df["low"].rolling(n1).min()
    d = df["close"] - (hh + ll) / 2
    r = hh - ll
    d1 = d.ewm(span=s1, adjust=False).mean()
    d2 = d1.ewm(span=s2, adjust=False).mean()
    r1 = r.ewm(span=s1, adjust=False).mean()
    r2 = r1.ewm(span=s2, adjust=False).mean()
    smi = 200 * d2 / r2
    signal = smi.ewm(span=n2, adjust=False).mean()
    out = df.copy()
    out["SMI"] = smi
    out["Signal"] = signal
    return out


def build_weekly(daily_df):
    """
    Bougies hebdomadaires (semaine se terminant vendredi), en éliminant
    la dernière semaine si elle est encore en formation (zéro look-ahead).
    """
    weekly = daily_df.resample("W-FRI").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()

    last_daily_date = daily_df.index[-1]
    if len(weekly) and weekly.index[-1] > last_daily_date:
        weekly = weekly.iloc[:-1]

    return weekly


def rule_C_weekly_cross(weekly_smi):
    """Événement hebdo: le SMI franchit le zéro à la hausse."""
    smi = weekly_smi["SMI"]
    return (smi > 0) & (smi.shift(1) <= 0)


def rule_D_daily(daily_smi, k=5):
    """
    Événement quotidien:
    - croisement haussier SMI/Signal aujourd'hui
    - ET une sortie de -40 (SMI passe de <-40 à >=-40) dans les k
      séances précédentes OU la séance actuelle.
    """
    smi = daily_smi["SMI"]
    signal = daily_smi["Signal"]

    cross_up = (smi > signal) & (smi.shift(1) <= signal.shift(1))
    exit_oversold = (smi >= -40) & (smi.shift(1) < -40)
    recent_exit = exit_oversold.rolling(k + 1, min_periods=1).max().astype(bool)

    return (cross_up & recent_exit).fillna(False)


def forward_returns(close, event_mask, horizons=(5, 10, 20, 60)):
    """
    Pour chaque jour marqué par event_mask, calcule le rendement du close
    entre ce jour et N séances plus tard, pour chaque horizon N.
    """
    event_mask = event_mask.reindex(close.index, fill_value=False)
    event_dates = close.index[event_mask]
    idx_map = {date: i for i, date in enumerate(close.index)}
    n = len(close)

    results = {}
    for h in horizons:
        rets = []
        for d in event_dates:
            i = idx_map[d]
            if i + h < n:
                rets.append((close.iloc[i + h] / close.iloc[i] - 1) * 100)
        results[h] = pd.Series(rets, dtype=float)

    return results, len(event_dates)


def build_event_log(close, event_mask, ticker, subset_label, horizons=(5, 10, 20, 60)):
    """
    Construit le journal événementiel: une ligne par signal, avec le
    rendement à chaque horizon (NaN si l'horizon dépasse la fin des données).
    """
    event_mask = event_mask.reindex(close.index, fill_value=False)
    event_dates = close.index[event_mask]
    idx_map = {date: i for i, date in enumerate(close.index)}
    n = len(close)

    rows = []
    for d in event_dates:
        i = idx_map[d]
        row = {"date": d.strftime("%Y-%m-%d"), "ticker": ticker, "sous_ensemble": subset_label}
        for h in horizons:
            if i + h < n:
                row[f"ret_{h}"] = round((close.iloc[i + h] / close.iloc[i] - 1) * 100, 4)
            else:
                row[f"ret_{h}"] = None
        rows.append(row)

    return pd.DataFrame(rows)


def summarize(rets_dict):
    rows = []
    for h, rets in rets_dict.items():
        if len(rets) == 0:
            rows.append({
                "Horizon (séances)": h, "N exploitables": 0,
                "Rendement moyen %": None, "Rendement médian %": None,
                "% positifs": None, "Meilleur %": None, "Pire %": None,
                "Écart-type %": None,
            })
            continue
        rows.append({
            "Horizon (séances)": h,
            "N exploitables": len(rets),
            "Rendement moyen %": round(rets.mean(), 2),
            "Rendement médian %": round(rets.median(), 2),
            "% positifs": round((rets > 0).mean() * 100, 1),
            "Meilleur %": round(rets.max(), 2),
            "Pire %": round(rets.min(), 2),
            "Écart-type %": round(rets.std(), 2),
        })
    return pd.DataFrame(rows)


# ================================================================
# INTERFACE
# ================================================================
ticker = st.text_input("Symbole (ex: XEG.TO)", value="XEG.TO")
years = st.slider("Historique à télécharger (années)", 5, 15, 10)
K = 5  # verrouillé — sortie de survente dans les k dernières séances

if st.button("Lancer EXP-001 / V1.0"):
    with st.spinner("Téléchargement des données..."):
        raw = yf.Ticker(ticker).history(period=f"{years}y", auto_adjust=False)
        raw.columns = [c.lower() for c in raw.columns]
        raw.index = raw.index.tz_localize(None)

    if raw.empty:
        st.error("Aucune donnée trouvée pour ce symbole.")
        st.stop()

    daily = compute_smi(raw[["high", "low", "close"]].copy())
    weekly_raw = build_weekly(raw[["open", "high", "low", "close"]])
    weekly = compute_smi(weekly_raw)

    # --- Événements ---
    ev_C_weekly = rule_C_weekly_cross(weekly)          # indexé par semaine
    ev_D_daily = rule_D_daily(daily, k=K)               # indexé par jour

    # État hebdo (SMI hebdo > 0) reporté sur la grille quotidienne,
    # en n'utilisant QUE les semaines déjà complètement closes à la date t
    # (ffill = backward-looking, aucune semaine future n'est utilisée).
    weekly_positive = pd.Series(weekly["SMI"].values > 0, index=weekly.index)
    weekly_positive_daily = weekly_positive.reindex(daily.index, method="ffill").fillna(False)

    ev_combo = ev_D_daily & weekly_positive_daily

    # Le signal hebdo C doit être testé aux dates de clôture hebdo (vendredis)
    ev_C_dates = ev_C_weekly[ev_C_weekly].index
    ev_C_daily_mask = pd.Series(daily.index.isin(ev_C_dates), index=daily.index)

    st.subheader(f"Résultats — {ticker}")
    st.caption(f"{len(raw)} séances quotidiennes · {len(weekly)} semaines complètes utilisées")

    st.markdown("### 📅 Signal hebdomadaire seul (règle C — franchissement du zéro)")
    rets_C, n_C = forward_returns(daily["close"], ev_C_daily_mask)
    st.write(f"Nombre total de signaux : **{n_C}**")
    st.dataframe(summarize(rets_C), hide_index=True)

    st.markdown("### 📆 Signal quotidien seul (règle D — croisement + sortie survente)")
    rets_D, n_D = forward_returns(daily["close"], ev_D_daily)
    st.write(f"Nombre total de signaux : **{n_D}**")
    st.dataframe(summarize(rets_D), hide_index=True)

    st.markdown("### 🔗 Signal combiné (D quotidien + SMI hebdo > 0)")
    rets_combo, n_combo = forward_returns(daily["close"], ev_combo)
    st.write(f"Nombre total de signaux : **{n_combo}**")
    st.dataframe(summarize(rets_combo), hide_index=True)

    st.info(
        "Aucune règle de sortie, aucun stop, aucun take-profit, aucun position "
        "sizing n'a été appliqué ici. Ceci mesure uniquement la valeur prédictive "
        "brute du signal d'entrée sur des horizons fixes."
    )

    with st.expander("🔒 Identification de l'expérience"):
        st.code(
            f"EXP-001 / V1.0\n"
            f"SMI(10,3,3,EMA) · Signal = EMA(10) du SMI\n"
            f"Hebdo = franchissement du zéro à la hausse\n"
            f"Quotidien = croisement haussier + sortie de -40 (k={K} séances)\n"
            f"Combiné = Quotidien ET SMI hebdo>0 (dernière semaine complètement close)\n"
            f"Ticker = {ticker} · Historique = {years} ans\n"
            f"Aucune règle de sortie · Aucune optimisation post-résultats"
        )

    # ============================================================
    # PHASE 2 — Exports bruts pour l'analyse statistique complète
    # ============================================================
    st.markdown("---")
    st.markdown("### 📤 Exports Phase 2")

    log_C = build_event_log(daily["close"], ev_C_daily_mask, ticker, "Weekly C")
    log_D = build_event_log(daily["close"], ev_D_daily, ticker, "Daily D")
    log_combo = build_event_log(daily["close"], ev_combo, ticker, "Combined")
    full_log = pd.concat([log_C, log_D, log_combo], ignore_index=True)

    st.download_button(
        "⬇️ Télécharger le journal des signaux (CSV)",
        data=full_log.to_csv(index=False).encode("utf-8"),
        file_name=f"exp001_journal_{ticker.replace('.', '_')}.csv",
        mime="text/csv",
    )

    prices_out = daily[["close"]].reset_index()
    prices_out.columns = ["date", "close"]
    prices_out["date"] = prices_out["date"].dt.strftime("%Y-%m-%d")
    prices_out["ticker"] = ticker

    st.download_button(
        "⬇️ Télécharger la série de prix quotidiens (CSV)",
        data=prices_out.to_csv(index=False).encode("utf-8"),
        file_name=f"exp001_prix_{ticker.replace('.', '_')}.csv",
        mime="text/csv",
    )
