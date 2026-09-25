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

st.markdown(
    """
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 2rem; padding-left: 0.8rem; padding-right: 0.8rem; }
        div[data-testid="stMetricValue"] { font-size: 1.2rem !important; }
        .stButton>button { width: 100%; border-radius: 8px; }
        hr { margin: 1rem 0; }
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


st.title("📈 Backtest 2 Chandelles")
st.subheader("⚙️ Paramètres généraux")

capital_total = st.number_input("Capital Total Initial ($)", min_value=100, max_value=10000000, value=10000, step=500)

col_annee1, col_annee2 = st.columns(2)
with col_annee1:
    annee_debut = st.number_input("Début (Janv.)", min_value=2000, max_value=2026, value=2020)
with col_annee2:
    annee_fin = st.number_input("Fin (Janv.)", min_value=2001, max_value=2026, value=2025)

mode_capital = st.radio(
    "Mode d'allocation du capital :",
    options=["100 % sur chaque FNB (Comparaison)", "Répartition personnalisée (Portefeuille)"],
    index=0,
)

st.markdown("---")
st.subheader("🎯 Indice de Référence")
symbole_indice = st.text_input("Symbole Indice", value="^NDX")

perf_ndx_str = "N/A"
if symbole_indice:
    donnees_ndx = obtenir_donnees_historiques(symbole_indice, int(annee_debut), int(annee_fin))
    if donnees_ndx and len(donnees_ndx) > 2:
        perf_ndx = ((donnees_ndx[-1]["close"] - donnees_ndx[0]["close"]) / donnees_ndx[0]["close"]) * 100.0
        perf_ndx_str = str(round(perf_ndx, 1)) + " %"
        st.info(symbole_indice + " (Buy & Hold) : " + perf_ndx_str + " sur la période")

st.markdown("---")
st.subheader("📦 FNB à Analyser")

fnbs_defaut = ["XEG.TO", "ZMT.TO", "XST.TO", "ZEB.TO", "", ""]
capital_accumule_robot = 0.0
capital_accumule_initial = 0.0
rendements_robot_liste = []
rendements_bh_liste = []
details_export = []

for idx in range(6):
    is_custom = idx >= 4
    titre_defaut = fnbs_defaut[idx]
    label_section = "FNB Officiel #" + str(idx + 1) if not is_custom else "FNB Personnalisé #" + str(idx - 3)

    with st.expander("🏷️ " + label_section, expanded=True):
        symbole = st.text_input("Ticker Yahoo #" + str(idx + 1), value=titre_defaut, key="sym_" + str(idx)).upper()

        if not symbole:
            st.caption("Case vide - Ignorée.")
            continue

        inclure = True
        part_pct = 25.0
        if "Répartition" in mode_capital:
            col_inc, col_part = st.columns([1, 2])
            with col_inc:
                inclure = st.checkbox("Inclure", value=True, key="inc_" + str(idx))
            with col_part:
                part_pct = st.number_input("Part (%)", min_value=0.0, max_value=100.0, value=25.0, step=5.0, key="part_" + str(idx))

        if not inclure:
            st.caption("Exclu de la répartition.")
            continue

        cap_fnb = capital_total if "100 %" in mode_capital else (capital_total * (part_pct / 100.0))
        bougies = obtenir_donnees_historiques(symbole, int(annee_debut), int(annee_fin))

        if not bougies or len(bougies) < 5:
            st.error("Données introuvables pour " + symbole)
            continue

        ranges = [((b["high"] - b["low"]) / b["low"]) * 100.0 for b in bougies]
        volatilite_moy = sum(ranges) / len(ranges)
        st.caption("📊 Volatilité journalière moyenne : " + str(round(volatilite_moy, 2)) + " %")

        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            marge_achat = st.number_input("Achat (+%)", value=0.05, step=0.01, key="ma_" + str(idx))
        with col_p2:
            stop_init = st.number_input("Stop Init (-%)", value=3.0, step=0.5, key="si_" + str(idx))
        with col_p3:
            marge_stop = st.number_input("Stop Suiv (-%)", value=0.05, step=0.01, key="ms_" + str(idx))

        res = executer_backtest(bougies, cap_fnb, marge_achat, stop_init, marge_stop)

        if res:
            st.markdown("**📈 Résultats du Backtest :**")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.metric("Robot (%)", str(round(res['rendement_robot_pct'], 1)) + " %")
                st.metric("Pire chute", "-" + str(round(res['max_drawdown_pct'], 1)) + " %")
            with col_r2:
                st.metric("Buy & Hold (%)", str(round(res['rendement_bh_pct'], 1)) + " %")
                st.metric("Capital Final", str(int(res['capital_final'])) + " $")

            capital_accumule_robot += res["capital_final"]
            capital_accumule_initial += cap_fnb
            rendements_robot_liste.append(res["rendement_robot_pct"])
            rendements_bh_liste.append(res["rendement_bh_pct"])

            ligne = symbole + " -> Robot: " + str(round(res['rendement_robot_pct'], 1)) + "% | Buy&Hold: " + str(round(res['rendement_bh_pct'], 1)) + "% | MaxDD: -" + str(round(res['max_drawdown_pct'], 1)) + "%"
            details_export.append(ligne)

st.markdown("---")
st.subheader("🏁 Bilan Global du Portefeuille")

if capital_accumule_initial > 0:
    if "Répartition" in mode_capital:
        profit_total = capital_accumule_robot - capital_accumule_initial
        perf_globale_pct = (profit_total / capital_accumule_initial) * 100.0
        st.metric("Capital Final Combiné", str(int(capital_accumule_robot)) + " $")
        st.write("Rendement Global Portefeuille : " + str(round(perf_globale_pct, 2)) + " %")
    else:
        moy_robot = sum(rendements_robot_liste) / len(rendements_robot_liste)
        moy_bh = sum(rendements_bh_liste) / len(rendements_bh_liste)
        st.write("Rendement Moyen Robot : " + str(round(moy_robot, 2)) + " %")
        st.write("Rendement Moyen Buy & Hold : " + str(round(moy_bh, 2)) + " %")

    st.markdown("---")
    st.subheader("📋 Exporter les résultats")
    rapport_texte = "RAPPORT BACKTEST\n" + "\n".join(details_export)
    st.code(rapport_texte, language="text")
