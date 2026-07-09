"""
Atlas - Graph Relation Repository
====================================
Accès PostgreSQL aux relations du graphe.
"""

import uuid

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import EntityType, GraphRelation, RelationType
from app.repositories.base import BaseRepository


class GraphRelationRepository(BaseRepository[GraphRelation]):

    model = GraphRelation

    # ── Upsert (cœur du graphe) ────────────────────────────────────────────────

    async def upsert(
        self,
        source_type: EntityType,
        source_id: uuid.UUID,
        target_type: EntityType,
        target_id: uuid.UUID,
        relation_type: RelationType,
        weight: float = 1.0,
        confidence_score: float = 1.0,
        relation_source: str = "manual",
        is_inferred: bool = False,
        source_label: str | None = None,
        target_label: str | None = None,
    ) -> GraphRelation:
        """
        Crée ou met à jour une relation.
        Si la relation existe (même source/target/type), met à jour weight et confidence.
        Idempotent — safe à appeler plusieurs fois.
        """
        # Tentative de récupération
        existing = await self._find_exact(
            source_type, source_id, target_type, target_id, relation_type
        )
        if existing:
            updated = await self.update(
                existing.id,
                weight=weight,
                confidence_score=confidence_score,
                source_label=source_label or existing.source_label,
                target_label=target_label or existing.target_label,
            )
            return updated or existing

        return await self.create(
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

    async def _find_exact(
        self,
        source_type: EntityType,
        source_id: uuid.UUID,
        target_type: EntityType,
        target_id: uuid.UUID,
        relation_type: RelationType,
    ) -> GraphRelation | None:
        result = await self.session.execute(
            select(GraphRelation).where(
                GraphRelation.source_type == source_type,
                GraphRelation.source_id == source_id,
                GraphRelation.target_type == target_type,
                GraphRelation.target_id == target_id,
                GraphRelation.relation_type == relation_type,
                GraphRelation.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    # ── Requêtes de traversée ──────────────────────────────────────────────────

    async def get_relations(
        self,
        entity_type: EntityType,
        entity_id: uuid.UUID,
        direction: str = "both",
        relation_type: RelationType | None = None,
        min_confidence: float = 0.0,
    ) -> list[GraphRelation]:
        """
        Récupère les relations d'un nœud.
        direction: "out" (sortantes), "in" (entrantes), "both"
        """
        base = and_(
            GraphRelation.is_deleted == False,  # noqa: E712
            GraphRelation.confidence_score >= min_confidence,
        )

        if direction == "out":
            cond = and_(
                GraphRelation.source_type == entity_type,
                GraphRelation.source_id == entity_id,
            )
        elif direction == "in":
            cond = and_(
                GraphRelation.target_type == entity_type,
                GraphRelation.target_id == entity_id,
            )
        else:
            cond = or_(
                and_(
                    GraphRelation.source_type == entity_type,
                    GraphRelation.source_id == entity_id,
                ),
                and_(
                    GraphRelation.target_type == entity_type,
                    GraphRelation.target_id == entity_id,
                ),
            )

        stmt = select(GraphRelation).where(base, cond)
        if relation_type:
            stmt = stmt.where(GraphRelation.relation_type == relation_type)

        stmt = stmt.order_by(
            GraphRelation.weight.desc(),
            GraphRelation.confidence_score.desc(),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_neighbors(
        self,
        entity_type: EntityType,
        entity_id: uuid.UUID,
        depth: int = 1,
    ) -> list[dict]:
        """
        BFS limité à `depth` niveaux via requêtes itératives.
        Pour depth > 2, Neo4j sera nettement plus performant.

        Chaque résultat porte via_entity_type/via_entity_id/via_relation_id :
        le nœud parent depuis lequel ce voisin a été découvert, et la
        relation empruntée. Sans cela, un appelant ne peut pas savoir
        *par où* un nœud de distance 2 ou 3 est rattaché au graphe — il
        ne pourrait dessiner qu'un éventail plat autour du centre, jamais
        une structure réellement connectée à plusieurs niveaux.
        """
        depth = min(depth, 3)  # Limite de sécurité sur PostgreSQL
        visited: set[tuple] = set()
        frontier: list[tuple[EntityType, uuid.UUID, int]] = [(entity_type, entity_id, 0)]
        results: list[dict] = []

        while frontier:
            current_type, current_id, current_depth = frontier.pop(0)
            if current_depth >= depth:
                continue
            key = (current_type, str(current_id))
            if key in visited:
                continue
            visited.add(key)

            relations = await self.get_relations(current_type, current_id, direction="both")
            for r in relations:
                # Déterminer le voisin
                if r.source_type == current_type and r.source_id == current_id:
                    neighbor_type, neighbor_id, neighbor_label = r.target_type, r.target_id, r.target_label
                else:
                    neighbor_type, neighbor_id, neighbor_label = r.source_type, r.source_id, r.source_label

                neighbor_key = (neighbor_type, str(neighbor_id))
                if neighbor_key not in visited:
                    results.append({
                        "entity_type": neighbor_type,
                        "entity_id": str(neighbor_id),
                        "entity_label": neighbor_label,
                        "relation_type": r.relation_type,
                        "weight": r.weight,
                        "distance": current_depth + 1,
                        "via_entity_type": current_type,
                        "via_entity_id": str(current_id),
                        "via_relation_id": str(r.id),
                    })
                    if current_depth + 1 < depth:
                        frontier.append((neighbor_type, neighbor_id, current_depth + 1))

        return results

    async def get_for_company(self, company_id: uuid.UUID) -> list[GraphRelation]:
        """Toutes les relations impliquant une entreprise (shortcut)."""
        return await self.get_relations(EntityType.COMPANY, company_id, direction="both")

    async def count_for_entity(
        self, entity_type: EntityType, entity_id: uuid.UUID
    ) -> int:
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count()).select_from(GraphRelation).where(
                or_(
                    and_(
                        GraphRelation.source_type == entity_type,
                        GraphRelation.source_id == entity_id,
                    ),
                    and_(
                        GraphRelation.target_type == entity_type,
                        GraphRelation.target_id == entity_id,
                    ),
                ),
                GraphRelation.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one()

    async def relation_exists(
        self,
        source_type: EntityType,
        source_id: uuid.UUID,
        target_type: EntityType,
        target_id: uuid.UUID,
        relation_type: RelationType,
    ) -> bool:
        r = await self._find_exact(source_type, source_id, target_type, target_id, relation_type)
        return r is not None
