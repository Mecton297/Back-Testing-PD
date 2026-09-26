"""
audit_holes_fx.py
Audit ciblé des trous de calendrier sur l'univers FX du Labo Quant (EXP-014).

Objectif : lister les dates manquantes réelles dans les deux zones suspectes
(août 2008 sur EURUSD/USDJPY, ~22 avril 2025 sur plusieurs paires),
SANS interpolation ni reconstruction. On liste ce qui manque, point final.

Corrige le bug KeyError précédent : après reset_index(), la colonne de dates
s'appelle "Date" (nom de l'index yfinance), pas "index".
"""

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import io

st.set_page_config(page_title="Audit trous FX - EXP-014", layout="wide")
st.title("🔍 Audit des trous de calendrier — EXP-014 (FX)")

UNIVERSE = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X"]
START_DATE = "2006-05-16"

# Zones suspectes à examiner en détail (bornes larges pour capturer le contexte)
ZONES = {
    "Août 2008": ("2008-07-25", "2008-09-05"),
    "Avril 2025": ("2025-04-10", "2025-04-30"),
}

HOLE_THRESHOLD_DAYS = 5  # Règle D-001 : trou calendaire > 5 jours = zone invalide


@st.cache_data(show_spinner=False)
def load_data(ticker: str, start: str) -> pd.DataFrame:
    """Télécharge les données et corrige le nom de colonne après reset_index()."""
    df = yf.download(ticker, start=start, progress=False)
    if df.empty:
        return df
    df = df.reset_index()
    # FIX: l'index yfinance s'appelle "Date", pas "index" — c'est ce qui
    # causait le KeyError dans la version précédente.
    if "Date" not in df.columns:
        # Filet de sécurité si yfinance change un jour le nom de l'index
        df = df.rename(columns={df.columns[0]: "Date"})
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def find_calendar_gaps(dates: pd.Series, min_gap_days: int) -> pd.DataFrame:
    """
    Retourne chaque trou calendaire (écart entre deux jours de trading
    consécutifs) supérieur ou égal à min_gap_days, avec les vraies dates
    manquantes listées (calendaire, pas ouvré — pour rester factuel,
    sans supposer quels jours auraient dû être ouvrés).
    """
    dates_sorted = dates.sort_values().reset_index(drop=True)
    gaps = []
    for i in range(1, len(dates_sorted)):
        prev_date = dates_sorted[i - 1]
        curr_date = dates_sorted[i]
        gap_days = (curr_date - prev_date).days
        if gap_days > min_gap_days:
            missing_dates = pd.date_range(
                start=prev_date + pd.Timedelta(days=1),
                end=curr_date - pd.Timedelta(days=1),
                freq="D",
            )
            gaps.append({
                "date_avant_trou": prev_date,
                "date_apres_trou": curr_date,
                "duree_calendaire_jours": gap_days,
                "nb_dates_manquantes": len(missing_dates),
                "premiere_date_manquante": missing_dates[0] if len(missing_dates) else None,
                "derniere_date_manquante": missing_dates[-1] if len(missing_dates) else None,
            })
    return pd.DataFrame(gaps)


def main():
    st.markdown(
        "Ce script **ne fait aucune interpolation ni reconstruction**. "
        "Il liste uniquement les trous calendaires réels détectés dans les données "
        "brutes de yfinance, pour chaque paire de l'univers EXP-014."
    )

    with st.spinner("Téléchargement des données..."):
        data = {ticker: load_data(ticker, START_DATE) for ticker in UNIVERSE}

    failed = [t for t, df in data.items() if df.empty]
    if failed:
        st.error(f"⚠️ Échec de téléchargement pour : {', '.join(failed)}")

    # ---- 1. RÉSUMÉ COMPACT (ce qui doit tenir sur un seul écran) ----
    st.header("📊 Résumé (tout tient ici, pas besoin de scroller)")

    summary_rows = []
    all_gaps_by_ticker = {}

    for ticker, df in data.items():
        if df.empty:
            continue
        gaps = find_calendar_gaps(df["Date"], HOLE_THRESHOLD_DAYS)
        all_gaps_by_ticker[ticker] = gaps
        summary_rows.append({
            "Paire": ticker,
            "Première date": df["Date"].min().date(),
            "Dernière date": df["Date"].max().date(),
            "Nb jours de données": len(df),
            f"Trous > {HOLE_THRESHOLD_DAYS}j calendaires": len(gaps),
        })

    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, use_container_width=True)

    # ---- 2. ZOOM SUR LES DEUX ZONES SUSPECTES ----
    st.header("🎯 Zoom sur les deux zones suspectes")

    zone_report_rows = []
    for zone_name, (zone_start, zone_end) in ZONES.items():
        st.subheader(zone_name)
        zone_start_dt = pd.Timestamp(zone_start)
        zone_end_dt = pd.Timestamp(zone_end)

        found_anything = False
        for ticker, gaps in all_gaps_by_ticker.items():
            if gaps.empty:
                continue
            in_zone = gaps[
                (gaps["date_avant_trou"] >= zone_start_dt - pd.Timedelta(days=10))
                & (gaps["date_apres_trou"] <= zone_end_dt + pd.Timedelta(days=10))
            ]
            if not in_zone.empty:
                found_anything = True
                for _, row in in_zone.iterrows():
                    st.write(
                        f"**{ticker}** : trou de {row['duree_calendaire_jours']} jours "
                        f"calendaires entre {row['date_avant_trou'].date()} et "
                        f"{row['date_apres_trou'].date()} "
                        f"({row['nb_dates_manquantes']} dates manquantes)"
                    )
                    zone_report_rows.append({
                        "zone": zone_name,
                        "paire": ticker,
                        **row.to_dict(),
                    })
        if not found_anything:
            st.write("Aucun trou > seuil détecté dans cette zone pour cet univers.")

    # ---- 3. TABLEAU COMPLET DE TOUS LES TROUS (toutes paires) ----
    st.header("📋 Détail complet de tous les trous détectés (toutes paires)")

    full_gaps_rows = []
    for ticker, gaps in all_gaps_by_ticker.items():
        if gaps.empty:
            continue
        g = gaps.copy()
        g.insert(0, "paire", ticker)
        full_gaps_rows.append(g)

    if full_gaps_rows:
        full_gaps_df = pd.concat(full_gaps_rows, ignore_index=True)
        st.dataframe(full_gaps_df, use_container_width=True)
    else:
        full_gaps_df = pd.DataFrame()
        st.write("Aucun trou détecté sur l'ensemble de l'univers.")

    # ---- 4. EXPORT CSV — pour éviter les captures d'écran multiples ----
    st.header("⬇️ Télécharger le rapport complet")
    st.markdown(
        "**Un seul clic, un seul fichier.** Télécharge ce CSV et envoie-le "
        "directement dans la conversation — plus besoin de captures d'écran."
    )

    buffer = io.StringIO()
    buffer.write("=== RÉSUMÉ PAR PAIRE ===\n")
    summary_df.to_csv(buffer, index=False)
    buffer.write("\n=== TROUS DANS LES ZONES SUSPECTES ===\n")
    pd.DataFrame(zone_report_rows).to_csv(buffer, index=False)
    buffer.write("\n=== TOUS LES TROUS DÉTECTÉS ===\n")
    full_gaps_df.to_csv(buffer, index=False)

    st.download_button(
        label="📥 Télécharger audit_trous_fx.csv",
        data=buffer.getvalue(),
        file_name=f"audit_trous_fx_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )

    st.caption(
        f"Généré le {datetime.now().strftime('%Y-%m-%d %H:%M')} — "
        f"Seuil de trou appliqué : {HOLE_THRESHOLD_DAYS} jours calendaires (règle D-001)."
    )


if __name__ == "__main__":
    main()
