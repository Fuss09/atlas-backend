"""
Atlas - Graph Service
======================
Orchestre les opérations sur le graphe via le backend abstrait.

Fonctionnalités :
- Création/suppression de relations (CRUD)
- Lecture des relations d'une entité
- Traversée du graphe (voisins, profondeur)
- Auto-liaison Company → Theme lors de l'association (hook)
- Statistiques du graphe

Extensibilité :
- Chaque module peut appeler create_relation() directement
- Le backend peut être switché vers Neo4j sans toucher ce service
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExistsError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.graph.backend import GraphBackend, PostgresGraphBackend
from app.models.graph import EntityType, GraphRelation, RelationType
from app.repositories.company import CompanyRepository
from app.repositories.graph import GraphRelationRepository
from app.schemas.graph import (
    CompanyGraphResponse,
    NeighborResponse,
    RelationCreate,
    RelationResponse,
    RelationUpdate,
)

logger = get_logger(__name__)


class GraphService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = GraphRelationRepository(session)
        self.backend: GraphBackend = PostgresGraphBackend(self.repo)
        self.company_repo = CompanyRepository(session)

    # ── Création / Upsert ──────────────────────────────────────────────────────

    async def create_relation(
        self,
        data: RelationCreate,
        created_by: uuid.UUID | None = None,
    ) -> RelationResponse:
        """
        Crée ou met à jour une relation dans le graphe.
        Idempotent : appeler deux fois avec les mêmes paramètres met à jour weight/confidence.
        """
        relation = await self.backend.upsert_relation(
            source_type=data.source_type,
            source_id=data.source_id,
            target_type=data.target_type,
            target_id=data.target_id,
            relation_type=data.relation_type,
            weight=data.weight,
            confidence_score=data.confidence_score,
            relation_source=data.relation_source,
            is_inferred=data.is_inferred,
            source_label=data.source_label,
            target_label=data.target_label,
        )
        logger.info(
            "Graph relation upserted",
            relation_type=data.relation_type,
            source=f"{data.source_type}:{data.source_id}",
            target=f"{data.target_type}:{data.target_id}",
            created_by=str(created_by) if created_by else "system",
        )
        return RelationResponse.model_validate(relation)

    async def link_company_to_theme(
        self,
        company_id: uuid.UUID,
        theme_id: uuid.UUID,
        company_name: str | None = None,
        theme_name: str | None = None,
        weight: float = 1.0,
        relation_source: str = "manual",
    ) -> RelationResponse:
        """
        Shortcut pour associer une Company à un Theme dans le graphe.
        Appelé automatiquement par ThemeService.add_company().
        """
        data = RelationCreate(
            source_type=EntityType.COMPANY,
            source_id=company_id,
            target_type=EntityType.THEME,
            target_id=theme_id,
            relation_type=RelationType.MEMBER_OF_THEME,
            weight=weight,
            confidence_score=1.0,
            relation_source=relation_source,
            is_inferred=False,
            source_label=company_name,
            target_label=theme_name,
        )
        return await self.create_relation(data)

    async def create_from_discovery(
        self,
        source_type: EntityType,
        source_id: uuid.UUID,
        target_type: EntityType,
        target_id: uuid.UUID,
        relation_type: RelationType,
        weight: float = 0.7,
        confidence_score: float = 0.7,
        relation_source: str = "discovery",
        source_label: str | None = None,
        target_label: str | None = None,
    ) -> RelationResponse | None:
        """
        Crée une relation inférée par un collecteur.
        Retourne None en cas d'erreur non critique (ne bloque pas le collecteur).
        """
        try:
            data = RelationCreate(
                source_type=source_type,
                source_id=source_id,
                target_type=target_type,
                target_id=target_id,
                relation_type=relation_type,
                weight=weight,
                confidence_score=confidence_score,
                relation_source=relation_source,
                is_inferred=True,
                source_label=source_label,
                target_label=target_label,
            )
            return await self.create_relation(data)
        except Exception as exc:
            logger.warning("Failed to create graph relation from discovery", error=str(exc))
            return None

    # ── Lecture ────────────────────────────────────────────────────────────────

    async def get_by_id(self, relation_id: uuid.UUID) -> GraphRelation:
        r = await self.repo.get_by_id(relation_id)
        if not r:
            raise NotFoundError("GraphRelation", relation_id)
        return r

    async def get_company_graph(
        self,
        company_id: uuid.UUID,
        depth: int = 1,
        min_confidence: float = 0.0,
    ) -> CompanyGraphResponse:
        """
        Retourne la vue graphe d'une entreprise :
        - ses relations directes
        - ses voisins jusqu'à `depth` niveaux
        """
        company = await self.company_repo.get_by_id(company_id)
        if not company:
            raise NotFoundError("Company", company_id)

        relations = await self.backend.get_relations(
            EntityType.COMPANY, company_id,
            direction="both",
            min_confidence=min_confidence,
        )
        neighbors_raw = await self.backend.get_neighbors(
            EntityType.COMPANY, company_id, depth=depth
        )

        return CompanyGraphResponse(
            company_id=company_id,
            relations_count=len(relations),
            relations=[RelationResponse.model_validate(r) for r in relations],
            neighbors=[NeighborResponse(**n) for n in neighbors_raw],
        )

    async def get_entity_relations(
        self,
        entity_type: EntityType,
        entity_id: uuid.UUID,
        direction: str = "both",
        relation_type: RelationType | None = None,
        min_confidence: float = 0.0,
    ) -> list[RelationResponse]:
        relations = await self.backend.get_relations(
            entity_type, entity_id,
            direction=direction,
            relation_type=relation_type,
            min_confidence=min_confidence,
        )
        return [RelationResponse.model_validate(r) for r in relations]

    # ── Mise à jour / Suppression ──────────────────────────────────────────────

    async def update_relation(
        self,
        relation_id: uuid.UUID,
        data: RelationUpdate,
    ) -> RelationResponse:
        await self.get_by_id(relation_id)
        updates = data.model_dump(exclude_none=True)
        if not updates:
            r = await self.get_by_id(relation_id)
            return RelationResponse.model_validate(r)
        updated = await self.repo.update(relation_id, **updates)
        if not updated:
            raise NotFoundError("GraphRelation", relation_id)
        return RelationResponse.model_validate(updated)

    async def delete_relation(
        self,
        relation_id: uuid.UUID,
        deleted_by: uuid.UUID | None = None,
    ) -> None:
        success = await self.backend.delete_relation(relation_id)
        if not success:
            raise NotFoundError("GraphRelation", relation_id)
        logger.info(
            "Graph relation deleted",
            relation_id=str(relation_id),
            deleted_by=str(deleted_by) if deleted_by else "system",
        )

    # ── Stats ──────────────────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        """Statistiques globales du graphe (approximatives, pas de COUNT *)."""
        from sqlalchemy import func, select
        from app.models.graph import GraphRelation

        async with self.session as _:
            pass  # session déjà active

        # Compter par type
        from sqlalchemy import func
        result = await self.session.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(
                GraphRelation.relation_type,
                func.count().label("cnt"),
            )
            .where(GraphRelation.is_deleted == False)  # noqa: E712
            .group_by(GraphRelation.relation_type)
        )
        by_type = {row.relation_type: row.cnt for row in result.all()}

        result2 = await self.session.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(
                GraphRelation.relation_source,
                func.count().label("cnt"),
            )
            .where(GraphRelation.is_deleted == False)  # noqa: E712
            .group_by(GraphRelation.relation_source)
        )
        by_source = {row.relation_source: row.cnt for row in result2.all()}

        return {
            "total_relations": sum(by_type.values()),
            "by_type": by_type,
            "by_source": by_source,
        }
