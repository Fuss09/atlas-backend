-- Atlas PostgreSQL Initialization
-- Ce script crée la base de données de test en plus de la base principale

-- La base principale (atlas) est créée automatiquement par POSTGRES_DB
-- On crée uniquement la base de test ici
CREATE DATABASE atlas_test
    WITH OWNER = atlas
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8';

-- Extensions utiles
\c atlas;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Recherche trigram (full-text search futur)
CREATE EXTENSION IF NOT EXISTS "btree_gin";  -- Index GIN pour les colonnes composites

\c atlas_test;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
