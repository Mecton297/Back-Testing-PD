import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="EXP-011 / V1.0", layout="centered")
st.title("🧪 EXP-011 / V1.0 — Breadth S&P 500 (sans biais de survivance)")
st.caption("% de titres au-dessus de leur MM50, composition réelle de l'indice à chaque date — mécanisme de stress collectif")

TICKER_ASSET = "SPY"
START = "2006-01-01"
END = "2026-01-01"
MA_WINDOW = 50
SEUILS = [20, 33]  # pré-enregistrés : EXP-011 (20%) et EXP-011b (33%)

CONSTITUENTS_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/"
    "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"
)

if "exp011_data" not in st.session_state:
    st.session_state.exp011_data = None

st.write(f"**Source de composition** : fja05680/sp500 (MIT, historique réel depuis 1996)")
st.write(f"**Fenêtre MM** : {MA_WINDOW} séances")
st.write(f"**Période** : {START} → {END}")
st.write(f"**Seuils pré-enregistrés** : {SEUILS[0]}% (EXP-011) et {SEUILS[1]}% (EXP-011b)")
st.warning("⚠️ Cette étape peut prendre plusieurs minutes (des centaines de titres à télécharger). Ne ferme pas l'app pendant l'exécution.")

def load_constituents():
    df = pd.read_csv(CONSTITUENTS_URL)
    # La premiere colonne est generalement 'date', la seconde 'tickers' (liste separee par virgules)
    date_col = df.columns[0]
    tickers_col = df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).reset_index(drop=True)
    df["ticker_set"] = df[tickers_col].apply(
        lambda s: set(t.strip().replace(".", "-") for t in str(s).split(",") if t.strip())
    )
    return df[[date_col, "ticker_set"]].rename(columns={date_col: "date"})


def composition_on(date, changes_df):
    """Renvoie l'ensemble de tickers en vigueur a la date donnee (dernier changement <= date)."""
    valid = changes_df[changes_df["date"] <= date]
    if valid.empty:
        return changes_df.iloc[0]["ticker_set"]
    return valid.iloc[-1]["ticker_set"]


if st.button("Lancer EXP-011 / V1.0 (télécharge tout, ~plusieurs minutes)"):
    status = st.empty()
    status.write("Chargement de la composition historique du S&P 500...")
    try:
        changes_df = load_constituents()
    except Exception as e:
        st.error(f"Échec du chargement de la composition : {e}")
        st.stop()

    st.write(f"{len(changes_df)} dates de changement chargées, "
             f"{changes_df['date'].min().date()} → {changes_df['date'].max().date()}")

    # Univers complet = union de tous les tickers ayant figure dans l'indice
    # pendant la fenetre d'etude (avec une marge de MA_WINDOW jours avant START)
    window_changes = changes_df[changes_df["date"] <= END]
    full_universe = set()
    for s in window_changes["ticker_set"]:
        full_universe |= s
    full_universe = sorted(full_universe)
    st.write(f"Univers total à télécharger : **{len(full_universe)} titres**")

    status.write("Téléchargement des prix (par lots de 100)...")
    progress = st.progress(0.0)
    all_closes = {}
    batch_size = 100
    n_batches = (len(full_universe) + batch_size - 1) // batch_size
    for b in range(n_batches):
        batch = full_universe[b*batch_size:(b+1)*batch_size]
        try:
            data = yf.download(batch, start=START, end=END, auto_adjust=False,
                                progress=False, group_by="ticker", threads=True)
        except Exception:
            data = None
        if data is not None and not data.empty:
            for tk in batch:
                try:
                    if len(batch) == 1:
                        col = data["Close"]
                    else:
                        col = data[tk]["Close"]
                    col = col.dropna()
                    if col.index.tz is not None:
                        col.index = col.index.tz_localize(None)
                    if len(col) > MA_WINDOW:
                        all_closes[tk] = col
                except Exception:
                    continue
        progress.progress((b + 1) / n_batches)

    status.write(f"✅ {len(all_closes)} / {len(full_universe)} titres téléchargés avec succès.")

    # Calendrier de reference = celui de SPY
    spy_raw = yf.Ticker(TICKER_ASSET).history(start=START, end=END, auto_adjust=False)
    spy_raw.columns = [c.lower() for c in spy_raw.columns]
    spy_raw.index = spy_raw.index.tz_localize(None)
    spy_close = spy_raw["close"]
    calendar = spy_close.index

    status.write("Calcul du breadth (% au-dessus de MM50, composition réelle par date) — version vectorisée...")

    # Matrice des clotures alignee sur le calendrier SPY
    close_df = pd.DataFrame(all_closes).reindex(calendar)
    ma_df = close_df.rolling(MA_WINDOW).mean()
    above_df = close_df > ma_df  # NaN gere naturellement (False si comparaison avec NaN)
    valid_df = ma_df.notna() & close_df.notna()

    # Matrice de composition (True si le titre est membre a cette date), construite
    # aux dates de changement puis reportee (ffill) sur le calendrier SPY - aucune
    # semaine future n'est utilisee, uniquement le dernier changement connu <= date.
    tickers = list(close_df.columns)
    comp_at_changes = pd.DataFrame(
        [{tk: (tk in row["ticker_set"]) for tk in tickers} for _, row in changes_df.iterrows()],
        index=changes_df["date"]
    )
    comp_daily = comp_at_changes.reindex(comp_at_changes.index.union(calendar)).sort_index()
    comp_daily = comp_daily.ffill().reindex(calendar).fillna(False).astype(bool)

    member_valid = comp_daily & valid_df
    total_per_day = member_valid.sum(axis=1)
    above_per_day = (member_valid & above_df).sum(axis=1)
    breadth = (above_per_day / total_per_day * 100).replace([np.inf, -np.inf], np.nan).dropna()

    status.write(f"✅ Terminé. Breadth calculé sur {len(breadth)} séances.")

    out = pd.DataFrame({"date": breadth.index.strftime("%Y-%m-%d"),
                         "breadth_pct": breadth.values})
    spy_out = spy_close.reset_index()
    spy_out.columns = ["date", "close"]
    spy_out["date"] = spy_out["date"].dt.strftime("%Y-%m-%d")

    st.session_state.exp011_data = {"breadth": out, "spy": spy_out, "n_titres": len(all_closes)}

if st.session_state.exp011_data is not None:
    d = st.session_state.exp011_data
    st.success(f"Breadth calculé à partir de {d['n_titres']} titres historiques réels.")
    st.line_chart(d["breadth"].set_index("date")["breadth_pct"])

    st.download_button(
        "⬇️ Télécharger la série de breadth (CSV)",
        data=d["breadth"].to_csv(index=False).encode("utf-8"),
        file_name="exp011_breadth.csv", mime="text/csv", key="dl_breadth",
    )
    st.download_button(
        "⬇️ Télécharger les prix SPY (CSV)",
        data=d["spy"].to_csv(index=False).encode("utf-8"),
        file_name="exp011_prix_SPY.csv", mime="text/csv", key="dl_spy",
    )

    st.markdown("### 📋 Alternative : copier-coller le texte brut")
    with st.expander("Voir le breadth (CSV en texte)"):
        st.text_area("Breadth", d["breadth"].to_csv(index=False), height=300, key="txt_breadth")
    with st.expander("Voir les prix SPY (CSV en texte)"):
        st.text_area("Prix SPY", d["spy"].to_csv(index=False), height=300, key="txt_spy")

    with st.expander("🔒 Identification de l'expérience"):
        st.code(
            f"EXP-011 / V1.0 — Breadth S&P 500 (composition historique réelle)\n"
            f"Source composition = fja05680/sp500 (MIT)\n"
            f"MA = {MA_WINDOW} séances · Période = {START} à {END}\n"
            f"Seuils pré-enregistrés (à appliquer sur breadth_pct, hors app) : {SEUILS}\n"
            f"Signal = franchissement à la baisse (Breadth_(t-1) > seuil ET Breadth_t <= seuil)\n"
            f"Aucune règle de sortie · Aucune optimisation post-résultats"
        )
