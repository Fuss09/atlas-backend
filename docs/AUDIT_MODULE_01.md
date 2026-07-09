# Audit — Module 01 Foundation
**Atlas Market Intelligence**
**Date :** 2025-01-01
**Rôle :** Tech Lead — Code Review avant merge

---

## Préambule

Cet audit couvre le Module 01 Foundation du projet Atlas. Il a été réalisé après une lecture complète de l'ensemble du code produit et de toute la documentation disponible dans le dépôt (`docs/`, `ATLAS_AI_GUIDELINES.md`, les ADR, les specs de chaque moteur).

Je n'atténue aucun défaut. Un audit bienveillant qui cache des problèmes est inutile.

---

## 1. Conformité

### Conformité avec MODULE_01_FOUNDATION.md

Le document spec liste les livrables attendus. Voici l'état réel :

| Livrable | Statut | Remarque |
|---|---|---|
| FastAPI | ✅ | Application factory propre |
| Docker | ✅ | Multi-stage Dockerfile |
| Docker Compose | ✅ | PostgreSQL, Redis, RabbitMQ, Neo4j |
| PostgreSQL | ✅ | SQLAlchemy 2 async, pool configuré |
| Redis | ✅ | Configuré, health check, non utilisé en runtime |
| RabbitMQ | ✅ | Configuré, health check, non utilisé en runtime |
| Neo4j | ✅ | Configuré, health check, non utilisé en runtime |
| Alembic | ✅ | Migration initiale écrite |
| SQLAlchemy | ✅ | Version 2, async |
| Pydantic v2 | ✅ | Schémas bien structurés |
| JWT Authentication | ✅ | Access + refresh tokens |
| Health Check | ✅ | /health et /ready |
| Swagger | ✅ | Disponible en dev |
| OpenAPI | ✅ | Disponible en dev |
| Logging | ✅ | structlog, JSON en prod |
| GitHub Actions | ✅ | CI complète (lint, test, build) |
| Pytest | ✅ | Fixtures async, tests unitaires + intégration |
| Ruff | ✅ | Configuré dans pyproject.toml |
| Black | ✅ | Configuré dans pyproject.toml |
| Pre-commit | ✅ | Hooks ruff + black |
| Configuration ENV | ✅ | Pydantic Settings v2, .env.example |
| GET /health | ✅ | |
| GET /ready | ✅ | |
| POST /auth/login | ✅ | |
| POST /auth/register | ✅ | |
| POST /auth/refresh | ✅ | |
| GET /me | ✅ | Implémenté comme /auth/me |

**Conclusion conformité spec :** 100% des livrables demandés sont présents.

---

### Conformité avec ATLAS_BACKEND_SPEC.md

Le fichier backend spec est plus détaillé. Points supplémentaires requis :

| Requis par la spec | Statut | Raison si absent |
|---|---|---|
| Python 3.13 | ⚠️ Python 3.12 | 3.13 non stable avec asyncpg/neo4j-driver au moment du développement |
| OAuth Google | ⚠️ Partiel | Modèle et DB prêts, flow OAuth non implémenté — acceptable pour Module 01 |
| OAuth GitHub | ⚠️ Partiel | Idem |
| Celery | ❌ Absent | Non implémenté. Choix délibéré documenté : Celery sans tâches = complexité vide |
| OpenSearch | ❌ Absent | Non implémenté. La spec le cite mais aucun use-case Module 01 ne le nécessite |
| S3 Compatible | ❌ Absent | Non implémenté. Aucun use-case stockage dans Module 01 |
| Prometheus | ⚠️ Partiel | Dépendance présente dans pyproject.toml, aucun endpoint /metrics implémenté |
| Sentry | ❌ Absent | Non implémenté |
| Rate limiting | ❌ Absent | Exception handler présent, middleware absent |
| user_id dans logs | ⚠️ Partiel | request_id et execution_time présents, user_id non injecté automatiquement |
| Pagination sur toutes les listes | ⚠️ Partiel | PaginationParams implémenté, non utilisé (pas encore de listes) |
| Architecture arborescente complète | ✅ | engines/, workers/, collectors/, graph/, ai/ créés |

---

### Conformité avec ATLAS_AI_GUIDELINES.md et ATLAS_FOUNDATION.md

Ces fichiers définissent la philosophie du produit, pas des livrables techniques. La conformité est évaluée sur l'esprit :

- **Historique immuable** : ✅ SoftDelete systématique. Aucune suppression physique.
- **Explicabilité** : ✅ Principe respecté dans les choix de conception.
- **Traçabilité** : ⚠️ Le champ `source` mentionné dans DATA_MODEL (toute donnée doit avoir une source) n'est pas implémenté. Normal pour Module 01, mais à anticiper dès Module 02.
- **Less Noise. More Intelligence.** : ✅ Aucune fonctionnalité superflue dans ce module.

---

## 2. Auto-évaluation

### Architecture — 8/10

La séparation en couches est propre et tient ses promesses : `router → deps → service → repository → model`. FastAPI ne touche jamais SQLAlchemy directement, les services ne connaissent pas FastAPI. L'Application Factory facilite les tests.

**Pourquoi pas 9 ou 10 :** Le moteur SQLAlchemy est instancié au niveau module (`_engine = _create_engine()`) — ce qui rend le remplacement difficile sans passer par les `dependency_overrides`. Ce serait plus propre avec une injection explicite. Point mineur mais visible dans une revue senior.

---

### Qualité du code — 7/10

Le code est lisible, typé, documenté, cohérent dans son style. Docstrings sur toutes les classes et méthodes non triviales. Bonne utilisation des types Python modernes (`str | None`, `Mapped[...]`).

**Pourquoi pas 8 :** Quatre défauts concrets identifiés lors de la relecture :

1. `config.py` importe `PostgresDsn` et `RedisDsn` depuis pydantic sans les utiliser.
2. `database.py` importe `event` et `MappedColumn` sans les utiliser.
3. Le dummy hash anti-timing attack utilise `"$2b$12$..."` — format bcrypt — alors que le système utilise maintenant Argon2id. Incohérence fonctionnelle potentielle selon l'implémentation de `verify_password`.
4. Dans `health.py`, `get_settings` est importé deux fois : une fois en top-level, une fois dans le body de la fonction `ready()`. Doublon inutile.
5. Le commentaire dans `test_security.py` dit "bcrypt utilise un salt aléatoire" alors que l'algorithme est Argon2id.
6. Le docstring `user.py` (modèle) décrit "mot de passe hashé bcrypt" — aussi obsolète.

Ces défauts auraient été bloqués par un pre-commit hook ruff activé en mode strict.

---

### Maintenabilité — 9/10

C'est le point fort du module. La structure est suffisamment explicite pour qu'un développeur n'ayant pas participé au projet comprenne rapidement où ajouter un nouveau moteur, un nouveau modèle, ou un nouveau endpoint.

Les `__init__.py` vides dans `engines/`, `workers/`, `collectors/`, `graph/`, `ai/` signalent clairement les zones d'extension future.

**Pourquoi pas 10 :** L'absence de CONTRIBUTING.md technique (comment ajouter un moteur, quel pattern suivre, comment créer une migration) laissera des ambiguïtés au prochain développeur.

---

### Évolutivité — 8/10

L'arborescence anticipe correctement les 7 modules suivants. Le pattern Repository/Service/Schema est facilement reproductible. Les feature flags permettent d'activer progressivement les services.

**Pourquoi pas 9 :** La configuration des sous-settings (`DatabaseSettings`, `RedisSettings`) utilise `env_prefix` via `model_config` dans des classes `BaseSettings` imbriquées — ce qui peut poser des problèmes de résolution de variables d'environnement avec certains déploiements (Railway notamment, ton infrastructure habituelle). Ce point méritera un test de déploiement réel avant le Module 02.

---

### Sécurité — 7/10

Les bonnes bases sont là : Argon2id, JWT avec séparation access/refresh, anti-timing attack sur le login, pas de trace Python exposée, validation des inputs via Pydantic.

**Pourquoi pas 8 :** Cinq lacunes identifiées :

1. **Pas de rate limiting** sur `/auth/login` et `/auth/register`. Un attaquant peut tenter des millions de mots de passe sans friction.
2. **Pas de JWT token blacklist/revocation**. Un refresh token volé est valide 30 jours sans possibilité de révocation.
3. **Le dummy hash Argon2 est faux**. Le fallback `"$2b$12$..."` est un hash bcrypt. `verify_password` (Argon2id) retournera probablement une erreur ou `False` sur ce hash — ce qui est correct fonctionnellement, mais incorrect sémantiquement. Il faut remplacer par un hash Argon2id valide ou capturer l'exception.
4. **Headers de sécurité absents** : `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`. Trivial à ajouter via `SecurityHeadersMiddleware`.
5. **Pas de validation de la longueur max du password** côté service — Pydantic valide `max_length=128` mais Argon2 tronque silencieusement au-delà de certaines tailles selon la configuration.

---

### Performance — 7/10

L'async est correctement utilisé partout. Le pool de connexions PostgreSQL est configuré. `pool_pre_ping=True` évite les connexions mortes.

**Pourquoi pas 8 :** 

1. Redis est configuré mais **aucun cache n'est utilisé** (normal pour Module 01, mais les patterns de cache ne sont pas encore définis).
2. `echo_pool=True` est activé en développement — verbeux mais acceptable.
3. L'endpoint `/ready` fait des connexions en temps réel à chaque appel vers Redis, RabbitMQ, Neo4j. En production sous load balancer, cela peut créer de la charge inutile. Un cache d'état de 10 secondes serait plus raisonnable.

---

### Documentation — 7/10

Le README est complet et opérationnel. Les docstrings couvrent l'essentiel. Les fichiers de configuration sont commentés.

**Pourquoi pas 8 :** 

1. Les ADR (ADR-001, ADR-002, ADR-003) sont des fichiers vides dans le repo. Les décisions prises ne sont pas encore documentées formellement.
2. Aucun CHANGELOG.
3. Aucun guide "Comment contribuer au Module 02" — laissé au prochain message du projet.
4. Les endpoints n'ont pas tous de descriptions OpenAPI détaillées (paramètres, exemples de réponse).

---

### Tests — 6/10

26 tests au total. Les tests de sécurité (JWT, hashing) sont complets. Les tests d'intégration couvrent les parcours principaux d'authentification.

**Pourquoi 6 et pas davantage :**

1. **Couverture estimée insuffisante pour atteindre les 80% requis.** Les modules suivants ne sont pas couverts : `config.py`, `logging.py`, `exceptions.py`, `models/base.py`, `repositories/base.py`, `middleware.py`, `exception_handlers.py`. En l'état, sans une base de données de test disponible, le seuil de 80% configuré dans `pytest.ini` ferait échouer le CI.
2. **Les tests d'intégration dépendent d'une base PostgreSQL réelle** — ce qui est le bon choix de design, mais cela signifie que les tests ne peuvent pas tourner sans infrastructure. Il manque des instructions pour préparer la base de test.
3. **Aucun test négatif sur les repositories** (get_by_id d'un UUID inexistant, soft_delete d'un objet déjà supprimé, etc.).
4. **Aucun test du middleware** (vérification du X-Request-ID dans les headers de réponse, bien que présent dans les tests d'intégration — c'est le seul point positif sur ce volet).
5. **Aucun test de l'endpoint `/ready`** — qui est pourtant un code de production critique.

---

## 3. Dette technique

### DT-001 — Imports inutilisés dans config.py et database.py
**Pourquoi :** Probablement hérités de versions de code antérieures pendant la rédaction.
**Impact :** Bas. Ruff les détecterait en CI si le hook était actif.
**Quand traiter :** Avant le merge. Correction triviale (5 minutes).

---

### DT-002 — Dummy hash incohérent (bcrypt vs Argon2id)
**Pourquoi :** La migration de `passlib/bcrypt` vers `pwdlib/argon2id` a été faite en cours de route. Le dummy hash n'a pas été mis à jour.
**Impact :** Moyen. Fonctionnellement, `verify_password` retourne `False` sur ce hash malformé (comportement correct), mais c'est une bombe à retardement si quelqu'un change l'implémentation de `verify_password` pour lever une exception sur hash invalide.
**Quand traiter :** Avant le merge. Remplacer par un hash Argon2id valide généré en amont, ou capturer l'exception dans le flux de login.

---

### DT-003 — Commentaires/docstrings bcrypt obsolètes
**Pourquoi :** Même raison que DT-002.
**Impact :** Bas. Risque de confusion documentaire.
**Quand traiter :** En même temps que DT-002.

---

### DT-004 — Double import get_settings dans health.py
**Pourquoi :** Imports placés dans le corps de la fonction `ready()` pour éviter une dépendance circulaire potentielle. La dépendance au niveau module est superflue.
**Impact :** Bas. Légère confusion à la lecture.
**Quand traiter :** Avant le merge.

---

### DT-005 — Moteur SQLAlchemy instancié au niveau module
**Pourquoi :** Pattern courant mais qui complique les tests et le remplacement de la DB.
**Impact :** Moyen. Les tests utilisent `dependency_overrides` pour contourner, mais une approche avec injection explicite serait plus propre à l'échelle.
**Quand traiter :** Module 02 ou 03, lors du refactoring des tests d'intégration si nécessaire.

---

### DT-006 — Pas de rate limiting sur /auth/*
**Pourquoi :** Hors scope Module 01, décision documentée.
**Impact :** Élevé en production. Les endpoints d'auth sont exposés sans protection contre les attaques par force brute.
**Quand traiter :** Avant tout déploiement public. `slowapi` suffit pour le MVP (10 lignes de code).

---

### DT-007 — Pas de révocation des refresh tokens
**Pourquoi :** Nécessite un stockage (Redis blacklist ou table DB). Hors scope Module 01.
**Impact :** Moyen. Un token volé est valide 30 jours.
**Quand traiter :** Module 02. Implémentation simple avec Redis (stocker le `jti` révoqué avec TTL).

---

### DT-008 — Prometheus installé mais non exposé
**Pourquoi :** Dépendance ajoutée, endpoint `/metrics` non créé.
**Impact :** Bas en développement. Moyen si le monitoring est prévu pour le Module 02.
**Quand traiter :** Lors de la mise en place du monitoring (probablement Module 05 ou 06).

---

### DT-009 — Headers de sécurité HTTP absents
**Pourquoi :** Hors scope explicite du Module 01.
**Impact :** Moyen. OWASP recommande ces headers pour toute API publique.
**Quand traiter :** Avant déploiement sur une URL publique. `starlette.middleware.trustedhost` + headers manuels = 30 lignes.

---

### DT-010 — Couverture de tests insuffisante pour atteindre 80%
**Pourquoi :** Le Module 01 pose les bases mais ne couvre pas tous ses propres composants.
**Impact :** Élevé. La CI échouerait si elle tournait sur une vraie DB de test.
**Quand traiter :** Avant le merge ou immédiatement après. Tests manquants prioritaires : repositories/base.py, exception_handlers.py, middleware.py.

---

### DT-011 — docker-compose version "3.9" (déprécié)
**Pourquoi :** La clé `version` est dépréciée dans Docker Compose v2. Elle est ignorée mais génère un warning.
**Impact :** Bas. Fonctionnel mais non-conforme aux bonnes pratiques actuelles.
**Quand traiter :** Correction triviale : supprimer la ligne `version: "3.9"`.

---

### DT-012 — Sous-settings Pydantic avec env_prefix non testés sur Railway
**Pourquoi :** Le pattern `DatabaseSettings(BaseSettings)` avec `env_prefix="POSTGRES_"` intégré dans `Settings` peut avoir un comportement non intuitif selon les versions de pydantic-settings.
**Impact :** Potentiellement élevé lors du premier déploiement sur Railway.
**Quand traiter :** À tester avant déploiement. Alternative : configurer toutes les variables dans un seul `Settings` plat.

---

## 4. Revue critique — Ce que je ferais différemment

### Ce que je reconstruirais

**1. Le moteur SQLAlchemy injecté, pas global**

```python
# Actuel — problématique
_engine = _create_engine()  # instancié à l'import

# Mieux — lifecycle management propre
@asynccontextmanager
async def get_engine():
    engine = create_async_engine(...)
    try:
        yield engine
    finally:
        await engine.dispose()
```

Le lifespan FastAPI est le bon endroit pour créer et détruire le moteur. Cela facilite les tests sans `dependency_overrides`.

**2. Le UserService ne devrait pas instancier son Repository**

```python
# Actuel
class UserService:
    def __init__(self, session):
        self.repo = UserRepository(session)  # couplage direct

# Mieux — injection du repository
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo
```

Cela permet de mocker le repository sans toucher à SQLAlchemy dans les tests unitaires du service. En l'état, tester `UserService` nécessite une vraie DB.

**3. Un `conftest.py` d'environnement séparé**

La variable `TEST_DATABASE_URL` est hardcodée dans `conftest.py`. Elle devrait venir d'une variable d'environnement avec fallback, pour permettre aux CI d'utiliser des URLs différentes sans modifier le code.

**4. Rate limiting dès Module 01**

`slowapi` s'installe en 2 lignes et protège dès le premier déploiement. Aucune raison de le reporter.

**5. Un fichier `app/core/constants.py`**

Centraliser les constantes qui seront partagées entre modules (noms des queues RabbitMQ, clés de cache Redis, préfixes d'index OpenSearch). Commencer ce fichier vide avec les conventions attend dès Module 01 évite la fragmentation plus tard.

### Choix techniques que je remettrais en question

**`python-jose` pour le JWT**

`python-jose` n'est plus maintenu activement. En 2025, `PyJWT` est plus robuste, plus maintenu, et officiellement recommandé par FastAPI. Migration triviale mais mieux faite tôt.

**Absence de `__all__` dans les modules**

Sans `__all__` définis, les imports `from app.core import *` peuvent créer des fuites. Convention utile dans un projet de cette taille.

---

## 5. Analyse par composant

### Structure du projet — Bonne

L'arborescence est cohérente avec la spec et anticipe correctement les modules futurs. Le seul point discutable : `app/db/migrations/` est à l'intérieur du package Python. Certaines équipes préfèrent un dossier `migrations/` à la racine de `backend/` pour le séparer du code applicatif. Les deux approches sont défendables.

---

### Repository Pattern — Très bon

`BaseRepository[ModelType]` générique avec Generic est une implémentation correcte. Le hard limit sur `limit = min(limit, 100)` dans `get_all` est un détail qui évite les abus. La séparation `get_by_id` / `get_by_email` est propre.

**Point à challenger :** `BaseRepository.update()` accepte `**kwargs: Any` sans validation. Un développeur pourrait passer n'importe quelle colonne, y compris `id`, `created_at`, ou `is_deleted`. Il faudra une liste d'exclusion ou une validation au niveau service avant le Module 02.

---

### Services — Bons, avec une limite

`UserService` est propre. La protection anti-timing attack dans `login()` est bien pensée — mais comme mentionné, le dummy hash est incohérent avec Argon2id.

**Limitation :** Les services ne sont pas testables unitairement sans une DB réelle, car ils instancient leur propre repository. Voir point 4 ci-dessus.

---

### Gestion de la configuration — Très bonne

La hiérarchie `Settings > DatabaseSettings > RedisSettings…` est élégante et évite le flat dict illisible de 40 variables. Les `@property` pour les URLs construites sont une bonne pratique.

**Risque identifié :** Le `@lru_cache(maxsize=1)` sur `get_settings()` est un piège en tests. Si un test modifie des variables d'environnement, le cache retourne l'ancienne valeur. La solution est d'appeler `get_settings.cache_clear()` dans les fixtures — ce qui est fait dans le conftest, mais non documenté.

---

### Logging — Très bon

`structlog` est le bon choix. Le format JSON en production est compatible avec Loki, Datadog, et la plupart des stacks de monitoring modernes. Le `request_id` dans chaque log via `contextvars` est une pratique de production essentielle.

**Point manquant :** Le `user_id` n'est pas automatiquement injecté dans les logs des requêtes authentifiées. La spec backend l'exige explicitement. À ajouter dans le middleware une fois le `CurrentUser` disponible dans le contexte.

---

### Gestion des erreurs — Très bonne

La hiérarchie d'exceptions est complète et extensible. Le format normalisé `{"error": {"code": ..., "message": ..., "details": ...}}` est cohérent et documentable. Le handler `Exception` générique de dernier recours est correct.

**Point discutable :** Le handler `Exception` générique log `exc_info=exc`. Selon la configuration de structlog en production, cela peut exposer des traces complètes dans les logs structurés — qui eux sont souvent accessibles à plus de personnes que le code source. Ce n'est pas un problème dans les logs internes, mais à surveiller si les logs sont envoyés vers un outil tiers (Datadog, Sentry).

---

### Docker — Bon

Le multi-stage est propre. L'utilisateur non-root (`atlas`) est une bonne pratique de sécurité souvent omise. Les healthchecks sur tous les services sont corrects.

**Points à améliorer :**
1. La ligne `version: "3.9"` est dépréciée (DT-011).
2. Le volume de code source monté dans le container backend (`./backend:/app`) en mode hot-reload est correct en dev, mais **doit absolument être retiré en production**. Une variable d'environnement ou un profil Docker Compose devrait gérer cette différence.
3. Neo4j Community Edition a des limitations importantes pour la production (voir Revue d'architecture du Module 01).

---

### CI/CD — Bonne

Le pipeline GitHub Actions couvre lint → tests → build Docker. La matrice de services (PostgreSQL, Redis, RabbitMQ) en CI est complète. Le cache Docker (`cache-from: type=gha`) accélérera les builds.

**Point manquant :** Pas de job de déploiement automatique (même vers un environnement de staging). Acceptable pour Module 01, à ajouter dès qu'un environnement Railway est configuré.

**Point à vérifier :** La CI désactive Neo4j (`FEATURE_NEO4J_ENABLED: "false"`) car indisponible en GitHub Actions. C'est pragmatique, mais cela signifie que la connectivité Neo4j n'est jamais testée automatiquement. À terme, envisager un service Neo4j dans la CI ou un mock.

---

### Sécurité — Acceptable pour un MVP, insuffisante pour la production

Points positifs : Argon2id, JWT avec rotation, anti-timing, pas de traces exposées.
Points manquants documentés en DT-006 à DT-009.

---

### Base de données — Bonne

`SoftDeleteMixin` systématique est aligné avec la philosophie "Atlas ne supprime jamais". Le `pool_pre_ping=True` évite les erreurs après inactivité. Les indexes sur `email` et `is_deleted` sont présents.

**Point manquant :** Le script `init.sql` crée la base `atlas_test`, mais **ne crée pas les extensions** (`uuid-ossp`, `pg_trgm`) pour la base principale avant que les migrations ne tournent. Le script PostgreSQL utilise `\c atlas` (métacommande psql) qui ne fonctionne pas via SQLAlchemy — ce script n'est exécuté que via Docker entrypoint. À vérifier que l'ordre d'exécution est garanti.

---

### Authentification — Bonne, avec lacunes connues

Les lacunes (OAuth flow, rate limiting, token revocation) sont documentées et justifiées. Le modèle de données supporte OAuth sans migration future.

**Point technique :** Le refresh token ne contient pas de `jti` (JWT ID unique). Sans `jti`, il est impossible d'invalider un token spécifique sans invalider tous les tokens de l'utilisateur. À ajouter avec Redis dès Module 02.

---

## 6. Préparation des futurs modules

### Company Engine (Module 02)
✅ **Prêt.** Le pattern Repository/Service/Schema/API est établi et reproductible. La migration Alembic est fonctionnelle. Le modèle `Company` avec ses attributs (ticker, exchange, isin, sector…) peut être ajouté sans toucher au Module 01.

⚠️ **Point à anticiper :** La spec demande OpenSearch pour toutes les recherches. Il faudra l'ajouter dans le `docker-compose.yml` et la configuration avant le Module 02.

---

### Theme Engine / Discovery Engine
✅ **Prêt structurellement.** Les dossiers `engines/` sont créés.

⚠️ **À définir :** Le pipeline de scoring (Conviction, Momentum, Innovation…) n'a aucune interface dans Module 01. Il faudra définir comment les engines communiquent entre eux (via RabbitMQ ? Via appels de service directs ?). Ce choix doit être documenté dans un ADR avant de commencer.

---

### Event Engine + Collecteurs
✅ **RabbitMQ configuré.** Les dossiers `workers/` et `collectors/` sont créés.

❌ **Celery absent.** L'Event Engine selon la spec nécessite des workers asynchrones. Sans Celery (ou équivalent), les collecteurs devront être des processus indépendants ou utiliser `asyncio` pur. Ce choix doit être fait avant le Module 03.

⚠️ **Fréquences définies dans la spec :** SEC toutes les 5 minutes, News toutes les 5 minutes, GitHub toutes les heures. Le scheduler (Celery Beat, APScheduler, ou cron) n'est pas encore décidé.

---

### Knowledge Graph (Neo4j)
✅ **Neo4j configuré et connecté.** Le dossier `graph/` est créé.

⚠️ **Community Edition** : Neo4j Community ne supporte pas le clustering. Pour un Knowledge Graph qui "doit devenir l'actif principal d'Atlas" (citation doc), Enterprise ou AuraDB sera probablement nécessaire.

❌ **Aucun schéma de graphe défini.** Les types de nœuds (Company, Technology, Theme, Person…) et les types de relations (SUPPLIES, INVESTS_IN, COMPETES_WITH…) ne sont pas encore modélisés. À faire en Module 04.

---

### Opportunity Engine / Stories Engine
✅ **Aucun obstacle bloquant issu du Module 01.**

⚠️ **Dépend fortement de l'IA** (OpenAI selon la spec). La configuration du client OpenAI et la gestion des coûts d'API devront être traitées. Aucune configuration OpenAI n'est présente dans les settings actuels.

---

### Point de risque transversal

La spec technique mentionne OpenSearch pour **toutes** les recherches. En l'état, aucun service OpenSearch n'est dans le `docker-compose.yml`. Si cette décision est maintenue, OpenSearch doit être ajouté avant que le Module 02 ne commence à implémenter des recherches — sinon les endpoints de recherche ne pourront pas être testés.

---

## 7. ADR — Architecture Decision Records

### ADR-001 — Choix du framework web : FastAPI

**Décision :** Utiliser FastAPI comme framework web backend.

**Contexte :** Atlas est une plateforme d'intelligence qui doit gérer des connexions concurrentes (collecteurs, utilisateurs, webhooks), exposer une API REST, et s'intégrer avec des modèles IA Python natifs.

**Alternatives envisagées :**
- Django REST Framework : Mature, mais synchrone par défaut, lourd pour une API pure.
- Flask + extensions : Trop minimal, nécessite de réassembler des briques.
- Litestar : Excellent, mais écosystème plus petit et équipe moins familière.

**Justification :** FastAPI est async natif, génère automatiquement Swagger et OpenAPI, s'intègre nativement avec Pydantic v2, et est adopté massivement dans l'écosystème Python IA/ML. Le typage fort facilite la maintenance long terme.

**Conséquences :** Toute la logique applicative est async. Les librairies non-async doivent être wrappées ou appelées dans un thread pool via `asyncio.to_thread()`.

---

### ADR-002 — Algorithme de hashing des mots de passe : Argon2id

**Décision :** Utiliser Argon2id via `pwdlib` pour le hashing des mots de passe.

**Contexte :** La librairie `passlib` (bcrypt) présente des incompatibilités avec Python 3.12+ et les versions récentes de `bcrypt`. Le projet démarre en 2025 et doit adopter les meilleures pratiques actuelles.

**Alternatives envisagées :**
- bcrypt via passlib : Instable sur Python 3.12+, bug de compatibilité actif.
- bcrypt via la librairie bcrypt directement : Fonctionnel mais inférieur à Argon2id.
- PBKDF2 : Standard FIPS mais inférieur à Argon2 en résistance aux attaques GPU.

**Justification :** Argon2id est l'algorithme recommandé par OWASP depuis 2021 pour le hashing de mots de passe. Il est résistant aux attaques GPU et aux attaques par canal auxiliaire. `pwdlib` est activement maintenu et conçu pour FastAPI.

**Conséquences :** Les mots de passe existants (si migration depuis un système bcrypt) devront être re-hashés à la prochaine connexion. Le dummy hash anti-timing attack doit utiliser un hash Argon2id valide (dette DT-002).

---

### ADR-003 — Stratégie de suppression : Soft Delete systématique

**Décision :** Toutes les entités Atlas utilisent le soft delete. Aucune suppression physique en production.

**Contexte :** Atlas est une plateforme de données financières dont la valeur croît avec l'historique. Les données supprimées peuvent être nécessaires pour : le backtesting, l'entraînement ML (Module 06 dans le projet connexe FMI), l'audit réglementaire.

**Alternatives envisagées :**
- Suppression physique avec table d'archive : Complexe, fragile, difficile à maintenir.
- Suppression physique uniquement : Perd l'historique, incompatible avec la vision ML.
- Event sourcing complet : Trop complexe pour le MVP.

**Justification :** Le soft delete avec `is_deleted` et `deleted_at` est la solution la plus simple qui satisfait tous les besoins. Elle s'implémente une fois dans `AtlasBase` et s'applique automatiquement à tous les modèles.

**Conséquences :** Toutes les requêtes doivent filtrer sur `is_deleted = False` par défaut. Le `BaseRepository` l'impose, mais les requêtes SQL directes (Alembic, scripts de maintenance) devront l'appliquer manuellement.

---

### ADR-004 — Pattern Repository/Service/Schema

**Décision :** Chaque entité métier est représentée par un triplet Repository (accès données) / Service (logique métier) / Schema (validation).

**Contexte :** Atlas va croître vers 10+ moteurs et des dizaines d'entités. La séparation des responsabilités doit être structurelle, pas conventionnelle.

**Alternatives envisagées :**
- Active Record pattern (Django-style) : Le modèle contient sa propre logique d'accès. Plus rapide à démarrer, difficile à tester.
- Service uniquement (sans Repository) : Le service appelle SQLAlchemy directement. Difficile à mocker.

**Justification :** Le pattern tri-couche permet de tester chaque couche indépendamment, de changer l'ORM sans toucher à la logique métier, et de maintenir une séparation claire entre accès données et règles métier.

**Conséquences :** Chaque nouveau module devra créer Repository + Service + Schemas. Légère verbosité initiale, mais excellente maintenabilité à long terme.

---

### ADR-005 — Gestion des tokens JWT : Access + Refresh sans révocation (MVP)

**Décision :** Implémenter des tokens JWT access (30 min) et refresh (30 jours). Pas de mécanisme de révocation pour le MVP.

**Contexte :** Un système de révocation nécessite un stockage persistant (Redis blacklist) et complexifie les flux. Pour le MVP d'un outil d'analyse personnel, le risque de vol de token est faible.

**Alternatives envisagées :**
- Tokens stateless sans refresh : Durée de vie courte, UX dégradée.
- Tokens avec révocation complète (jti + Redis) : Correct, mais complexité inutile pour le MVP.
- Sessions côté serveur : Contre la philosophie API stateless.

**Justification :** Les tokens de 30 minutes limitent la fenêtre d'exposition en cas de vol. La révocation sera ajoutée en Module 02 avec Redis (stocker les `jti` révoqués avec TTL).

**Conséquences :** Un refresh token volé est valide 30 jours. Acceptable pour un MVP, inacceptable pour une version publique. DT-007 documente ce risque.

---

### ADR-006 — Python 3.12 au lieu de 3.13

**Décision :** Utiliser Python 3.12 comme version de référence malgré la spec demandant 3.13.

**Contexte :** Python 3.13 est sorti en octobre 2024 mais plusieurs dépendances critiques d'Atlas (`asyncpg`, `neo4j-driver`) n'ont pas de wheels stables sur toutes les plateformes pour 3.13 au moment du développement du Module 01.

**Alternatives envisagées :**
- Python 3.13 strict : Risque de blocage sur certaines dépendances en CI/CD.
- Python 3.11 : Stable mais n'apporte pas les améliorations de typing de 3.12.

**Justification :** 3.12 offre toutes les fonctionnalités utilisées (typing amélioré, `str | None`, `Mapped[...]`). La migration vers 3.13 sera triviale dès que l'écosystème est stable (estimé Q2 2025).

**Conséquences :** La spec devra être mise à jour pour documenter cette décision. Migration vers 3.13 à planifier avant Module 03.

---

## 8. CHANGELOG — Module 01

```markdown
# CHANGELOG

## [0.1.0] — Module 01 Foundation — 2025-01-01

### Ajouté

#### Infrastructure
- Application FastAPI avec pattern Application Factory et lifespan management
- Docker multi-stage (builder + runtime non-root) pour le backend
- docker-compose.yml : PostgreSQL 17, Redis 7.4, RabbitMQ 4.0, Neo4j 5.26
- Script d'initialisation PostgreSQL (base principale + base de test)
- CI GitHub Actions : lint (ruff + black) → tests → build Docker image vers GHCR
- Pre-commit hooks : ruff (lint + fix) + black (format)

#### Configuration
- Système de configuration centralisé via Pydantic Settings v2
- Sous-configurations typées par service (DatabaseSettings, RedisSettings, RabbitMQSettings, Neo4jSettings, JWTSettings)
- Feature flags pour désactiver Neo4j/RabbitMQ (utile en CI et développement)
- Fichier .env.example documenté

#### Sécurité & Authentification
- Hashing des mots de passe avec Argon2id (via pwdlib)
- Authentification JWT : access tokens (30 min) + refresh tokens (30 jours)
- Protection anti-timing attack sur le login
- Validation de la complexité des mots de passe (uppercase + chiffre requis)
- Modèle User avec support local + OAuth Google/GitHub (DB prête, flow à implémenter)

#### Base de données
- SQLAlchemy 2 en mode async (asyncpg)
- Classe de base AtlasBase : UUID primaire, timestamps (created_at, updated_at), SoftDelete
- Modèle User avec rôles (user, analyst, admin)
- Migrations Alembic : migration initiale (table users + enums + indexes)
- Health check de connexion à la DB au démarrage

#### API
- GET /health — liveness check
- GET /ready — readiness check (PostgreSQL, Redis, RabbitMQ, Neo4j)
- POST /api/v1/auth/register — inscription
- POST /api/v1/auth/login — connexion
- POST /api/v1/auth/refresh — rafraîchissement des tokens
- GET /api/v1/auth/me — profil de l'utilisateur authentifié

#### Qualité
- Hiérarchie complète d'exceptions métier (20 types)
- Exception handlers normalisés (format JSON uniforme, jamais de trace Python exposée)
- Middleware de logging des requêtes (request_id UUID, execution_time, status_code)
- Logging structuré avec structlog (JSON en production, coloré en développement)
- Repository Pattern générique avec BaseRepository[ModelType]
- Paramètres de pagination standardisés (PaginationParams)
- 26 tests : unitaires (security) + intégration (auth endpoints)
- Swagger/OpenAPI disponible en développement

#### Structure
- Arborescence anticipant les 7 modules futurs : engines/, workers/, collectors/, graph/, ai/

### Technologies retenues
- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic
- PostgreSQL 17, Redis 7, RabbitMQ 4, Neo4j 5
- Argon2id (pwdlib), python-jose (JWT)
- structlog, pytest-asyncio, httpx
- ruff, black, pre-commit
- Docker, GitHub Actions

### Décisions d'architecture importantes
- ADR-001 : FastAPI comme framework web
- ADR-002 : Argon2id pour le hashing des mots de passe
- ADR-003 : Soft Delete systématique sur toutes les entités
- ADR-004 : Pattern Repository/Service/Schema
- ADR-005 : JWT access + refresh sans révocation (MVP)
- ADR-006 : Python 3.12 (3.13 instable avec asyncpg au moment du dev)

### Points reportés aux prochains modules
- OAuth Google et GitHub (modèle DB prêt, flow à implémenter en Module 02)
- Rate limiting sur /auth/* (à ajouter avec slowapi avant tout déploiement public)
- Révocation des refresh tokens via Redis jti blacklist (Module 02)
- OpenSearch pour la recherche (à ajouter avant Module 02 Company Engine)
- Celery pour les workers de collecte (Module 03 Event Engine)
- S3 pour le stockage de documents (Module 03+)
- Prometheus /metrics endpoint (Module 05+)
- Sentry pour le tracking d'erreurs en production (Module 02+)
- Schéma Neo4j (nœuds et relations) (Module 04 Knowledge Graph)
- Configuration client OpenAI (Module 05 Intelligence Engine)
```

---

## 9. Validation finale

### Ce Module 01 est-il prêt à être fusionné dans la branche principale ?

**Réponse honnête : Non, pas encore. Mais à une condition très proche du merge.**

Ce module pose des bases solides et répond à 100% des livrables demandés dans `MODULE_01_FOUNDATION.md`. L'architecture est bonne, le code est lisible, la structure anticipe correctement les futurs modules.

**Cependant, trois points bloquants doivent être traités avant le merge :**

---

**Bloquant 1 — DT-001/DT-002/DT-003 : Incohérences bcrypt/Argon2id**

Le dummy hash `"$2b$12$..."` et les commentaires/docstrings bcrypt sont des erreurs factuelles dans le code. Elles indiquent une migration incomplète et peuvent induire en erreur tout développeur qui reprend le code. Correction estimée : 15 minutes.

---

**Bloquant 2 — DT-001 : Imports inutilisés**

`PostgresDsn`, `RedisDsn`, `event`, `MappedColumn` importés sans utilisation. Ces imports seraient bloqués par la CI ruff si elle était correctement configurée. Ils doivent être propres avant le merge. Correction estimée : 5 minutes.

---

**Bloquant 3 — DT-010 : Couverture de tests insuffisante**

La configuration `--cov-fail-under=80` dans `pyproject.toml` signifie que la CI échouerait si elle tournait contre une vraie base de données. Les modules non couverts sont : `repositories/base.py`, `exception_handlers.py`, `middleware.py`, `models/base.py`. Il faut soit ajouter ces tests, soit abaisser temporairement le seuil à 60% avec un commentaire explicite de roadmap.

---

**Non bloquants mais recommandés avant merge :**
- Corriger la ligne `version: "3.9"` dans docker-compose.yml (5 secondes)
- Corriger le double import `get_settings` dans health.py (2 minutes)
- Ajouter les ADR dans les fichiers existants du dossier `docs/adr/`
- Ajouter ce CHANGELOG au dépôt

---

**Délai estimé pour atteindre le merge :** 2 à 4 heures de travail, dont la majorité sur les tests manquants.

Une fois ces corrections apportées, le Module 01 constitue une fondation technique sérieuse, maintenable, et correctement dimensionnée pour accueillir les 7 modules suivants. Il n'y a aucune dette d'architecture structurelle qui nécessiterait une refonte — seulement des finitions.

---

*Audit réalisé par Claude (Lead Software Engineer) — Atlas Module 01 — v0.1.0*
