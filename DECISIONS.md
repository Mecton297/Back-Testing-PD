# QUANT LAB — DECISIONS

## D-001
Date : 2026-09-25
Expérience : EXP-014

Décision :
Aucune interpolation ou imputation des données FX.

Règle :
Toute fenêtre de calcul traversant un trou >5 jours
calendaires est invalidée (aucun signal généré sur cette zone).

Statut :
🟢 DÉCISION ACTIVE

---

## D-002
Date : 2026-09-25
Expérience : Laboratoire (règle générale)

Décision :
Un résultat fourni par une IA sans preuve d'exécution
réelle (capture d'écran ou copier-coller direct de l'app
Streamlit) est classé 🔴 NON VÉRIFIÉ et ne peut pas être
archivé comme résultat expérimental.

Statut :
🟢 DÉCISION ACTIVE

---

## D-003
Date : 2026-09-25
Expérience : Laboratoire (règle générale)

Décision :
Python/Streamlit constitue la source de vérité pour
les résultats expérimentaux. Aucune IA ne déclare un test
réussi ou échoué sans confirmation par l'exécution réelle.

Statut :
🟢 DÉCISION ACTIVE

---

## D-004
Date : 2026-09-25
Expérience : Laboratoire (règle générale)

Décision :
Aucune IA ne modifie silencieusement LAB_STATE.md. Toute
modification est proposée sous forme de « PATCH PROPOSÉ »
dans la section dédiée du fichier, et appliquée au corps
du document uniquement par Patrick ou par consensus explicite
des trois IA.

Statut :
🟢 DÉCISION ACTIVE

---

## D-005
Date : 2026-09-25
Expérience : EXP-014

Décision :
014a (breakout/expansion) et 014b (mean-reversion) sont
pré-enregistrées simultanément dès le départ, soumises au
même protocole statistique, en long-only. Aucun choix entre
les deux après observation des résultats.

Statut :
🟢 DÉCISION ACTIVE (paramètres numériques encore à définir)
