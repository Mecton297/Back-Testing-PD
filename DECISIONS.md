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


## D-006 — EXP-014a (Breakout FX) formellement rejetée

**Date : 2026-09-26**
**Contexte : EXP-014, Cycle 2, mécanisme 014a**

**Décision :** EXP-014a (breakout / expansion de volatilité, Donchian(20) + ATR(14), seuil 1,20) est classée 🔴 FALSIFIÉE et archivée. Elle ne sera pas retestée avec d'autres paramètres sous le nom "014a" — toute nouvelle tentative sur une hypothèse de breakout FX nécessiterait un nouveau numéro d'expérience et un nouveau charter pré-enregistré.

**Preuve :** 0/24 cellules (6 paires × 4 horizons) ne passent le seuil Bonferroni pré-enregistré (α=0,0010417) simultanément dans les deux blocs temporels indépendants (2006-2015 et 2016-2026). Date de coupure gelée : 2026-09-25.

**Irréversible sauf nouvelle version documentée du charter EXP-014 (V1.1) avec justification écrite.**

## D-007 — Clôture formelle d'EXP-014 (FX, Breakout & Mean-Reversion)

**Date : 2026-09-27**
**Contexte : fin du Cycle 2 du laboratoire**

**Décision :** EXP-014 est officiellement clôturée. Les deux mécanismes pré-enregistrés (014a breakout, 014b mean-reversion) sont classés 🔴 FALSIFIÉS selon le protocole verrouillé (charter V1.0). Aucune des 48 cellules de la famille statistique (2 mécanismes × 6 paires × 4 horizons) ne passe le seuil Bonferroni (α=0,0010417) de façon synchrone dans les deux blocs temporels indépendants.

**Formulation scientifique retenue (à utiliser dans toute référence future à EXP-014) :**

> EXP-014 n'a fourni aucune preuve statistiquement validée d'un effet robuste pour les deux mécanismes testés, dans l'univers, la période et le protocole définis.

**Irréversible.** EXP-014 ne sera pas rouverte avec les mêmes paramètres. Toute nouvelle exploration d'idées de breakout ou de mean-reversion en FX nécessiterait une nouvelle expérience numérotée avec un charter pré-enregistré distinct.

**Décision annexe :** avant de démarrer EXP-015, le laboratoire observe une pause volontaire pour un bilan post-mortem du Cycle 2. Aucun code ni aucune nouvelle hypothèse tant que ce bilan n'est pas complété et documenté.

