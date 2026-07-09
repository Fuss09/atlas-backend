# ATLAS TECHNICAL ARCHITECTURE

Version : 1.0

---

# Vision

Atlas est construit comme une plateforme modulaire.

Chaque moteur est indépendant.

Ils communiquent uniquement via des événements.

Aucun moteur ne dépend directement d'un autre.

Cela permet :

- Scalabilité
- Tests
- Maintenance
- Évolutions

---

# Architecture globale

                    Frontend (Next.js)
                           │
                     REST / WebSocket
                           │
                    API Gateway (FastAPI)
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
 Discovery          Recommendation       User Service
   Engine               Engine
        │                  │
        └──────────────┬───┘
                       ▼
               Intelligence Engine
                       │
               Opportunity Engine
                       │
                 Stories Engine
                       │
                 Knowledge Graph
                       │
                 Event Engine
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
 SEC Collector    FDA Collector   News Collector
        ▼              ▼              ▼
                 RabbitMQ Queue
                       ▼
                  Worker Pool

---

# Backend

Framework

FastAPI

Pourquoi ?

- rapide
- moderne
- async
- documentation automatique
- excellent avec Python IA

---

# Frontend

Framework

Next.js

Pourquoi ?

SEO

Performance

React

Très grande communauté

---

# Base de données

PostgreSQL

Stocke :

Utilisateurs

Entreprises

Scores

Alertes

Events

Watchlists

Historique

---

# Graphe

Neo4j

Stocke :

Relations

Thèmes

Technologies

Entreprises

Knowledge Graph

---

# Cache

Redis

Utilisé pour :

Cache API

Sessions

Jobs

Scores récents

---

# Queue

RabbitMQ

Chaque collecteur envoie des événements.

Les workers les traitent.

---

# IA

OpenAI

+

Modèles open-source à terme.

L'IA ne prend jamais les décisions.

Elle enrichit uniquement les données.

---

# Recherche

OpenSearch

Permet de rechercher :

Entreprises

Stories

Technologies

Brevets

Evénements

---

# Stockage

S3

Documents

Rapports

Images

Pièces jointes

---

# Monitoring

Prometheus

Grafana

Sentry

---

# Authentification

JWT

OAuth Google

OAuth GitHub

---

# Déploiement

Docker

Docker Compose

Puis Kubernetes à terme.

---

# Infrastructure

Cloud :

Railway (MVP)

Puis

AWS

ou

Hetzner

---

# Logging

Tous les événements sont loggés.

Aucune donnée critique ne disparaît.

---

# Tests

Unitaires

Intégration

End-to-End

---

# CI/CD

GitHub Actions

Lint

Tests

Build Docker

Déploiement

---

# Objectif

Une architecture capable d'évoluer pendant plusieurs années sans être reconstruite.
