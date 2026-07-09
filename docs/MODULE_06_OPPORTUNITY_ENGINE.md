# MODULE 06 — OPPORTUNITY ENGINE

## Objectif

Calculer, pour chaque entreprise, un score d'opportunité entre 0 et 100 —
jamais une boîte noire : chaque point du score doit pouvoir être expliqué.

---

## Livrables

- `app/engines/opportunity.py` — moteur de calcul pur (aucune dépendance
  SQLAlchemy/FastAPI), entièrement testable unitairement.
- `app/models/opportunity.py` — modèle `OpportunityScore` (une ligne active
  par entreprise).
- `app/repositories/opportunity.py` — accès DB (upsert, classement).
- `app/services/opportunity.py` — pont entre les modèles ORM et le moteur.
- `app/api/v1/endpoints/opportunity.py` — endpoints REST.
- `db/migrations/versions/006_opportunity_scores.py` — migration Alembic.
- `tests/unit/test_opportunity_engine.py` — tests unitaires du moteur pur
  (aucune DB requise, exécutables même sans dépendances installées).
- `tests/integration/test_opportunity.py` — tests d'intégration API.

## Endpoints

```
GET  /api/v1/companies/{id}/opportunity            — score actuel (calculé à la volée si absent)
POST /api/v1/companies/{id}/opportunity/recompute  — force le recalcul (analyst+)
GET  /api/v1/opportunities                         — entreprises triées par score décroissant
                                                       (filtres: min_score, conviction, stage)
```

## Composants du score (scoring_version = 1)

| Composant           | Poids | Source                                                |
|----------------------|-------|--------------------------------------------------------|
| Events                | 35 %  | `EventService.get_score_boost()` avec décroissance temporelle (demi-vie 90j) |
| Theme Strength        | 20 %  | Maturité des thèmes associés + bonus de convergence   |
| Company Quality       | 25 %  | Complétude du profil (9 champs clés) + statut         |
| Discovery Signals     | 20 %  | Corroboration multi-sources + fraîcheur (demi-vie 180j) |
| Market Signals        | 0 %   | Structure prête, **volontairement non connecté**       |

Le score global est la somme pondérée des composants connectés, borné à [0, 100].

## Stades d'opportunité

`early` → `acceleration` → `confirmation` → `mature`, déterminés
heuristiquement à partir du volume d'événements récents, du score, et de la
maturité des thèmes — chaque stade est accompagné d'une phrase de
justification (`stage_rationale`).

## Effets de bord du recalcul

- Répercute le score sur `Company.atlas_score` (champ prévu au Module 02).
- Marque les events consommés comme `is_processed = True`.

## Ce qui est volontairement hors scope

- **Market Signals** : structure présente dans l'API (`value: null`,
  `is_connected: false`) mais aucune source de données de marché n'est
  branchée. À faire dans un module futur, sans changement de contrat API.
- **Historique de scores dans le temps** : une seule ligne active par
  entreprise est conservée. Voir ADR-004 pour la justification et les
  conditions de révision de ce choix.
- **Machine Learning** : le moteur est conçu pour être remplaçable (aucune
  dépendance ORM), mais reste à base de règles explicites pour l'instant —
  conformément au principe "toujours expliquer le score".

## Dette technique identifiée

- Les ADR-001 à ADR-003 existent mais sont vides dans le dépôt actuel — à
  compléter (voir ADR-004 pour le format attendu, il documente ce module).
- Aucun `CHANGELOG.md` n'existe encore à la racine du projet.
- Les tests d'intégration de ce module n'ont pas pu être exécutés dans cet
  environnement (pas d'accès réseau pour installer les dépendances ni PostgreSQL
  disponible) — ils suivent strictement le style des modules précédents et sont
  prêts à tourner via `docker compose up -d && pytest`. Les tests unitaires du
  moteur pur, eux, ont été exécutés et passent (22/22 vérifications).
