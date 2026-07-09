# Atlas — Market Intelligence Platform

> *Less Noise. More Intelligence.*

Atlas est une plateforme de découverte et d'analyse des opportunités d'investissement.
Elle aide les investisseurs à comprendre les tendances émergentes avant qu'elles deviennent évidentes.

---

## Module 01 — Foundation

Ce module constitue la fondation technique sur laquelle tous les futurs modules s'appuient.

### Stack

| Composant | Technologie |
|-----------|-------------|
| Backend   | Python 3.12 + FastAPI |
| ORM       | SQLAlchemy 2 (async) |
| Migrations | Alembic |
| Auth       | JWT (HS256) |
| Cache      | Redis 7 |
| Queue      | RabbitMQ 4 |
| Graph DB   | Neo4j 5 |
| Validation | Pydantic v2 |
| Tests      | Pytest + pytest-asyncio |
| Lint       | Ruff + Black |
| CI/CD      | GitHub Actions |

---

## Démarrage rapide

### Prérequis

- Docker Desktop (ou Docker + Docker Compose)
- Git

### 1. Cloner et configurer

```bash
git clone https://github.com/Fuss09/atlas.git
cd atlas

# Copier et adapter les variables d'environnement
cp .env.example .env
```

### 2. Démarrer tous les services

```bash
docker compose up -d
```

Cela démarre : PostgreSQL, Redis, RabbitMQ, Neo4j, et le backend FastAPI.

### 3. Appliquer les migrations

```bash
docker compose --profile migrate up migrate
```

Ou depuis le container backend :

```bash
docker compose exec backend alembic upgrade head
```

### 4. Charger le dataset de démonstration (recommandé)

Atlas ne contient aucune donnée après les migrations — seuls les 12 thèmes
de référence (`themes`) sont pré-remplis. Pour explorer le produit sans
connecter de source externe (SEC, GitHub, YCombinator...), un script de
seed insère un jeu de données réaliste et cohérent.

```bash
docker compose exec backend python -m scripts.seed_demo
```

Ou en local sans Docker :

```bash
cd backend
python -m scripts.seed_demo
```

Ce script insère :

- **10 entreprises** réparties sur 4 domaines : IA, Informatique quantique,
  Biotechnologie, Énergie
- Leurs **associations aux thèmes** déjà seedés (IA → Artificial
  Intelligence, etc.)
- **32 événements** variés (levées de fonds, dépôts SEC, approbations FDA,
  activité GitHub, acquisitions, partenariats...) répartis sur les ~90
  derniers jours
- Un **job + une source de découverte** par entreprise, pour que l'onglet
  Sources et le score ne soient jamais vides
- **8 relations** dans le Knowledge Graph, à l'intérieur et entre les
  quatre domaines

Les **scores d'opportunité ne sont pas insérés directement** — le script
appelle le vrai moteur de scoring (`OpportunityScoreService.recompute`)
contre les données qu'il vient de créer. Le score que vous verrez dans
l'interface est un score réellement calculé, pas une valeur choisie à la
main.

Le script est idempotent : le relancer ne duplique rien.

### 5. Vérifier

```bash
# Santé de l'application
curl http://localhost:8000/health

# Disponibilité de tous les services
curl http://localhost:8000/ready

# Documentation API
open http://localhost:8000/docs

# Confirmer que le seed a bien créé des entreprises
curl http://localhost:8000/api/v1/companies | head -c 300
```

---

## Développement local (sans Docker)

```bash
cd backend

# Créer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Installer les dépendances
pip install -e ".[dev]"

# Configurer l'environnement
cp ../.env.example .env
# Éditer .env avec vos credentials locaux

# Appliquer les migrations
alembic upgrade head

# Charger le dataset de démonstration (optionnel mais recommandé)
python -m scripts.seed_demo

# Démarrer le serveur
uvicorn app.main:app --reload
```

---

## Tests

```bash
cd backend

# Tous les tests
pytest

# Avec couverture détaillée
pytest --cov=app --cov-report=html

# Tests unitaires uniquement
pytest tests/unit/

# Tests d'intégration uniquement
pytest tests/integration/

# Un test spécifique
pytest tests/unit/test_security.py::TestJWT::test_create_and_decode_access_token -v
```

---

## Migrations

```bash
cd backend

# Créer une nouvelle migration
alembic revision --autogenerate -m "description_de_la_migration"

# Appliquer toutes les migrations
alembic upgrade head

# Revenir en arrière
alembic downgrade -1

# Voir l'historique
alembic history

# Voir l'état actuel
alembic current
```

---

## API Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET    | /health | Liveness check | Non |
| GET    | /ready  | Readiness check | Non |
| POST   | /api/v1/auth/register | Créer un compte | Non |
| POST   | /api/v1/auth/login    | Se connecter | Non |
| POST   | /api/v1/auth/refresh  | Rafraîchir les tokens | Non |
| GET    | /api/v1/auth/me       | Mon profil | Oui |

---

## Services UI

| Service | URL | Credentials |
|---------|-----|-------------|
| API Docs (Swagger) | http://localhost:8000/docs | — |
| RabbitMQ Management | http://localhost:15672 | atlas / atlas |
| Neo4j Browser | http://localhost:7474 | neo4j / atlas_neo4j |

---

## Architecture

```
atlas/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers, middleware, exception handlers
│   │   │   └── v1/
│   │   │       └── endpoints/
│   │   ├── core/             # Config, logging, security, exceptions
│   │   ├── db/               # SQLAlchemy engine, session, migrations
│   │   ├── models/           # SQLAlchemy models (PostgreSQL)
│   │   ├── schemas/          # Pydantic v2 schemas
│   │   ├── services/         # Business logic
│   │   ├── repositories/     # Data access layer
│   │   ├── engines/          # Future: Discovery, Event, Opportunity engines
│   │   ├── workers/          # Future: Celery workers
│   │   ├── collectors/       # Future: SEC, FDA, News collectors
│   │   ├── graph/            # Future: Neo4j graph operations
│   │   └── ai/               # Future: AI analysis
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── alembic.ini
├── docker/
│   └── postgres/init.sql
├── docker-compose.yml
├── .env.example
├── .github/workflows/ci.yml
└── .pre-commit-config.yaml
```

---

## Linting

```bash
cd backend

# Vérifier
ruff check .
black --check .

# Corriger automatiquement
ruff check . --fix
black .
```

---

## Variables d'environnement importantes

| Variable | Description | Default |
|----------|-------------|---------|
| `JWT_SECRET_KEY` | Clé secrète JWT — **changer en production** | CHANGE_THIS... |
| `ENVIRONMENT` | `development`, `staging`, `production` | development |
| `FEATURE_NEO4J_ENABLED` | Active/désactive Neo4j (utile en CI) | true |
| `FEATURE_RABBITMQ_ENABLED` | Active/désactive RabbitMQ | true |

---

## Dépannage (Troubleshooting)

**`docker compose up -d` échoue ou un service ne démarre pas**
Vérifiez qu'aucun autre service local n'occupe déjà les ports utilisés
(5432 PostgreSQL, 6379 Redis, 5672/15672 RabbitMQ, 7474/7687 Neo4j, 8000
backend). `docker compose ps` montre l'état de chaque service ;
`docker compose logs <service>` affiche ses logs.

**`alembic upgrade head` échoue avec une erreur de connexion**
Le backend a probablement démarré avant que PostgreSQL soit prêt à
accepter des connexions. Réessayez après quelques secondes, ou vérifiez
`docker compose logs postgres`.

**`GET /health` répond mais `GET /ready` échoue**
`/ready` vérifie chaque service dépendant individuellement (PostgreSQL,
Redis, RabbitMQ, Neo4j). Le corps de la réponse indique lequel n'est pas
prêt. Si Neo4j ou RabbitMQ ne sont pas nécessaires pour votre usage, ils
peuvent être désactivés via `FEATURE_NEO4J_ENABLED=false` /
`FEATURE_RABBITMQ_ENABLED=false` dans `.env`.

**Le script `seed_demo.py` échoue avec une erreur Pydantic/settings**
Le script charge la même configuration que l'application (`.env`). Assurez-vous
que `.env` existe à la racine (copié depuis `.env.example`) et que les
variables `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_USER` /
`POSTGRES_PASSWORD` / `POSTGRES_DB` pointent vers une base accessible et
déjà migrée (`alembic upgrade head` doit avoir tourné avant le seed).

**Le seed tourne mais le Dashboard du frontend est toujours vide**
Vérifiez que `NEXT_PUBLIC_API_URL` (frontend) pointe bien vers ce backend
(`http://localhost:8000` par défaut), puis que
`curl http://localhost:8000/api/v1/companies` renvoie bien des résultats.
Si l'API répond mais que le frontend reste vide, videz le cache Next.js
(`rm -rf .next` côté frontend) et relancez `npm run dev`.

**Les tests unitaires échouent sur `test_core.py` (EmailStr) ou
`test_discovery.py` (YCombinator batch year)**
Ces deux tests dépendent des versions installées de `pydantic` /
`email-validator`. Si votre environnement diffère de celui figé par le
projet (`pyproject.toml`), réinstallez avec
`pip install -e ".[dev]" --force-reinstall` pour aligner les versions.
Ces deux cas n'affectent pas le reste de la suite ni le fonctionnement
de l'application.

**Le port 8000 est déjà utilisé**
Changez le port exposé dans `docker-compose.yml` (`ports: - "8001:8000"`
par exemple), et mettez à jour `NEXT_PUBLIC_API_URL` côté frontend en
conséquence.

---

## État des modules

Livrés :

- **Module 01** — Foundation (Auth, infra, patterns de base)
- **Module 02** — Company Engine (CRUD entreprises, recherche, pagination)
- **Module 03** — Theme Engine (thèmes d'investissement, relation M2M)
- **Module 04** — Discovery Engine (collecteurs SEC, GitHub, YCombinator, Crunchbase)
- **Module 05** — Event Engine (signaux détectés, scoring de base par event)
- **Module 06** — Opportunity Engine (score explicable 0-100, voir `docs/MODULE_06_OPPORTUNITY_ENGINE.md`)
- **Module 07** — Knowledge Graph (relations entre entités, traversée BFS multi-niveaux, prêt pour une future migration Neo4j via le pattern Strategy)

Le frontend (Next.js 15) vit désormais dans un repository séparé,
`atlas-frontend` — voir son propre README pour le développement de
l'interface.

À venir :

- **Stories Engine** (narration automatique des opportunités)
- Analyse IA réelle, alertes, watchlist persistée, notifications

