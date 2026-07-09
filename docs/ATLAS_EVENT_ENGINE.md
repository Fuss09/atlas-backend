# ATLAS EVENT ENGINE

Version : 1.0

---

# Objectif

L'Event Engine est responsable de détecter, normaliser, enrichir et distribuer tous les événements utilisés par Atlas.

Il constitue le point d'entrée de toutes les informations.

Sans Event Engine, Atlas est aveugle.

---

# Vision

Internet produit des millions d'informations.

Atlas ne conserve que celles qui peuvent modifier une décision d'investissement.

Le rôle du moteur n'est donc pas de récupérer des news.

Le rôle est de transformer une information brute en événement exploitable.

---

# Pipeline

Internet

↓

Collecteurs

↓

Normalisation

↓

Déduplication

↓

Classification

↓

Enrichissement IA

↓

Knowledge Graph

↓

Scoring Engine

↓

Alertes

---

# Les Collecteurs

Chaque collecteur est indépendant.

Ils fonctionnent en parallèle.

Ils peuvent être ajoutés ou supprimés sans impacter les autres modules.

---

## SEC Collector

Sources :

- 8-K
- 10-K
- 10-Q
- Form 4
- Schedule 13D
- Schedule 13G

Détecte :

- achats d'initiés
- ventes d'initiés
- nouveaux risques
- acquisitions
- changements importants

---

## FDA Collector

Surveille :

- nouvelles approbations
- essais cliniques
- changements de phase
- refus
- Fast Track
- Breakthrough Therapy

---

## Patent Collector

Sources :

USPTO

Google Patents

European Patent Office

Détecte :

- nouveaux brevets
- nouveaux déposants
- technologies émergentes

---

## News Collector

Agrège :

- Reuters
- Bloomberg
- CNBC
- Financial Times
- Yahoo Finance
- MarketWatch

Chaque article reçoit un score de qualité.

---

## GitHub Collector

Surveille :

- nouveaux repositories
- releases
- stars
- forks
- commits
- activité

Très utile pour :

IA

Robotique

Open Source

Cybersécurité

---

## Hiring Collector

Détecte :

- hausse des recrutements

- nouveaux bureaux

- nouvelles équipes

- métiers recherchés

Une explosion des recrutements est souvent un signal précoce.

---

## Funding Collector

Détecte :

- levées de fonds

- investisseurs

- montants

- valorisations

Permet d'identifier les startups prometteuses.

---

## Government Collector

Surveille :

- contrats publics

- subventions

- appels d'offres

- lois

- réglementations

---

# Normalisation

Tous les événements deviennent une structure unique.

Exemple

Event

id

title

summary

source

company

theme

technology

importance

confidence

published_at

---

# Déduplication

Une même information peut provenir de 20 médias.

Atlas ne conserve qu'un seul événement.

Toutes les sources sont attachées à cet événement.

---

# Classification IA

Chaque événement est automatiquement classé.

Exemple :

Catégorie

- Earnings
- Patent
- Acquisition
- FDA
- Hiring
- Funding
- Partnership

Puis :

Impact :

Positif

Neutre

Négatif

Puis :

Niveau de confiance.

---

# Enrichissement

L'IA ajoute automatiquement :

Résumé

Entreprises concernées

Technologies

Secteurs

Catalyseurs

Risques

Questions à surveiller

---

# Knowledge Graph

Chaque événement met à jour le graphe.

Exemple

Microsoft investit dans une startup.

↓

Nouvelle relation.

↓

Score recalculé.

↓

Nouvelle recommandation.

---

# Historique

Jamais supprimer.

Jamais écraser.

Tous les événements restent disponibles.

Cela permettra :

Backtesting

Machine Learning

Recherche

Statistiques

---

# Priorité

Tous les événements possèdent une priorité.

P0

Impact immédiat.

P1

Très important.

P2

Important.

P3

Information utile.

P4

Archive.

---

# Fréquence

SEC

Toutes les 5 minutes

News

Toutes les 5 minutes

GitHub

Toutes les heures

FDA

Toutes les heures

Brevets

Toutes les 24 heures

Government

Toutes les heures

---

# Objectifs

Temps moyen de traitement

< 30 secondes

Disponibilité

99,9 %

Aucune perte d'événement

Historique complet

---

# Decisions

Chaque collecteur est indépendant.

Tous les événements sont historisés.

Toutes les données sont normalisées.

Aucune IA n'accède directement aux données brutes.

---

# TODO

Créer les workers.

Créer RabbitMQ.

Créer les files d'attente.

Créer les retries.

Créer le monitoring.

Créer les métriques.
