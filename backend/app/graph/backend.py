"""
Atlas - Graph Backend Abstraction
===================================
Couche d'abstraction permettant de migrer de PostgreSQL vers Neo4j
sans modifier l'API publique ni le service.

Pattern : Strategy
    GraphBackend (ABC)
        ├── PostgresGraphBackend   ← implémentation actuelle
        └── Neo4jGraphBackend      ← future implémentation (Module Neo4j)

Le GraphService utilise uniquement GraphBackend — jamais directement
PostgresGraphBackend ou Neo4jGraphBackend.

Migration vers Neo4j :
    1. Implémenter Neo4jGraphBackend
    2. Changer la factory get_graph_backend() dans config.py
    3. Zero changement dans GraphService, les endpoints, les tests d'intégration

Notes sur le modèle de données Neo4j (futur) :
    - Les entités (Company, Theme…) deviennent des nœuds avec label
    - GraphRelation devient une arête typée
    - weight et confidence_score deviennent des propriétés de l'arête
    - Les requêtes Cypher remplaceront les SELECT SQLAlchemy
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.models.graph import EntityType, GraphRelation, RelationType


class GraphBackend(ABC):
    """Contrat que toute implémentation de graphe doit respecter."""

    @abstractmethod
    async def upsert_relation(
        self,
        source_type: EntityType,
        source_id: UUID,
        target_type: EntityType,
        target_id: UUID,
        relation_type: RelationType,
        weight: float = 1.0,
        confidence_score: float = 1.0,
        relation_source: str = "manual",
        is_inferred: bool = False,
        source_label: str | None = None,
        target_label: str | None = None,
    ) -> GraphRelation:
        """Crée ou met à jour une relation. Idempotent."""
        ...

    @abstractmethod
    async def get_relations(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        direction: str = "both",          # "out", "in", "both"
        relation_type: RelationType | None = None,
        min_confidence: float = 0.0,
    ) -> list[GraphRelation]:
        """Retourne les relations d'un nœud."""
        ...

    @abstractmethod
    async def delete_relation(self, relation_id: UUID) -> bool:
        """Soft delete d'une relation."""
        ...

    @abstractmethod
    async def get_neighbors(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        depth: int = 1,
    ) -> list[dict]:
        """
        Retourne les voisins jusqu'à `depth` niveaux.
        Chaque dict : {entity_type, entity_id, entity_label, relation_type,
        weight, distance, via_entity_type, via_entity_id, via_relation_id}.
        via_* identifie le nœud parent et la relation empruntée pour
        atteindre ce voisin — indispensable pour reconstruire une
        structure de graphe réellement connectée au-delà de depth=1
        (sans cela, un appelant ne peut dessiner qu'un éventail plat
        autour du centre).
        """
        ...


class PostgresGraphBackend(GraphBackend):
    """
    Implémentation PostgreSQL du graphe.
    Utilise GraphRelationRepository pour toutes les opérations.
    """

    def __init__(self, repo: "GraphRelationRepository") -> None:  # type: ignore[name-defined]
        self._repo = repo

    async def upsert_relation(
        self,
        source_type: EntityType,
        source_id: UUID,
        target_type: EntityType,
        target_id: UUID,
        relation_type: RelationType,
        weight: float = 1.0,
        confidence_score: float = 1.0,
        relation_source: str = "manual",
        is_inferred: bool = False,
        source_label: str | None = None,
        target_label: str | None = None,
    ) -> GraphRelation:
        return await self._repo.upsert(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relation_type=relation_type,
            weight=weight,
            confidence_score=confidence_score,
            relation_source=relation_source,
            is_inferred=is_inferred,
            source_label=source_label,
            target_label=target_label,
        )

    async def get_relations(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        direction: str = "both",
        relation_type: RelationType | None = None,
        min_confidence: float = 0.0,
    ) -> list[GraphRelation]:
        return await self._repo.get_relations(
            entity_type=entity_type,
            entity_id=entity_id,
            direction=direction,
            relation_type=relation_type,
            min_confidence=min_confidence,
        )

    async def delete_relation(self, relation_id: UUID) -> bool:
        return await self._repo.soft_delete(relation_id)

    async def get_neighbors(
        self,
        entity_type: EntityType,
        entity_id: UUID,
        depth: int = 1,
    ) -> list[dict]:
        return await self._repo.get_neighbors(entity_type, entity_id, depth=depth)
