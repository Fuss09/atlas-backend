# MODULE 01 - FOUNDATION

Objectif

Construire une infrastructure professionnelle sur laquelle tous les futurs modules viendront s'appuyer.

---

## Livrables

Backend FastAPI

Docker

Docker Compose

PostgreSQL

Redis

RabbitMQ

Neo4j

Alembic

SQLAlchemy

Pydantic v2

JWT Authentication

Health Check

Swagger

OpenAPI

Logging

GitHub Actions

Pytest

Ruff

Black

Pre-commit

Configuration ENV

---

## Arborescence

backend/

app/

api/

core/

config/

db/

engines/

workers/

repositories/

services/

models/

schemas/

tests/

---

## Endpoints

GET /health

GET /ready

POST /auth/login

POST /auth/register

POST /auth/refresh

GET /me

---

## Docker

Tous les services doivent démarrer avec

docker compose up

sans configuration supplémentaire.

---

## Critères de validation

Le backend démarre.

Toutes les bases sont connectées.

Swagger fonctionne.

Les tests passent.

CI verte.

Documentation générée.
