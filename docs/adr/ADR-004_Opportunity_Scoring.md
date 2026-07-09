# ADR-004 — Opportunity Engine : moteur pur et score non historisé

## Statut

Accepté (Module 06).

## Contexte

Atlas doit calculer un score d'opportunité par entreprise, entièrement
explicable, et amené à évoluer (nouvelles sources de signaux, passage
possible à du Machine Learning). Deux décisions structurantes devaient être
prises avant d'écrire le code : (1) où placer la logique de calcul, et
(2) comment persister le résultat.

## Décision

1. **Le calcul vit dans une classe pure (`OpportunityEngine`), sans aucune
   dépendance à SQLAlchemy, à la session DB ou à FastAPI.** Le
   `OpportunityScoreService` est seul responsable de traduire les modèles
   ORM en dataclasses simples (`EventSignal`, `ThemeSignal`, `CompanySignal`,
   `DiscoverySignal`) avant d'appeler le moteur.

2. **Une seule ligne `OpportunityScore` active par entreprise** (contrainte
   d'unicité sur `company_id`). Le recalcul écrase le score précédent plutôt
   que d'en créer un nouveau.

## Alternatives envisagées

- **Moteur de scoring intégré au service ou au repository** : rejeté, car
  cela aurait couplé la logique métier (qui devra probablement changer
  souvent, ou être remplacée par du ML) à l'infrastructure de données
  (qui, elle, ne devrait pas changer pour cette raison).
- **Historique complet des scores (une ligne par calcul)** : envisagé, mais
  écarté pour ce module. Il aurait fallu définir dès maintenant une stratégie
  de rétention et des index d'agrégation sans cas d'usage concret (aucun
  écran de "tendance du score dans le temps" n'est encore spécifié). Le détail
  des events reste, lui, entièrement historisé — un historique de scores
  pourra être reconstruit a posteriori en rejouant le moteur sur les events
  tels qu'ils étaient à une date donnée, donc rien n'est perdu par ce choix.
- **Market Signals calculé avec une valeur par défaut (ex: 50/100)** : rejeté.
  Un score par défaut aurait été indiscernable d'un vrai signal neutre. Le
  choix de `value: null` + `is_connected: false` rend l'absence de donnée
  explicite dans l'API plutôt que de la maquiller.

## Justification

- La séparation moteur pur / service ORM est le même principe déjà appliqué
  au Repository Pattern (Module 01) : chaque couche a une responsabilité
  unique, ce qui facilite les tests (22 vérifications unitaires passent sans
  aucune dépendance externe ni base de données) et rend le remplacement du
  mode de calcul par du ML un changement localisé à un seul fichier.
- Ne pas historiser les scores maintenant évite de la complexité vide, en
  cohérence avec la décision déjà prise au Module 01 de ne pas ajouter
  OpenSearch sans cas d'usage concret.

## Conséquences

- Si un écran "évolution du score dans le temps" devient nécessaire, ce
  choix devra être révisé : migration vers une table d'historique
  (`opportunity_score_history`) ou passage de `OpportunityScore` à un modèle
  append-only. Cette ADR sert de point de départ à cette discussion future.
- `scoring_version` est déjà en place sur chaque score : le jour où
  l'algorithme change (nouveaux poids, Market Signals connecté, passage au
  ML), tous les scores existants pourront être identifiés et retraités sans
  ambiguïté sur la méthode utilisée pour les produire.
- Le passage à un historique de scores, le jour où il sera nécessaire,
  n'impactera pas `OpportunityEngine` : le moteur reste "sans état" par
  conception, seule la couche de persistance changerait.
