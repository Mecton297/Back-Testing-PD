# BILAN POST-MORTEM — CYCLE 2 (EXP-014)

**Statut : 🟢 APPROUVÉ PAR CONSENSUS GPT/GEMINI/CLAUDE — prêt pour archivage**
**Rédigé par Claude, corrigé par GPT, enrichi par Gemini**

---

## 1. Ce qui a été testé

Deux mécanismes FX pré-enregistrés, sur 6 paires (EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD), 2006-05-16 à 2026-09-25 :
- **014a** : Breakout Donchian(20) + expansion ATR(14) ≥ 1,20
- **014b** : Mean-reversion Z-score(20) ≥ ±2,0

Résultat : 0 cellule sur 48 validée. **Les deux mécanismes n'ont fourni aucune preuve statistiquement validée selon le protocole verrouillé, dans l'univers et la période testés.**

## 2. Ce qui a bien fonctionné (à garder pour EXP-015)

- La gouvernance à 3 IA + validation humaine a attrapé toutes les erreurs avant qu'elles comptent : la faute de frappe de date de GPT, mon bouton de téléchargement manquant, une formulation trop absolue corrigée à deux reprises par GPT.
- Le refus explicite d'ajouter un critère a posteriori (« 3 paires sur 6 » retiré parce qu'il n'était pas dans le charter verrouillé) a protégé l'intégrité du test. **C'est la preuve que la charte écrite prime sur toute intuition ou tentative d'assouplissement rétrospectif** (Gemini).
- L'approche étape par étape avec artefact vérifiable à chaque étape (signal → rendements → baseline → permutation → Bonferroni+blocs) a permis de repérer des problèmes tôt.
- Le format CSV unique téléchargeable a résolu le problème pratique de départ (25 captures d'écran) — à réutiliser systématiquement.

## 3. Ce qui a coûté du temps ou aurait pu être évité

- La date de fin n'a pas été gelée dès le charter V1.0 — corrigée en cours de route plutôt que d'être une case obligatoire dès le départ.
- Le premier script de signal (014a) n'avait pas de téléchargement unique, un problème pourtant déjà résolu une fois sur un script antérieur puis oublié sur un nouveau.
- Aucun bug de calcul majeur détecté — mais le système de gouvernance n'a donc pas encore été mis à l'épreuve par une vraie erreur statistique silencieuse, seulement des erreurs de procédure/présentation.

## 4. Ce que le rejet de 014a et 014b nous apprend

- Aucune des deux familles classiques de signaux techniques testées (tendance et retour à la moyenne) ne survit à un test rigoureux sur cet univers FX précis, cette période, ces paramètres.
- Certaines combinaisons paire/hypothèse ont montré les excès descriptifs les plus marqués, notamment USDCHF et USDJPY, mais aucune n'a satisfait les critères de validation. **Ceci reste une observation descriptive, PAS une piste à exploiter directement** — la retester spécifiquement sur ces deux paires serait un p-hacking a posteriori.
- Cohérent avec les résultats du Cycle 1, où aucune hypothèse n'avait été validée selon les critères retenus. Ces résultats montrent que le protocole permet effectivement de rejeter des hypothèses qui ne satisfont pas ses critères préétablis. Ils ne suffisent toutefois pas à démontrer l'absence de biais systématique du laboratoire.

## 5. Checklist de démarrage — à imposer dès EXP-015 (adoptée par consensus)

Tout futur script du laboratoire doit intégrer, de manière native et non négociable :

- [ ] Date de coupure verrouillée AVANT tout téléchargement (jamais « jusqu'à aujourd'hui »)
- [ ] Données téléchargées une seule fois et archivées (version exacte du dataset traçable)
- [ ] Graine aléatoire fixe pour toute permutation ou tirage aléatoire
- [ ] Paramètres du charter verrouillés, rappelés en commentaire dans le code
- [ ] Formule exacte des signaux documentée dans le script
- [ ] Formule exacte des rendements documentée dans le script
- [ ] Traitement des trous de calendrier (D-001) appliqué et vérifiable
- [ ] Nombre de cellules de la famille statistique explicite dès le charter
- [ ] Export CSV unique et organisé (jamais plusieurs fichiers à télécharger séparément)
- [ ] Artefact vérifiable à chaque étape du pipeline
- [ ] Aucune modification de paramètre après observation de résultats

## 6. Questions ouvertes pour la discussion avant EXP-015

1. Le labo veut-il continuer à tester des familles de signaux classiques (momentum, volatilité), ou explorer une direction structurellement différente (données alternatives, cross-asset, filtres macro/inter-marchés) ?
2. Faut-il revoir la taille de l'univers (6 paires FX) ou la période, ou est-ce jugé suffisant ?
3. La checklist de la section 5 doit être formalisée comme gabarit standard (template) pour tout futur charter — accord de principe déjà obtenu, reste à l'intégrer formellement au processus.

*Aucune de ces questions n'est tranchée ici. La pause reste importante : on ne choisit pas la prochaine hypothèse à partir des quelques résultats descriptifs qui ont semblé intéressants dans EXP-014.*
