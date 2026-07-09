# ATLAS DATA MODEL

Version : 1.0

---

# Introduction

Le modèle de données d'Atlas représente tout ce que le moteur connaît.

Le principe est simple :

Tout est une entité.

Toutes les entités sont reliées.

Toutes les relations sont exploitables par l'IA.

---

# Company

Représente une entreprise cotée ou privée.

## Attributs

- id
- name
- ticker
- exchange
- isin
- sector
- industry
- country
- founded_year
- market_cap
- employees
- website
- description

## Relations

- Technologies
- Themes
- Events
- Scores
- Relationships
- Patents
- Financial Reports
- Insider Trades
- Alerts

---

# Theme

Exemple :

Artificial Intelligence

Quantum Computing

Defense

Healthcare

Robotics

Cloud

Cybersecurity

## Attributs

- id
- name
- description
- maturity
- growth_score

---

# Technology

Exemple :

GPU

HBM

Cryogenics

Photonics

LLM

Inference

Fusion

## Attributs

- id
- name
- category
- description

---

# Event

Chaque information détectée devient un Event.

## Types

- Earnings
- SEC Filing
- Form 4
- FDA
- Patent
- Acquisition
- Partnership
- Hiring
- Layoff
- Grant
- Funding
- Conference
- GitHub Release
- Government Contract
- Regulation

## Attributs

- id
- title
- summary
- source
- published_at
- importance
- confidence
- sentiment

---

# Score

Chaque entreprise possède plusieurs scores.

## Types

- Conviction
- Momentum
- Innovation
- Financial
- Risk
- Sentiment

## Attributs

- value
- explanation
- updated_at

---

# Alert

Une notification envoyée à l'utilisateur.

## Attributs

- id
- title
- description
- priority
- created_at
- status

---

# Investment Thesis

Le cœur d'Atlas.

Exemple :

"Les Data Centers vont exploser."

## Attributs

- id
- title
- description
- owner
- created_at

## Relations

- Themes
- Companies
- Events
- Alerts

---

# Relationship

Décrit un lien entre deux entités.

Exemple

NVIDIA

↓

SUPPLIES

↓

Microsoft

Attributs

- id
- source
- target
- relation_type
- confidence
- created_at

---

# Patent

## Attributs

- number
- title
- applicant
- date
- technology

---

# Clinical Trial

## Attributs

- phase
- indication
- sponsor
- status

---

# Financial Report

## Attributs

- revenue
- eps
- guidance
- gross_margin
- operating_margin

---

# Insider Trade

## Attributs

- executive
- transaction
- shares
- amount
- filing_date

---

# User

## Attributs

- id
- email
- name

Relations

- Watchlists
- Investment Thesis
- Alerts

---

# Watchlist

Même si Atlas est centré sur les thèses, l'utilisateur pourra toujours créer une watchlist classique.

---

# Source

Toutes les données possèdent une source.

Exemple

SEC

FDA

GitHub

Yahoo Finance

Polygon

Finnhub

Alpha Vantage

Company Website

Chaque donnée doit rester traçable.

---

# Historique

Atlas ne remplace jamais une donnée.

Chaque modification crée un historique.

Cela permettra :

- d'entraîner le Machine Learning
- de rejouer une journée
- de comparer les évolutions
- d'analyser les performances

---

# Objectif

Toutes les données doivent pouvoir répondre à trois questions :

Que sait Atlas ?

Pourquoi le sait-il ?

Depuis quand le sait-il ?

---

# Decisions

- Toutes les entités possèdent un identifiant unique.
- Les relations sont des objets à part entière.
- L'historique est conservé.
- Les scores sont explicables.

---

# TODO

- Définir le schéma PostgreSQL.
- Définir les index.
- Définir Redis.
- Définir le cache.
