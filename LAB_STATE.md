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
