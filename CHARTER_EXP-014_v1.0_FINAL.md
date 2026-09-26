# CHARTER EXP-014 — FX (V1.0)

**Statut : 🟢 VERROUILLÉ**
**Validé par Patrick le 2026-09-26.**
**Historique : rédigé par Claude, révisé par consensus GPT + Gemini + Claude, validation humaine finale reçue.**

Ce document est maintenant figé. Plus aucun paramètre ne peut être modifié sans créer une nouvelle version (V1.1), avec justification écrite du changement.

---

## 1. Univers

EURUSD=X, GBPUSD=X, USDJPY=X, USDCHF=X, AUDUSD=X, USDCAD=X

## 2. Période

Début commun : 2006-05-16
Fin : dernière date disponible au moment du verrouillage

## 3. Gestion des trous de calendrier

- D-001 inchangée : fenêtre traversant un trou > 5 jours calendaires = invalide sur cette zone, aucune interpolation.
- **Décidé** : seule la paire touchée par un trou est invalidée sur cette période. Les 5 autres paires restent utilisables ces jours-là.
- Zones connues et déjà auditées (🟢 exécuté) : EURUSD/USDJPY août 2008 (2 trous distincts), GBPUSD janvier 2008.

## 4. Fréquence

Quotidienne (close-to-close).

## 5. Mécanisme 014a — Breakout / expansion de volatilité

- Canal Donchian : N = 20
- ATR : fenêtre 14
- Seuil d'expansion : ATR(14) ≥ 1,20 × SMA20(ATR(14))
- Entrée : **Open du jour suivant le signal (T+1)**
- Direction : **Long & Short** (symétrique — pas de biais haussier structurel en FX)

## 6. Mécanisme 014b — Mean-reversion sur étirement extrême

- SMA : 20 jours
- Z-score : (Close − SMA20) / Écart-type 20 jours
- Seuil K : Z ≥ +2,0 (signal short) ou Z ≤ −2,0 (signal long)
- Entrée : **Open du jour suivant le signal (T+1)**
- Direction : **Long & Short** (symétrique)

## 7. Définition exacte du signal

Binaire : −1 (short) / 0 (rien) / +1 (long).

## 8. Sortie

Aucune sortie conditionnelle. Le rendement est mesuré à horizon fixe uniquement (voir point 10).

## 9. Traitement des signaux opposés (014a vs 014b)

Silos complètement indépendants. 014a et 014b sont deux hypothèses distinctes, jamais combinées ni compensées entre elles.

## 10. Horizons testés

Quatre horizons fixes, testés indépendamment : **+1, +5, +10, +20 jours**.
Justification : mesurer si l'effet est immédiat, persistant ou temporaire est une question scientifique en soi — les horizons ne sont pas retirés pour faciliter la correction statistique.

## 11. Baseline

Rendement moyen inconditionnel par paire, calculé sur tous les jours (pas seulement les jours de signal).

## 12. Déduplication

Un nouveau signal sur une même paire n'est conservé que s'il survient au moins 5 séances après le signal précédent, pour cette même paire. Les signaux des autres paires restent indépendants entre eux.

## 13. Permutation

Permutation circulaire, décalage synchronisé sur les 6 paires (préserve la corrélation inter-devises).

## 14. Famille statistique / Correction multiple

- Famille unique regroupant 014a et 014b.
- **Décompte des tests (M)** : 2 mécanismes × 6 paires × 4 horizons = **48 cellules**.
- **Correction Bonferroni globale** : α = 0,05 / 48 = **0,0010417**
- Les blocs temporels (voir point 15) sont des réplications indépendantes du même protocole — ils ne comptent pas comme des tests supplémentaires dans ce calcul, et aucun paramètre ne change entre les deux blocs.

## 15. Réplication temporelle

- Bloc A : 2006–2015
- Bloc B : 2016 → dernière date disponible
- Une cellule (mécanisme × paire × horizon) n'est considérée robuste que si elle passe le seuil corrigé indépendamment dans les deux blocs, avec direction d'effet cohérente.

## 16. Réplication transversale

Pas de seuil obligatoire du type « significatif sur N paires sur 6 » — jugé arbitraire avec seulement 6 paires disponibles.
**Décidé** : approche descriptive uniquement. Pour chaque mécanisme, on rapporte :
- nombre de paires avec effet positif / négatif
- médiane des excess returns
- dispersion entre paires
- nombre de paires individuellement significatives (à titre informatif, pas comme critère de rejet/validation)

## 17. Critères de validation finale

Une cellule (mécanisme × paire × horizon) est considérée **VALIDÉE** seulement si TOUTES les conditions suivantes sont remplies :

1. 🟢 Protocole V1.0 entièrement pré-enregistré avant tout résultat
2. 🟢 Aucun paramètre choisi ou modifié après observation de résultats
3. 🟢 Passe le seuil Bonferroni global (p < 0,0010417)
4. 🟢 Résultat reproduit indépendamment dans Bloc A ET Bloc B
5. 🟢 Direction de l'effet cohérente dans les deux blocs
6. 🟢 Aucune fenêtre invalide (trou de calendrier) utilisée dans le calcul
7. 🟢 Aucune explication post-hoc nécessaire pour justifier le résultat

Si un résultat est positif mais ne remplit pas toutes ces conditions, il reste classé **« signal intéressant / non validé »** — jamais promu au rang de stratégie validée.

---

## Historique du consensus

| Point en désaccord | Position GPT | Position Gemini | Décision finale |
|---|---|---|---|
| Entrée | Close T | Open T+1 | **Open T+1** (accord mutuel) |
| Direction | Long-only | Long & Short | **Long & Short** (accord mutuel) |
| Horizons | 4 (1,5,10,20) | 1 seul (5j), révisé ensuite | **4 horizons**, tranché par Claude, ratifié par GPT et Gemini |
| Seuil paires | Pas de seuil | 3 sur 6 | **Pas de seuil**, tranché par Claude, ratifié par GPT et Gemini |
| Famille statistique | 48 cellules | 2, puis 12, puis 48 | **48 cellules**, α = 0,0010417 — consensus unanime final |

---

## Statut

- Cycle 1 EXP-001 → EXP-013 : 🟢 FERMÉ
- EXP-014 Phase 0 (audit FX) : 🟢 CLÔTURÉE
- EXP-014 V1.0 (ce charter) : 🟢 VERROUILLÉ
- Codage / backtest : 🟢 AUTORISÉ à partir de maintenant

**Prochaine action : mettre ce fichier sur GitHub à la place du brouillon, puis commencer le code du pipeline EXP-014.**
