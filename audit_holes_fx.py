import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-014 — Audit des trous FX", layout="centered")
st.title("🔍 Audit des trous — Août 2008 & Avril 2025")
st.caption("Aucune interpolation, aucun rendement nul, aucune reconstruction. Objectif unique : lister précisément les dates manquantes.")

PAIRS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X"]
START = "2005-01-01"
END = "2026-01-01"

ZONES = {
    "Zone 1 — Août 2008": ("2008-08-01", "2008-09-05"),
    "Zone 2 — Avril 2025": ("2025-04-10", "2025-04-30"),
}

if st.button("Lancer l'audit des trous"):
    raw_data = {}
    status = st.empty()
    for pair in PAIRS:
        status.write(f"Téléchargement {pair}...")
        df = yf.Ticker(pair).history(start=START, end=END, auto_adjust=False)
        df.columns = [c.lower() for c in df.columns]
        df.index = df.index.tz_localize(None)
        if not df.empty:
            raw_data[pair] = df
    status.write("✅ Téléchargements terminés.")

    for zone_label, (z_start, z_end) in ZONES.items():
        st.header(zone_label)
        expected_bdays = pd.bdate_range(start=z_start, end=z_end)  # freq='B', detecteur initial imparfait (voir note)
        st.caption(f"Calendrier lundi-vendredi attendu (freq='B', ne tient pas compte des jours fériés réels) : "
                    f"{len(expected_bdays)} jours entre {z_start} et {z_end}.")

        for pair, df in raw_data.items():
            actual_dates = set(df.index[(df.index >= z_start) & (df.index <= z_end)])
            expected_set = set(expected_bdays)
            missing = sorted(expected_set - actual_dates)

            with st.expander(f"{pair} — {len(missing)} date(s) 'manquantes' (jours ouvrés Lun-Ven sans observation)"):
                if missing:
                    st.dataframe(pd.DataFrame({"Date manquante (jour ouvré attendu)":
                                                [d.strftime("%Y-%m-%d (%A)") for d in missing]}), hide_index=True)
                else:
                    st.write("Aucune date manquante dans cette zone pour cette paire.")

                # Derniere observation avant la zone, et premiere observation apres
                before = df.index[df.index < z_start]
                after = df.index[df.index > z_end]
                last_before = before.max() if len(before) else None
                first_after = after.min() if len(after) else None

                st.write(f"**Dernière observation avant la zone** : "
                         f"{last_before.strftime('%Y-%m-%d') if last_before is not None else 'N/A'}"
                         f"{' (close=' + str(round(df.loc[last_before, 'close'], 5)) + ')' if last_before is not None else ''}")
                st.write(f"**Première observation après la zone** : "
                         f"{first_after.strftime('%Y-%m-%d') if first_after is not None else 'N/A'}"
                         f"{' (close=' + str(round(df.loc[first_after, 'close'], 5)) + ')' if first_after is not None else ''}")

                # Toutes les observations reellement presentes dans la zone (pas juste les bornes)
                zone_obs = df.loc[(df.index >= z_start) & (df.index <= z_end), ["close"]]
                if len(zone_obs) > 0:
                    st.write(f"**{len(zone_obs)} observation(s) réellement présente(s) dans la zone :**")
                    st.dataframe(zone_obs.reset_index().rename(columns={"index": "date"}).assign(
                        date=lambda d: d["date"].dt.strftime("%Y-%m-%d (%A)")), hide_index=True)

    with st.expander("🔒 Rappel du périmètre"):
        st.code(
            "Audit de faisabilité EXP-014 — deux zones ciblées uniquement.\n"
            "Aucune interpolation, aucun rendement nul inséré, aucune reconstruction de prix.\n"
            "freq='B' est un détecteur initial imparfait (calendrier Lun-Ven brut, sans jours fériés réels) —\n"
            "chaque date listée doit être jugée au cas par cas, pas traitée automatiquement comme anomalie."
        )
