"""
Assistant de trading Disnat — Application Streamlit (3 onglets complets)
==========================================================================
Outil d'aide au calcul. Ne place AUCUN ordre — tu copies les valeurs
affichées et tu les entres toi-même dans Disnat.

Hébergement : Streamlit Community Cloud (voir LISEZMOI.md pour les étapes).
"""

import json
import math
import os
from datetime import date, timedelta

import streamlit as st
import yfinance as yf

# ---------------------------------------------------------------------
# Persistance locale (capital, position, liste de surveillance)
# ---------------------------------------------------------------------
DATA_FILE = "donnees_locales.json"

def charger_donnees():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "watchlist": ["XGD.TO", "GDX", "GLXY.TO"],
        "actif_selectionne": "XGD.TO",
        "en_encaisse": 20000.0,
        "position": {
            "en_position": False,
            "quantite": 0,
            "prix_entree": 0.0,
            "stop_actuel": 0.0,
        },
    }

def sauvegarder_donnees(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

if "donnees" not in st.session_state:
    st.session_state.donnees = charger_donnees()
donnees = st.session_state.donnees

# ---------------------------------------------------------------------
# Config de page — format mobile épuré
# ---------------------------------------------------------------------
st.set_page_config(page_title="Disnat Assistant", page_icon="📈", layout="centered")
st.markdown("""
<style>
    .stApp { max-width: 480px; margin: 0 auto; }
    div.stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)
st.title("📈 Disnat Assistant")

# ---------------------------------------------------------------------
# Fonctions communes — données de marché
# ---------------------------------------------------------------------
@st.cache_data(ttl=3600)
def obtenir_chandelles(symbole, jours=10):
    """Dernières chandelles quotidiennes closes pour un symbole."""
    df = yf.Ticker(symbole).history(period=f"{jours}d")
    return df.tail(jours)

def deux_dernieres_chandelles(df):
    """Retourne (avant-dernière, dernière) chandelle CLOSE."""
    if len(df) < 2:
        return None, None
    return df.iloc[-2], df.iloc[-1]

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

    if not donnees["watchlist"]:
        st.info("Ta liste est vide. Ajoute un symbole ci-dessus.")
    for symbole in donnees["watchlist"]:
        actif = symbole == donnees["actif_selectionne"]
        c1, c2, c3 = st.columns([3, 2, 1])
        c1.markdown(f"### {'✅' if actif else '▫️'} {symbole}")
        if not actif:
            if c2.button("Activer", key=f"act_{symbole}"):
                donnees["actif_selectionne"] = symbole
                sauvegarder_donnees(donnees)
                st.rerun()
        else:
            c2.caption("Actif partout")
        if c3.button("🗑️", key=f"del_{symbole}"):
            donnees["watchlist"].remove(symbole)
            if donnees["actif_selectionne"] == symbole:
                donnees["actif_selectionne"] = donnees["watchlist"][0] if donnees["watchlist"] else None
            sauvegarder_donnees(donnees)
            st.rerun()

    st.divider()
    st.caption(f"Actif sélectionné : **{donnees['actif_selectionne']}**")

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

        with st.spinner("Récupération des chandelles..."):
            try:
                df = obtenir_chandelles(symbole)
                avant, aujourdhui = deux_dernieres_chandelles(df)
            except Exception:
                avant = aujourdhui = None

        if avant is None:
            st.error("Impossible de récupérer les chandelles pour ce symbole.")
        else:
            st.caption(
                f"Basé sur {avant.name.date()} et {aujourdhui.name.date()} — "
                f"clôture : {aujourdhui['Close']:.2f} $"
            )

            if statut == "En encaisse":
                pos["en_position"] = False
                deux_haut = max(avant["High"], aujourdhui["High"])
                declencheur = round(deux_haut * 1.0005, 2)
                quantite = math.floor(donnees["en_encaisse"] / declencheur)

                st.markdown("#### 🟢 Achat Stop à placer ce soir")
                st.code(f"{declencheur}", language=None)
                st.markdown("#### Quantité")
                st.code(f"{quantite}", language=None)
                st.caption("Le bloc gris ci-dessus a une icône de copie au survol/tap.")

            else:  # Titres détenus
                deux_bas = min(avant["Low"], aujourdhui["Low"])
                stop_suiveur = round(deux_bas * 0.9995, 2)

                if not pos["en_position"]:
                    pos["en_position"] = True
                    if pos["prix_entree"] == 0.0:
                        pos["prix_entree"] = float(aujourdhui["Close"])
                    pos["stop_actuel"] = round(pos["prix_entree"] * 0.97, 2)

                pos["stop_actuel"] = max(pos["stop_actuel"], stop_suiveur)
                sauvegarder_donnees(donnees)

                st.markdown("#### 🔴 Ordre stop à ajuster ce soir")
                st.code(f"{pos['stop_actuel']}", language=None)
                st.caption(
                    f"Stop initial de sécurité (-3 %) : {round(pos['prix_entree']*0.97,2)} $ — "
                    "le stop ne descend jamais, seulement à la hausse."
                )

                if st.button("J'ai vendu / je suis sorti de la position"):
                    pos["en_position"] = False
                    pos["prix_entree"] = 0.0
                    pos["stop_actuel"] = 0.0
                    sauvegarder_donnees(donnees)
                    st.rerun()

# =======================================================================
# ONGLET 3 — HISTORIQUE & BACKTESTING
# =======================================================================
with onglet3:
    symbole = donnees["actif_selectionne"]
    st.subheader(f"Backtesting — {symbole or '—'}")

    if not symbole:
        st.info("Choisis d'abord un actif dans l'onglet Surveillance.")
    else:
        col_d, col_f = st.columns(2)
        debut = col_d.date_input("Date de début", value=date.today() - timedelta(days=365))
        fin = col_f.date_input("Date de fin", value=date.today())
        capital_test = st.number_input("Capital de départ ($)", value=20000.0, step=500.0)

        if st.button("Lancer le backtest"):
            with st.spinner("Téléchargement de l'historique..."):
                df = yf.Ticker(symbole).history(start=debut, end=fin)

            if len(df) < 5:
                st.error("Pas assez de données pour cette période.")
            else:
                cash, shares = capital_test, 0.0
                en_pos, prix_entree, stop = False, 0.0, 0.0
                rows = df.reset_index()

                for i in range(1, len(rows) - 1):
                    c0, c1, nxt = rows.iloc[i - 1], rows.iloc[i], rows.iloc[i + 1]
                    deux_haut = max(c0["High"], c1["High"])
                    deux_bas = min(c0["Low"], c1["Low"])

                    if not en_pos:
                        declencheur = deux_haut * 1.0005
                        if nxt["High"] >= declencheur:
                            prix_entree = max(nxt["Open"], declencheur)
                            shares = cash / prix_entree
                            cash = 0.0
                            en_pos = True
                            stop = prix_entree * 0.97
                    else:
                        stop = max(stop, deux_bas * 0.9995)
                        if nxt["Low"] <= stop:
                            prix_sortie = nxt["Open"] if nxt["Open"] < stop else stop
                            cash = shares * prix_sortie
                            shares = 0.0
                            en_pos = False

                valeur_finale = cash if not en_pos else shares * rows.iloc[-1]["Close"]
                rendement_strategie = (valeur_finale - capital_test) / capital_test * 100
                rendement_bah = (rows.iloc[-1]["Close"] - rows.iloc[0]["Close"]) / rows.iloc[0]["Close"] * 100

                c1, c2 = st.columns(2)
                c1.metric("Marché (Buy & Hold)", f"{rendement_bah:.1f} %")
                c2.metric("Stratégie", f"{rendement_strategie:.1f} %",
                          delta=f"{rendement_strategie - rendement_bah:.1f} pts vs marché")
