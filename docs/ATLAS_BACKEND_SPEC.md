# ATLAS BACKEND SPECIFICATION

Version : 1.0

---

# Stack

Language

Python 3.13

Framework

FastAPI

Validation

Pydantic v2

ORM

SQLAlchemy 2

Migration

Alembic

Authentication

JWT

OAuth Google

OAuth GitHub

Background Jobs

Celery

Broker

RabbitMQ

Cache

Redis

Database

PostgreSQL

Knowledge Graph

Neo4j

Object Storage

S3 Compatible

---

# Architecture

backend/

app/

api/

core/

models/

schemas/

services/

repositories/

engines/

workers/

collectors/

graph/

ai/

tests/

---

# Core Engines

Discovery Engine

Responsable de découvrir automatiquement les entreprises.

---

Event Engine

Normalise les données provenant des collecteurs.

---

Knowledge Engine

Met à jour Neo4j.

---

Intelligence Engine

Analyse les événements avec l'IA.

---

Opportunity Engine

Calcule les opportunités.

---

Recommendation Engine

Produit les recommandations finales.

---

Stories Engine

Construit automatiquement les Stories.

---

Alert Engine

Envoie les notifications.

---

# Services

CompanyService

EventService

StoryService

ThemeService

TechnologyService

RecommendationService

ScoreService

GraphService

AlertService

UserService

SearchService

---

# Repository Pattern

Chaque modèle possède :

Repository

Service

Schema

API

Exemple

CompanyRepository

↓

CompanyService

↓

CompanyAPI

---

# API Versioning

/api/v1/

Toutes les futures versions resteront compatibles.

---

# Documentation

Swagger automatique

OpenAPI

---

# Logs

Chaque requête possède

request_id

user_id

execution_time

status

---

# Error Handling

Jamais de trace Python envoyée au frontend.

Toujours un message normalisé.

---

# Pagination

Toutes les listes sont paginées.

---

# Recherche

Toutes les recherches passent par OpenSearch.

Jamais directement PostgreSQL.

---

# Tests

Minimum

80%

de couverture.

---

# Docker

Chaque service possède son propre Dockerfile.

---

# Convention

Tout le code est documenté.

Typé.

Testé.
