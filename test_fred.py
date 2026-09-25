import streamlit as st
import pandas as pd

st.set_page_config(page_title="Test faisabilité FRED", layout="centered")
st.title("🔍 Test de faisabilité — FRED BAMLH0A0HYM2")
st.caption("Objectif unique : déterminer la plage historique réellement accessible. Aucun calcul, aucun backtest.")

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2"

if st.button("Tester le téléchargement FRED"):
    st.write(f"**URL testée** : `{FRED_URL}`")
    try:
        df = pd.read_csv(FRED_URL)
        st.success("✅ Téléchargement réussi.")

        st.write(f"**Colonnes** : {list(df.columns)}")
        date_col = df.columns[0]
        val_col = df.columns[1]

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        st.write(f"**Nombre de lignes** : {len(df)}")
        st.write(f"**Première date** : {df[date_col].min()}")
        st.write(f"**Dernière date** : {df[date_col].max()}")
        st.write(f"**Nombre de dates uniques** : {df[date_col].nunique()}")

        n_nan_val = df[val_col].apply(lambda x: str(x).strip() in [".", "nan", "NaN", ""]).sum()
        st.write(f"**Nombre de valeurs manquantes/NaN (colonne valeur)** : {n_nan_val}")
        st.write(f"**Nombre de NaN (dates non parsables)** : {df[date_col].isna().sum()}")

        st.markdown("### Premières observations")
        st.dataframe(df.head(10))

        st.markdown("### Dernières observations")
        st.dataframe(df.tail(10))

        span_years = (df[date_col].max() - df[date_col].min()).days / 365.25
        st.write(f"**Étendue couverte** : environ {span_years:.1f} années")

        if span_years > 15:
            st.success("→ Couverture large (>15 ans) : compatible avec la fenêtre 2006-2026.")
        elif span_years > 2:
            st.warning(f"→ Couverture restreinte (~{span_years:.1f} ans) : probablement tronquée, incompatible avec 2006-2026 complet.")
        else:
            st.error("→ Couverture très courte : accès manifestement restreint.")

    except Exception as e:
        st.error(f"❌ Échec du téléchargement : {e}")
