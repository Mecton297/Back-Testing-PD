import json
import math
import urllib.request
from datetime import datetime
import streamlit as st

st.set_page_config(
    page_title="Backtest 2 Chandelles",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# --- CSS ULTRA-COMPACT ET POLICES RÉDUITES ---
st.markdown(
    """
    <style>
        .block-container { padding-top: 0.5rem !important; padding-bottom: 1rem !important; padding-left: 0.3rem !important; padding-right: 0.3rem !important; }
        h1 { font-size: 1.3rem !important; margin-bottom: 0.2rem !important; }
        h2, h3 { font-size: 1.0rem !important; margin-top: 0.3rem !important; margin-bottom: 0.2rem !important; }
        .stNumberInput, .stTextInput, .stRadio { font-size: 0.8rem !important; }
        div[data-baseweb="input"] { min-height: 28px !important; }
        input { padding-top: 2px !important; padding-bottom: 2px !important; font-size: 0.85rem !important; }
        .streamlit-expanderHeader { padding-top: 0.2rem !important; padding-bottom: 0.2rem !important; font-size: 0.85rem !important; }
        div[data-testid="stExpanderDetails"] { padding: 0.3rem !important; }
        hr { margin: 0.4rem 0 !important; }
    </style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600)
def obtenir_donnees_historiques(symbole, annee_debut, annee_fin):
    try:
        t_debut = int(datetime(annee_debut, 1, 1).timestamp())
        t_fin = int(datetime(annee_fin + 1, 1, 5).timestamp())

        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + symbole + "?period1=" + str(t_debut) + "&period2=" + str(t_fin) + "&interval=1d"
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
        "capital_final": capital,
        "rendement_robot_pct": rendement_robot_pct,
        "rendement_bh_pct": rendement_bh_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "max_drawdown_dollar": max_drawdown_dollar,
    }


# --- TITRE & REGLAGES COMPACTS ---
st.title("📈 Backtest 2 Chandelles")

c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    capital_total = st.number_input("Capital ($)", value=10000, step=500)
with c2:
    annee_debut = st.number_input("Début", min_value=2000, max_value=2026, value=2020)
with c3:
    annee_fin = st.number_input("Fin", min_value=2001, max_value=2026, value=2025)

c_mode, c_ind = st.columns([2, 1])
with c_mode:
    mode_capital = st.radio("Mode :", ["100% / FNB", "Répartition %"], horizontal=True)
with c_ind:
    symbole_indice = st.text_input("Indice", value="^NDX")

perf_ndx_str = "N/A"
if symbole_indice:
    donnees_ndx = obtenir_donnees_historiques(symbole_indice, int(annee_debut), int(annee_fin))
    if donnees_ndx and len(donnees_ndx) > 2:
        perf_ndx = ((donnees_ndx[-1]["close"] - donnees_ndx[0]["close"]) / donnees_ndx[0]["close"]) * 100.0
        perf_ndx_str = str(round(perf_ndx, 1)) + " %"

st.caption("🎯 **" + symbole_indice + " (Buy&Hold)** : " + perf_ndx_str)

st.markdown("---")

# --- CONFIGURATION COMPACTE DES FNB (DANS DES SECTIONS REPLIÉES PAR DÉFAUT) ---
fnbs_defaut = ["XEG.TO", "ZMT.TO", "XST.TO", "ZEB.TO", "", ""]
resultats_tableau = []

capital_accumule_robot = 0.0
capital_accumule_initial = 0.0
rendements_robot_liste = []
rendements_bh_liste = []

with st.expander("⚙️ Configuration des 6 FNB (Cliquer pour ouvrir/fermer)", expanded=False):
    for idx in range(6):
        titre_defaut = fnbs_defaut[idx]
        col_s, col_ma, col_si, col_ms = st.columns([2, 1, 1, 1])
        
        with col_s:
            sym = st.text_input("FNB #" + str(idx+1), value=titre_defaut, key="sym_" + str(idx)).upper()
        with col_ma:
            ma = st.number_input("Ach%", value=0.05, step=0.01, key="ma_" + str(idx))
        with col_si:
            si = st.number_input("StInit%", value=3.0, step=0.5, key="si_" + str(idx))
        with col_ms:
            ms = st.number_input("StSuiv%", value=0.05, step=0.01, key="ms_" + str(idx))

# --- CALCUL ET AFFICHAGE CÔTÉ À CÔTÉ (TABLEAU) ---
st.subheader("📊 Résultats Comparatifs")

for idx in range(6):
    sym = st.session_state.get("sym_" + str(idx), fnbs_defaut[idx]).upper()
    if not sym:
        continue
    
    ma = st.session_state.get("ma_" + str(idx), 0.05)
    si = st.session_state.get("si_" + str(idx), 3.0)
    ms = st.session_state.get("ms_" + str(idx), 0.05)

    cap_fnb = capital_total if "100%" in mode_capital else (capital_total / 4.0)
    bougies = obtenir_donnees_historiques(sym, int(annee_debut), int(annee_fin))

    if bougies and len(bougies) >= 5:
        res = executer_backtest(bougies, cap_fnb, ma, si, ms)
        if res:
            resultats_tableau.append({
                "FNB": sym,
                "Robot %": str(round(res['rendement_robot_pct'], 1)) + "%",
                "B&H %": str(round(res['rendement_bh_pct'], 1)) + "%",
                "Max DD": "-" + str(round(res['max_drawdown_pct'], 1)) + "%",
                "Cap. Final": str(int(res['capital_final'])) + " $"
            })
            capital_accumule_robot += res["capital_final"]
            capital_accumule_initial += cap_fnb
            rendements_robot_liste.append(res["rendement_robot_pct"])
            rendements_bh_liste.append(res["rendement_bh_pct"])

if resultats_tableau:
    # Tableau synthétique où les résultats sont affichés côte à côte
    st.dataframe(resultats_tableau, use_container_width=True, hide_index=True)

    st.markdown("---")
    # Bilan Global compact
    if "Répartition" in mode_capital:
        profit_total = capital_accumule_robot - capital_accumule_initial
        perf_globale_pct = (profit_total / capital_accumule_initial) * 100.0
        st.caption("🏁 **Cap. Final Global :** " + str(int(capital_accumule_robot)) + " $ | **Rendement :** " + str(round(perf_globale_pct, 2)) + " %")
    else:
        moy_robot = sum(rendements_robot_liste) / len(rendements_robot_liste)
        moy_bh = sum(rendements_bh_liste) / len(rendements_bh_liste)
        st.caption("🏁 **Moy. Robot :** " + str(round(moy_robot, 1)) + "% | **Moy. Buy&Hold :** " + str(round(moy_bh, 1)) + "%")
else:
    st.info("Aucune donnée disponible.")
