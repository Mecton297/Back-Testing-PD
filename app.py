"""
Assistant de trading Disnat — Application Streamlit
======================================================
3 onglets : Liste de surveillance / Suivi journalier / Historique & Backtesting

Deux méthodes disponibles dans l'onglet Historique :
  - "Méthode Claude et Mecton" : score pondéré sur 10 (voir POIDS ci-dessous)
  - "2 dernières chandelles" : méthode originale (Achat Stop / Ordre stop)

Outil d'aide au calcul seulement. Ne place AUCUN ordre — tu copies les
valeurs affichées et tu les entres toi-même dans Disnat.
"""

import json
import math
import os
from datetime import date

import pandas as pd
import streamlit as st
import yfinance as yf

# =======================================================================
# PARAMÈTRES DE LA MÉTHODE CLAUDE ET MECTON — modifie ces chiffres pour
# ajuster la méthode sans toucher au reste du code.
# =======================================================================
POIDS_5ANS = 4
POIDS_1AN = 3
POIDS_TENDANCE = 2
POIDS_VOLUME = 1
SEUIL_ENTREE = 7   # score minimum (sur 10) pour déclencher un achat
SEUIL_SORTIE = 5   # score minimum (sur 10) pour déclencher une vente

# Paramètres de la méthode "2 dernières chandelles" (cahier des charges Disnat)
ENTREE_BUFFER = 0.0005   # +0.05 % au-dessus du plus haut des 2 dernières chandelles
STOP_INITIAL = 0.03      # -3 % de stop de sécurité dès l'entrée
STOP_SUIVEUR_BUFFER = 0.0005  # -0.05 % sous le plus bas des 2 dernières chandelles

# ---------------------------------------------------------------------
# Persistance locale
# ---------------------------------------------------------------------
DATA_FILE = "donnees_locales.json"

def charger_donnees():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "watchlist": ["XGD.TO", "HURA.TO", "COPP.TO", "GLXY.TO", "CHPS.TO", "BANK.TO"],
        "actif_selectionne": "XGD.TO",
        "en_encaisse": 20000.0,
        "position": {"en_position": False, "quantite": 0, "prix_entree": 0.0, "stop_actuel": 0.0},
    }

def sauvegarder_donnees(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

if "donnees" not in st.session_state:
    st.session_state.donnees = charger_donnees()
donnees = st.session_state.donnees

st.set_page_config(page_title="Disnat Assistant", page_icon="📈", layout="centered")
st.markdown("""
<style>
    .stApp { max-width: 480px; margin: 0 auto; }
    div.stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)
st.title("📈 Disnat Assistant")

# =======================================================================
# INDICATEURS — calcul vectorisé (rapide, même sur 20 ans de données)
# =======================================================================

def calculer_smi(high, low, close, k=10, d=3, signal=10):
    """Stochastic Momentum Index façon Yahoo Finance (10,3,3,10,ema)."""
    hh = high.rolling(k).max()
    ll = low.rolling(k).min()
    centre = (hh + ll) / 2
    ecart = close - centre
    etendue = hh - ll
    ecart_lisse = ecart.ewm(span=d, adjust=False).mean().ewm(span=d, adjust=False).mean()
    etendue_lisse = etendue.ewm(span=d, adjust=False).mean().ewm(span=d, adjust=False).mean()
    smi = 100 * ecart_lisse / (etendue_lisse / 2)
    smi_signal = smi.ewm(span=signal, adjust=False).mean()
    return smi, smi_signal

def calculer_indicateurs(df_quotidien):
    """
    Retourne le df quotidien enrichi des colonnes de score, en combinant
    le contexte hebdomadaire (5 ans) et le quotidien (1 an).
    """
    df = df_quotidien.copy()

    # --- SMI quotidien (contexte "1 an") ---
    df["smi_1an"], _ = calculer_smi(df["High"], df["Low"], df["Close"])
    df["smi_1an_prev"] = df["smi_1an"].shift(1)
    df["smi_1an_min5"] = df["smi_1an"].rolling(5).min()
    df["smi_1an_max5"] = df["smi_1an"].rolling(5).max()
    df["crit_1an_entree"] = (df["smi_1an"] > df["smi_1an_prev"]) & (df["smi_1an_min5"] <= -40)
    df["crit_1an_sortie"] = (df["smi_1an"] < df["smi_1an_prev"]) & (df["smi_1an_max5"] >= 40)

    # --- Volume ---
    df["vol_moy20"] = df["Volume"].rolling(20).mean()
    df["crit_volume"] = df["Volume"] > df["vol_moy20"]

    # --- Contexte hebdomadaire (5 ans + tendance MM40) ---
    hebdo = df_quotidien.resample("W-FRI").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna()
    hebdo["smi_5ans"], _ = calculer_smi(hebdo["High"], hebdo["Low"], hebdo["Close"])
    hebdo["smi_5ans_prev"] = hebdo["smi_5ans"].shift(1)
    hebdo["smi_5ans_min5"] = hebdo["smi_5ans"].rolling(5).min()
    hebdo["smi_5ans_max5"] = hebdo["smi_5ans"].rolling(5).max()
    hebdo["crit_5ans_entree"] = (hebdo["smi_5ans"] > hebdo["smi_5ans_prev"]) & (hebdo["smi_5ans_min5"] <= -40)
    hebdo["crit_5ans_sortie"] = (hebdo["smi_5ans"] < hebdo["smi_5ans_prev"]) & (hebdo["smi_5ans_max5"] >= 40)

    hebdo["mm40"] = hebdo["Close"].rolling(40).mean()
    hebdo["mm40_4sem"] = hebdo["mm40"].shift(4)
    hebdo["crit_tendance_haussiere"] = (hebdo["Close"] > hebdo["mm40"]) & (hebdo["mm40"] > hebdo["mm40_4sem"])
    hebdo["crit_tendance_baissiere"] = (hebdo["Close"] < hebdo["mm40"]) & (hebdo["mm40"] < hebdo["mm40_4sem"])

    colonnes_hebdo = ["crit_5ans_entree", "crit_5ans_sortie", "crit_tendance_haussiere", "crit_tendance_baissiere"]
    hebdo_a_fusionner = hebdo[colonnes_hebdo].reset_index()
    hebdo_a_fusionner.columns = ["Date"] + colonnes_hebdo

    df_reset = df.reset_index().rename(columns={df.reset_index().columns[0]: "Date"})
    fusion = pd.merge_asof(
        df_reset.sort_values("Date"), hebdo_a_fusionner.sort_values("Date"),
        on="Date", direction="backward",
    )
    fusion = fusion.set_index("Date")

    fusion["score_entree"] = (
        POIDS_5ANS * fusion["crit_5ans_entree"].fillna(False)
        + POIDS_1AN * fusion["crit_1an_entree"].fillna(False)
        + POIDS_TENDANCE * fusion["crit_tendance_haussiere"].fillna(False)
        + POIDS_VOLUME * fusion["crit_volume"].fillna(False)
    )
    fusion["score_sortie"] = (
        POIDS_5ANS * fusion["crit_5ans_sortie"].fillna(False)
        + POIDS_1AN * fusion["crit_1an_sortie"].fillna(False)
        + POIDS_TENDANCE * fusion["crit_tendance_baissiere"].fillna(False)
        + POIDS_VOLUME * fusion["crit_volume"].fillna(False)
    )
    return fusion

@st.cache_data(ttl=3600)
def obtenir_indicateurs(symbole, period="5y"):
    df = yf.Ticker(symbole).history(period=period)
    if df.empty:
        return None
    return calculer_indicateurs(df)

def badge_couleur(score, seuil):
    if score >= seuil:
        return "🟢"
    elif score >= seuil - 3:
        return "🟡"
    else:
        return "🔴"

onglet1, onglet2, onglet3 = st.tabs(["📌 Surveillance", "⚡ Suivi journalier", "📊 Historique"])

# =======================================================================
# ONGLET 1 — LISTE DE SURVEILLANCE
# =======================================================================
with onglet1:
    st.subheader("Liste de surveillance")

    with st.expander("➕ Ajouter un symbole"):
        nouveau = st.text_input("Symbole (ex: XGD.TO, AAPL, GDX)").strip().upper()
        if st.button("Valider et ajouter"):
            if not nouveau:
                st.warning("Entre un symbole avant de valider.")
            elif nouveau in donnees["watchlist"]:
                st.warning(f"{nouveau} est déjà dans ta liste.")
            else:
                with st.spinner("Vérification..."):
                    try:
                        valide = not yf.Ticker(nouveau).history(period="5d").empty
                    except Exception:
                        valide = False
                if valide:
                    donnees["watchlist"].append(nouveau)
                    sauvegarder_donnees(donnees)
                    st.success(f"{nouveau} ajouté.")
                    st.rerun()
                else:
                    st.error(f"Impossible de trouver « {nouveau} ». Vérifie l'orthographe.")

    st.divider()
    st.caption("Score d'achat de la Méthode Claude et Mecton — trié du plus prometteur au moins prometteur.")

    # Calcul du score de chaque symbole, puis tri décroissant
    lignes = []
    for symbole in donnees["watchlist"]:
        ind = obtenir_indicateurs(symbole)
        if ind is None or ind.empty:
            lignes.append((symbole, None, None, None))
            continue
        derniere = ind.iloc[-1]
        lignes.append((symbole, derniere["Close"], int(derniere["score_entree"]), derniere))
    lignes.sort(key=lambda x: (x[2] is None, -(x[2] or 0)))

    for symbole, prix, score, derniere in lignes:
        actif = symbole == donnees["actif_selectionne"]
        if score is None:
            label = f"⚪ {symbole} — données indisponibles"
        else:
            emoji = badge_couleur(score, SEUIL_ENTREE)
            marque = " ✅" if actif else ""
            label = f"{emoji} {symbole}   {prix:.2f} $   Score {score}/10{marque}"

        with st.expander(label):
            if score is not None:
                c1, c2 = st.columns(2)
                if c1.button("Activer cet actif", key=f"act_{symbole}"):
                    donnees["actif_selectionne"] = symbole
                    sauvegarder_donnees(donnees)
                    st.rerun()
                if c2.button("🗑️ Retirer", key=f"del_{symbole}"):
                    donnees["watchlist"].remove(symbole)
                    if donnees["actif_selectionne"] == symbole:
                        donnees["actif_selectionne"] = donnees["watchlist"][0] if donnees["watchlist"] else None
                    sauvegarder_donnees(donnees)
                    st.rerun()

                st.markdown("**Détail du score d'entrée**")
                details = [
                    ("Stoch 5 ans (poids 4)", derniere["crit_5ans_entree"], POIDS_5ANS),
                    ("Stoch 1 an (poids 3)", derniere["crit_1an_entree"], POIDS_1AN),
                    ("Tendance MM40 (poids 2)", derniere["crit_tendance_haussiere"], POIDS_TENDANCE),
                    ("Volume (poids 1)", derniere["crit_volume"], POIDS_VOLUME),
                ]
                for nom, vrai, poids in details:
                    icone = "✅" if bool(vrai) else "❌"
                    pts = poids if bool(vrai) else 0
                    st.write(f"{icone} {nom} — +{pts}")
            else:
                st.write("Symbole invalide ou pas assez d'historique.")
                if st.button("🗑️ Retirer", key=f"del_{symbole}"):
                    donnees["watchlist"].remove(symbole)
                    sauvegarder_donnees(donnees)
                    st.rerun()

# =======================================================================
# ONGLET 2 — SUIVI JOURNALIER DISNAT
# =======================================================================
with onglet2:
    symbole = donnees["actif_selectionne"]
    st.subheader(f"Suivi journalier — {symbole or '—'}")

    if not symbole:
        st.info("Choisis d'abord un actif dans l'onglet Surveillance.")
    else:
        pos = donnees["position"]

        nouveau_capital = st.number_input(
            "En encaisse ($)", value=float(donnees["en_encaisse"]), step=100.0
        )
        if nouveau_capital != donnees["en_encaisse"]:
            donnees["en_encaisse"] = nouveau_capital
            sauvegarder_donnees(donnees)

        statut = st.radio(
            "Ton statut réel sur Disnat en ce moment",
            ["En encaisse", "Titres détenus"],
            index=1 if pos["en_position"] else 0,
            horizontal=True,
        )
        pos["en_position"] = statut == "Titres détenus"
        sauvegarder_donnees(donnees)

        with st.spinner("Calcul du score..."):
            ind = obtenir_indicateurs(symbole)

        if ind is None or ind.empty:
            st.error("Impossible de récupérer les données pour ce symbole.")
        else:
            derniere = ind.iloc[-1]
            st.caption(f"Basé sur la clôture du {ind.index[-1].date()} — {derniere['Close']:.2f} $")

            if statut == "En encaisse":
                score = int(derniere["score_entree"])
                seuil = SEUIL_ENTREE
                st.markdown(f"#### Score d'entrée : {score} / 10")
                if score >= seuil:
                    quantite = math.floor(donnees["en_encaisse"] / derniere["Close"])
                    st.success(f"Achat au marché suggéré — quantité : {quantite}")
                    st.code(f"{quantite}", language=None)
                elif score >= seuil - 3:
                    st.warning("Zone intermédiaire — pas assez fort pour acheter.")
                else:
                    st.error("Aucun signal d'achat aujourd'hui.")
            else:
                score = int(derniere["score_sortie"])
                seuil = SEUIL_SORTIE
                st.markdown(f"#### Score de sortie : {score} / 10")
                if score >= seuil:
                    st.error("Vente au marché suggérée.")
                elif score >= seuil - 2:
                    st.warning("Signal de sortie qui se renforce — reste attentif.")
                else:
                    st.success("Rien à faire — le signal de sortie n'est pas encore présent.")

            with st.expander("Voir le détail du score"):
                if statut == "En encaisse":
                    details = [
                        ("Stoch 5 ans", derniere["crit_5ans_entree"], POIDS_5ANS),
                        ("Stoch 1 an", derniere["crit_1an_entree"], POIDS_1AN),
                        ("Tendance MM40", derniere["crit_tendance_haussiere"], POIDS_TENDANCE),
                        ("Volume", derniere["crit_volume"], POIDS_VOLUME),
                    ]
                else:
                    details = [
                        ("Stoch 5 ans", derniere["crit_5ans_sortie"], POIDS_5ANS),
                        ("Stoch 1 an", derniere["crit_1an_sortie"], POIDS_1AN),
                        ("Tendance MM40 baissière", derniere["crit_tendance_baissiere"], POIDS_TENDANCE),
                        ("Volume", derniere["crit_volume"], POIDS_VOLUME),
                    ]
                for nom, vrai, poids in details:
                    icone = "✅" if bool(vrai) else "❌"
                    st.write(f"{icone} {nom} — +{poids if bool(vrai) else 0}")

# =======================================================================
# ONGLET 3 — HISTORIQUE & BACKTESTING
# =======================================================================
with onglet3:
    symbole = donnees["actif_selectionne"]
    st.subheader(f"Backtesting — {symbole or '—'}")

    if not symbole:
        st.info("Choisis d'abord un actif dans l'onglet Surveillance.")
    else:
        methode = st.radio(
            "Méthode",
            ["Méthode Claude et Mecton", "2 dernières chandelles"],
        )

        col_d, col_f = st.columns(2)
        annee_debut = col_d.number_input("Année de début", min_value=1990, max_value=2026, value=2007, step=1)
        annee_fin = col_f.number_input("Année de fin", min_value=1990, max_value=2026, value=2026, step=1)
        capital_test = st.number_input("Capital de départ ($)", value=20000.0, step=500.0)

        if st.button("Lancer le backtest"):
            debut = date(int(annee_debut), 1, 1)
            fin = date(int(annee_fin), 12, 31)

            with st.spinner("Téléchargement de l'historique..."):
                df = yf.Ticker(symbole).history(start=debut, end=fin)

            if len(df) < 60:
                st.error("Pas assez de données pour cette période (le titre n'existait peut-être pas encore).")
            else:
                cash, shares = capital_test, 0.0
                en_pos, stop = False, 0.0

                if methode == "Méthode Claude et Mecton":
                    ind = calculer_indicateurs(df)
                    rows = ind.reset_index()
                    for i in range(len(rows) - 1):
                        score_e = rows.loc[i, "score_entree"]
                        score_s = rows.loc[i, "score_sortie"]
                        prix_ouverture_suivant = rows.loc[i + 1, "Open"]
                        if not en_pos and score_e >= SEUIL_ENTREE:
                            shares = cash / prix_ouverture_suivant
                            cash = 0.0
                            en_pos = True
                        elif en_pos and score_s >= SEUIL_SORTIE:
                            cash = shares * prix_ouverture_suivant
                            shares = 0.0
                            en_pos = False
                    rows_pour_bah = rows
                else:
                    rows = df.reset_index()
                    for i in range(1, len(rows) - 1):
                        c0, c1, nxt = rows.iloc[i - 1], rows.iloc[i], rows.iloc[i + 1]
                        deux_haut = max(c0["High"], c1["High"])
                        deux_bas = min(c0["Low"], c1["Low"])
                        if not en_pos:
                            declencheur = deux_haut * (1 + ENTREE_BUFFER)
                            if nxt["High"] >= declencheur:
                                prix_entree = max(nxt["Open"], declencheur)
                                shares = cash / prix_entree
                                cash = 0.0
                                en_pos = True
                                stop = prix_entree * (1 - STOP_INITIAL)
                        else:
                            stop = max(stop, deux_bas * (1 - STOP_SUIVEUR_BUFFER))
                            if nxt["Low"] <= stop:
                                prix_sortie = nxt["Open"] if nxt["Open"] < stop else stop
                                cash = shares * prix_sortie
                                shares = 0.0
                                en_pos = False
                    rows_pour_bah = rows

                valeur_finale = cash if not en_pos else shares * rows_pour_bah.iloc[-1]["Close"]
                rendement_strategie = (valeur_finale - capital_test) / capital_test * 100
                rendement_bah = (
                    (rows_pour_bah.iloc[-1]["Close"] - rows_pour_bah.iloc[0]["Close"])
                    / rows_pour_bah.iloc[0]["Close"] * 100
                )

                c1, c2 = st.columns(2)
                c1.metric("Marché (Buy & Hold)", f"{rendement_bah:.1f} %")
                c2.metric("Stratégie", f"{rendement_strategie:.1f} %",
                          delta=f"{rendement_strategie - rendement_bah:.1f} pts vs marché")
                st.success(f"Capital final : {valeur_finale:,.0f} $".replace(",", " "))
