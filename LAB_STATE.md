# QUANT LAB — LAB STATE

Dernière mise à jour : 2026-09-25
Version du protocole : 1.0

---

## 🟢 RÈGLES DU LABORATOIRE

- Python/Streamlit = juge de paix expérimental.
- Un résultat non exécuté n'est jamais un résultat.
- Aucun résultat rapporté par une IA n'est considéré comme confirmé sans preuve d'exécution.
- Une expérience verrouillée n'est jamais modifiée après observation des résultats.
- Toute modification devient une nouvelle version.
- Aucune optimisation post-hoc.
- Git = historique permanent.

### Statuts

🟢 EXÉCUTÉ / CONFIRMÉ
🟡 PROPOSÉ / À TESTER
🔴 NON VÉRIFIÉ / À NE PAS UTILISER

---

## 📝 DERNIÈRES PROPOSITIONS / PATCHES EN ATTENTE

*(Chaque IA ajoute ici ses propositions de modification, horodatées et signées. Rien ici n'est actif tant que ce n'est pas intégré dans le corps du document ci-dessous par Patrick ou par consensus explicite des trois IA.)*

- Aucun patch en attente pour le moment.

---

# EXPÉRIENCE ACTIVE

## EXP-014 — FX

### Statut
🟡 Phase 0 — validation technique en attente

### Univers
- EURUSD=X
- GBPUSD=X
- USDJPY=X
- USDCHF=X
- AUDUSD=X
- USDCAD=X

### Fenêtre commune
16 mai 2006 → dernière date commune effectivement disponible (à confirmer par exécution réelle, pas encore verrouillée).

### Phase 0 — État des lieux
- Diagnostic de faisabilité général (`diagnostic_fx.py`) : 🟢 EXÉCUTÉ (résultats reçus par capture d'écran).
- Audit ciblé des trous août 2008 / avril 2025 (`audit_holes_fx.py`) : 🔴 EN ATTENTE — aucune preuve d'exécution réelle reçue à ce jour. Un texte présenté comme sortie de ce script a été soumis mais rejeté (format incompatible avec une sortie Streamlit réelle).
- Règle de traitement des trous (déjà actée, voir D-001) : aucune interpolation, aucun remplissage par zéro. Fenêtre de calcul traversant un trou >5 jours calendaires = invalide, pas de signal généré sur cette zone.
- Les fermetures normales du marché FX (week-ends, jours fériés bancaires standards) sont conservées comme calendrier normal, pas des anomalies.

### 014a — 🟡 PROPOSÉ (non scellé)
Breakout / expansion de volatilité (Donchian + filtre ATR).

Paramètres à définir avant verrouillage :
- N (canal Donchian) : à définir
- Fenêtre de volatilité/ATR : à définir
- Seuil d'expansion : à définir
- Entrée : Close ou Open suivant, à définir
- Long-only (recommandé par GPT, à confirmer)

### 014b — 🟡 PROPOSÉ (non scellé)
Mean-reversion sur étirement extrême (Z-score).

Paramètres à définir avant verrouillage :
- SMA N : à définir
- Fenêtre de volatilité pour le Z-score : à définir
- Seuil K : à définir
- Entrée : à définir
- Long-only (recommandé par GPT, à confirmer)

### Pipeline statistique (hérité du Cycle 1, à confirmer pour EXP-014)
- Baseline inconditionnelle par paire
- Déduplication par clusters temporels
- Permutation circulaire, décalage synchronisé sur les 6 paires (corrélation inter-devises préservée)
- Correction Bonferroni au niveau global de l'expérience
- Réplication temporelle : Bloc A (2006-2015) / Bloc B (2016-2026), significativité indépendante exigée dans les deux blocs

### Résultats
Aucun résultat confirmé à ce jour.

### Prochaine action
1. Obtenir la preuve d'exécution réelle de `audit_holes_fx.py` (capture d'écran ou copier-coller direct de l'app).
2. Sur cette base, statuer sur la clôture de la Phase 0.
3. Verrouiller tous les paramètres numériques de 014a et 014b avant tout codage du pipeline complet.

---

## ARCHIVE — CYCLE 1 (EXP-001 à EXP-013)

Statut : CLÔTURÉ. 0 stratégie validée. Voir `rapport_maitre_exp001-013.md` pour le détail complet.

Familles couvertes : oscillateurs, breakout, momentum, retour à la moyenne, volatilité VIX, structure par terme, breadth de marché, volume climax, stress de crédit.

Résultat le plus proche de la validation : EXP-013 (crédit, 24/24 directions positives), rejeté faute de réplication indépendante dans les deux blocs temporels.

## 📝 PATCH PROPOSÉ — clarification chronologie EXP-014 (2026-09-26)

*(à intégrer dans le corps de LAB_STATE.md par Patrick)*

### EXP-014 — Charter V1.0

**Statut : 🟢 VERROUILLÉ le 2026-09-26**, validé par Patrick, consensus GPT + Gemini + Claude.
Document : `CHARTER_EXP-014_v1.0_FINAL.md` sur GitHub (branche main).

**Chronologie exacte (pour éviter toute confusion pour une future IA/session) :**
1. Charter rédigé avec tous les paramètres du consensus (48 tests, Bonferroni α=0,0010417, Open T+1, Long & Short, horizons 1/5/10/20j)
2. Validation humaine reçue : « Je valide »
3. Fichier marqué 🟢 VERROUILLÉ, poussé sur GitHub
4. **SEULEMENT ENSUITE** : code du signal 014a (isolé, sans rendement ni stats)
5. Signaux 014a exécutés et vérifiés (🟢, voir résumé ci-dessous) — **archivés comme artefacts, ne pas supprimer**

**Aucun calcul de résultat n'a précédé le verrouillage.** Toute IA qui rejoint le projet doit vérifier cette chronologie directement sur GitHub (historique des commits) avant de soulever un doute de procédure.

### Protocole d'embarquement pour nouvelle IA (adopté ce jour, proposition GPT)

Avant de coder quoi que ce soit, toute IA qui rejoint une session doit :
1. Lire `LAB_STATE.md`
2. Lire `DECISIONS.md`
3. Lire le charter de l'expérience active
4. Lire le dernier rapport d'exécution
5. Répondre explicitement : *« Voici ce que je considère comme verrouillé, ce qui est en attente, et ce qui est interdit. »*

Aucun code avant cette confirmation.

### Résumé signal 014a (🟢 exécuté, 2026-09-26)

| Paire | Signaux Long | Signaux Short | Jours invalides (trous) |
|---|---|---|---|
| EURUSD=X | 26 | 23 | 35 |
| GBPUSD=X | 14 | 30 | 34 |
| USDJPY=X | 44 | 55 | 35 |
| USDCHF=X | 18 | 31 | 0 |
| AUDUSD=X | 18 | 35 | 0 |
| USDCAD=X | 37 | 15 | 0 |

Note méthodologique : ces comptages sont strictement descriptifs (contrôle de qualité des données). Ils ne constituent pas une validation de la pertinence du seuil ni de l'efficacité du signal.

### Prochaine étape

Calcul des rendements bruts aux 4 horizons (+1/+5/+10/+20j), entrée Open T+1, avec exclusion des trades dont la fenêtre de détention chevauche un trou > 5 jours calendaires. Toujours 🔴 interdit : tests statistiques (Bonferroni, permutation, blocs temporels) tant que cette étape n'est pas terminée et vérifiée.

## 📝 PATCH PROPOSÉ — Verdict final EXP-014a (2026-09-26)

*(à intégrer dans le corps de LAB_STATE.md par Patrick)*

### EXP-014a — Breakout / expansion de volatilité

**Statut : 🔴 FALSIFIÉE — archivée, ne pas rouvrir sans nouvelle version (V1.1) justifiée**

**Date de coupure gelée utilisée : 2026-09-25** (immuable pour toute réplication future de ce résultat)

**Résultat (24 cellules : 6 paires × 4 horizons) :**
- 0/24 passe le seuil Bonferroni pré-enregistré (α = 0,05/48 = 0,0010417)
- 0/24 passe simultanément Bloc A (2006-2015) ET Bloc B (2016-2026)
- Meilleure p-value individuelle observée : 0,010 (AUDUSD, 20j, Bloc B) — encore ~10× trop élevée pour le seuil requis

**Critères de validation (charter section 17), appliqués strictement :**
- [ ] Bonferroni global : ❌ échec (0/24)
- [ ] Réplication indépendante Bloc A ET Bloc B : ❌ échec (0/24)
- [x] Règle D-001 (trous de calendrier) respectée tout au long du calcul : ✅
- N/A : le charter ne prévoit AUCUN seuil du type "significatif sur N paires sur 6" (section 16, décision explicite) — ce critère n'existe pas et ne doit pas être ajouté rétroactivement à la grille de validation.

**Conclusion : 014a ne devient PAS une stratégie validée. Elle est classée « hypothèse testée et rejetée », conformément à la philosophie du laboratoire (le labo doit pouvoir dire NON).**

**Aucune modification de paramètre n'a eu lieu après observation des résultats.**

### Prochaine étape

Basculer sur EXP-014b (mean-reversion / étirement extrême Z-score), en suivant exactement le même pipeline étape par étape (signal isolé → rendements → baseline/excess → permutation → Bonferroni + blocs A/B), avec la même date de coupure gelée (2026-09-25).

