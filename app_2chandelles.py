import json
import math
import urllib.request
from datetime import datetime
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Backtest 2 Chandelles",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# --- CSS MOBILE MAXI-COMPACT ---
st.markdown(
    """
    <style>
        .block-container { padding: 0.2rem 0.2rem 0.5rem 0.2rem !important; }
        h1, h2, h3 { font-size: 0.9rem !important; margin: 0 !important; padding: 0 !important; }
        .stNumberInput, .stTextInput, .stRadio { font-size: 0.75rem !important; }
        div[data-baseweb="input"] { min-height: 24px !important; }
        input { padding: 1px 2px !important; font-size: 0.8rem !important; }
        .streamlit-expanderHeader { padding: 0.1rem !important; font-size: 0.8rem !important; }
        div[data-testid="stExpanderDetails"] { padding: 0.2rem !important; }
        hr { margin: 0.2rem 0 !important; }
        
        /* Garde les colonnes alignées côte à côte sur téléphone */
        [data-testid="column"] {
            min-width: 0px !important;
            flex: 1 1 0% !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600)
def obtenir_donnees_historiques(symbole, annee_debut, annee_fin):
    try:
        t_debut = int(datetime(annee_debut, 1, 1).timestamp())
        t_fin = int(datetime(annee_fin + 1, 1, 5).timestamp())

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbole}?period1={t_debut}&period2={t_fin}&interval=1d"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        res = payload["chart"]["result"][0]
        timestamps = res["timestamp"]
        quotes = res["indicators"]["quote"][0]

        bougies = []
        for i in range(len(timestamps)):
            h, l, c = quotes["high"][i], quotes["low"][i], quotes["close"][i]
            if h is not None and l is not None and c is not None:
                bougies.append(
                    {
                        "date": datetime.fromtimestamp(timestamps[i]).strftime("%Y-%m-%d"),
                        "high": float(h),
                        "low": float(l),
                        "close": float(c),
                    }
                )
        return bougies
    except Exception:
        return []


def executer_backtest(bougies, capital_initial, marge_achat_pct, stop_initial_pct, marge_stop_pct):
    if len(bougies) < 3:
        return None

    capital = capital_initial
    metrique_max_capital = capital_initial
    max_drawdown_dollar = 0.0
    max_drawdown_pct = 0.0

    en_position = False
    prix_entree = 0.0
    nb_actions = 0
    prix_stop = 0.0

    marge_achat = marge_achat_pct / 100.0
    stop_init_max = stop_initial_pct / 100.0
    marge_stop = marge_stop_pct / 100.0

    prix_depart = bougies[0]["close"]
    prix_fin = bougies[-1]["close"]
    rendement_bh_pct = ((prix_fin - prix_depart) / prix_depart) * 100.0

    for i in range(2, len(bougies)):
        bougie_actuelle = bougies[i]
        b1, b2 = bougies[i - 1], bougies[i - 2]
        h_actuel, l_actuel = bougie_actuelle["high"], bougie_actuelle["low"]

        if not en_position:
            sommet_2_bougies = max(b1["high"], b2["high"])
            prix_declenchement = sommet_2_bougies * (1.0 + marge_achat)

            if h_actuel >= prix_declenchement:
                en_position = True
                prix_entree = prix_declenchement
                nb_actions = math.floor(capital / prix_entree)

                if nb_actions <= 0:
                    en_position = False
                    continue

                stop_securite_capital = prix_entree * (1.0 - stop_init_max)
                bas_2_bougies = min(b1["low"], b2["low"])
                stop_technique = bas_2_bougies * (1.0 - marge_stop)
                prix_stop = max(stop_securite_capital, stop_technique)

        else:
            if l_actuel <= prix_stop:
                en_position = False
                capital = nb_actions * prix_stop
                nb_actions = 0
            else:
                bas_2_bougies = min(b1["low"], b2["low"])
                nouveau_stop = bas_2_bougies * (1.0 - marge_stop)
                if nouveau_stop > prix_stop:
                    prix_stop = nouveau_stop

        valeur_courante = capital if not en_position else (nb_actions * bougie_actuelle["close"])
        if valeur_courante > metrique_max_capital:
            metrique_max_capital = valeur_courante

        drawdown_actuel_dollar = metrique_max_capital - valeur_courante
        drawdown_actuel_pct = (drawdown_actuel_dollar / metrique_max_capital) * 100.0 if metrique_max_capital > 0 else 0.0

        if drawdown_actuel_dollar > max_drawdown_dollar:
            max_drawdown_dollar = drawdown_actuel_dollar
            max_drawdown_pct = drawdown_actuel_pct

    if en_position:
        capital = nb_actions * bougies[-1]["close"]

    rendement_robot_pct = ((capital - capital_initial) / capital_initial) * 100.0

    return {
        "capital_initial": capital_initial,
        "capital_final": capital,
        "gain_dollar": capital - capital_initial,
        "rendement_robot_pct": rendement_robot_pct,
        "rendement_bh_pct": rendement_bh_pct,
        "max_drawdown_pct": max_drawdown_pct,
    }


# --- INTERFACE ET SÉLECTION DES PARAMÈTRES ---
st.title("📈 Backtest 2 Chandelles")

col1, col2, col3 = st.columns([1.2, 1, 1])
with col1:
    capital_total = st.number_input("Capital ($)", value=10000, step=500)
with col2:
    annee_debut = st.number_input("Début", min_value=2000, max_value=2026, value=2020)
with col3:
    annee_fin = st.number_input("Fin", min_value=2001, max_value=2026, value=2025)

col_m, col_i = st.columns([1.5, 1])
with col_m:
    mode_capital = st.radio("Mode :", ["100% / FNB", "Répartition %"], horizontal=True)
with col_i:
    symbole_indice = st.text_input("Indice", value="^NDX")

perf_ndx_str = "N/A"
if symbole_indice:
    donnees_ndx = obtenir_donnees_historiques(symbole_indice, int(annee_debut), int(annee_fin))
    if donnees_ndx and len(donnees_ndx) > 2:
        perf_ndx = ((donnees_ndx[-1]["close"] - donnees_ndx[0]["close"]) / donnees_ndx[0]["close"]) * 100.0
        perf_ndx_str = f"{int(round(perf_ndx))}%"

st.caption(f"🎯 **{symbole_indice} (Buy&Hold)** : {perf_ndx_str}")

# --- RÉGLAGES DES FNB MASQUÉS ---
fnbs_defaut = ["XEG.TO", "ZMT.TO", "XST.TO", "ZEB.TO", "", ""]

with st.expander("⚙️ Modifier FNB / Réglages", expanded=False):
    for idx in range(6):
        c_s, c_ma, c_si, c_ms = st.columns([1.5, 1, 1, 1])
        with c_s:
            st.text_input(f"FNB #{idx+1}", value=fnbs_defaut[idx], key=f"sym_{idx}")
        with c_ma:
            st.number_input("Ach%", value=0.05, step=0.01, key=f"ma_{idx}")
        with c_si:
            st.number_input("StInit%", value=3.0, step=0.5, key=f"si_{idx}")
        with c_ms:
            st.number_input("StSuiv%", value=0.05, step=0.01, key=f"ms_{idx}")

# --- CALCUL DES RÉSULTATS ---
fnbs_actifs = []
for idx in range(6):
    sym = st.session_state.get(f"sym_{idx}", fnbs_defaut[idx]).upper().strip()
    if sym:
        fnbs_actifs.append((idx, sym))

nb_fnb = len(fnbs_actifs)

donnees_fnb = {}
capital_accumule_robot = 0.0
capital_accumule_initial = 0.0
rendements_robot_liste = []
rendements_bh_liste = []

for idx, sym in fnbs_actifs:
    ma = st.session_state.get(f"ma_{idx}", 0.05)
    si = st.session_state.get(f"si_{idx}", 3.0)
    ms = st.session_state.get(f"ms_{idx}", 0.05)

    # Détermination du capital alloué par FNB selon le mode choisi
    cap_fnb = capital_total if "100%" in mode_capital else (capital_total / float(max(1, nb_fnb)))
    bougies = obtenir_donnees_historiques(sym, int(annee_debut), int(annee_fin))

    if bougies and len(bougies) >= 5:
        res = executer_backtest(bougies, cap_fnb, ma, si, ms)
        if res:
            donnees_fnb[sym] = [
                f"{int(round(res['rendement_robot_pct']))}%",
                f"{int(round(res['rendement_bh_pct']))}%",
                f"{int(round(res['gain_dollar']))} $",
                f"-{int(round(res['max_drawdown_pct']))}%",
            ]

            capital_accumule_robot += res["capital_final"]
            capital_accumule_initial += cap_fnb
            rendements_robot_liste.append(res["rendement_robot_pct"])
            rendements_bh_liste.append(res["rendement_bh_pct"])

st.markdown("---")
st.subheader("📊 Résultats")

if donnees_fnb:
    # Construction explicite pour empêcher le décalage de la colonne 'Métrique'
    colonnes_m = ["Métrique"] + list(donnees_fnb.keys())
    lignes_m = [
        ["% Test"] + [donnees_fnb[k][0] for k in donnees_fnb],
        ["% Hold"] + [donnees_fnb[k][1] for k in donnees_fnb],
        ["Gain $"] + [donnees_fnb[k][2] for k in donnees_fnb],
        ["DD %"] + [donnees_fnb[k][3] for k in donnees_fnb],
    ]

    df_final = pd.DataFrame(lignes_m, columns=colonnes_m)
    st.dataframe(df_final, use_container_width=True, hide_index=True)

    # Récapitulatif
    if "Répartition" in mode_capital:
        profit_total = capital_accumule_robot - capital_accumule_initial
        perf_globale_pct = (profit_total / capital_accumule_initial) * 100.0 if capital_accumule_initial > 0 else 0.0
        st.caption(f"🏁 **Capital Final Total :** {int(round(capital_accumule_robot))} $ | **Profit Total :** {int(round(profit_total))} $ ({int(round(perf_globale_pct))}%)")
    else:
        moy_robot = sum(rendements_robot_liste) / len(rendements_robot_liste) if rendements_robot_liste else 0.0
        moy_bh = sum(rendements_bh_liste) / len(rendements_bh_liste) if rendements_bh_liste else 0.0
        st.caption(f"🏁 **Moyenne Robot :** {int(round(moy_robot))}% | **Moyenne Buy&Hold :** {int(round(moy_bh))}%")
else:
    st.info("Aucune donnée FNB disponible.")
