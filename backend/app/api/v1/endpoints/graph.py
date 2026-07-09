"""
Atlas - Graph Endpoints
========================

GET  /graph/relations                           — liste filtrée
POST /graph/relations                           — créer/upsert (analyst+)
GET  /graph/relations/{id}                      — détail
PATCH /graph/relations/{id}                     — update (analyst+)
DELETE /graph/relations/{id}                    — soft delete (admin)
GET  /graph/stats                               — statistiques globales

GET  /companies/{id}/graph                      — graphe d'une entreprise
POST /companies/{id}/graph/relations            — ajouter une relation depuis une company
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, Pagination
from app.api.v1.endpoints.companies import require_admin, require_analyst
from app.models.graph import EntityType, RelationType
from app.schemas.graph import (
    CompanyGraphResponse,
    GraphStatsResponse,
    RelationCreate,
    RelationResponse,
    RelationUpdate,
)
from app.services.graph import GraphService

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])
companies_router = APIRouter(prefix="/companies", tags=["Companies"])


async def get_graph_service(db: DbSession) -> GraphService:
    return GraphService(db)


GraphServiceDep = Annotated[GraphService, Depends(get_graph_service)]


# ── Lecture ────────────────────────────────────────────────────────────────────

@router.get(
    "/relations",
    response_model=list[RelationResponse],
    summary="Lister les relations",
)
async def list_relations(
    graph_service: GraphServiceDep,
    entity_type: EntityType | None = Query(default=None),
    entity_id: UUID | None = Query(default=None),
    relation_type: RelationType | None = Query(default=None),
    direction: str = Query(default="both", pattern="^(in|out|both)$"),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
) -> list[RelationResponse]:
    if entity_type and entity_id:
        return await graph_service.get_entity_relations(
            entity_type, entity_id,
            direction=direction,
            relation_type=relation_type,
            min_confidence=min_confidence,
        )
    # Sans filtre : retourner vide (évite un full scan)
    return []


@router.get(
    "/stats",
    response_model=GraphStatsResponse,
    summary="Statistiques du graphe",
)
async def get_graph_stats(graph_service: GraphServiceDep) -> GraphStatsResponse:
    stats = await graph_service.get_stats()
    return GraphStatsResponse(
        total_relations=stats["total_relations"],
        by_type=stats["by_type"],
        by_source=stats["by_source"],
        most_connected_entities=[],
    )


@router.get(
    "/relations/{relation_id}",
    response_model=RelationResponse,
    summary="Détail d'une relation",
)
async def get_relation(
    relation_id: UUID,
    graph_service: GraphServiceDep,
) -> RelationResponse:
    r = await graph_service.get_by_id(relation_id)
    return RelationResponse.model_validate(r)


# ── Écriture ───────────────────────────────────────────────────────────────────

@router.post(
    "/relations",
    response_model=RelationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer ou mettre à jour une relation",
    description="Upsert idempotent. Si la relation existe déjà, met à jour weight et confidence.",
    dependencies=[Depends(require_analyst)],
)
async def create_relation(
    data: RelationCreate,
    graph_service: GraphServiceDep,
    current_user: CurrentUser,
) -> RelationResponse:
    return await graph_service.create_relation(data, created_by=current_user.id)


@router.patch(
    "/relations/{relation_id}",
    response_model=RelationResponse,
    summary="Mettre à jour une relation",
    dependencies=[Depends(require_analyst)],
)
async def update_relation(
    relation_id: UUID,
    data: RelationUpdate,
    graph_service: GraphServiceDep,
) -> RelationResponse:
    return await graph_service.update_relation(relation_id, data)


@router.delete(
    "/relations/{relation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une relation",
    dependencies=[Depends(require_admin)],
)
async def delete_relation(
    relation_id: UUID,
    graph_service: GraphServiceDep,
    current_user: CurrentUser,
) -> None:
    await graph_service.delete_relation(relation_id, deleted_by=current_user.id)


# ── Endpoints entreprise ───────────────────────────────────────────────────────

@companies_router.get(
    "/{company_id}/graph",
    response_model=CompanyGraphResponse,
    tags=["Companies"],
    summary="Graphe de relations d'une entreprise",
)
async def get_company_graph(
    company_id: UUID,
    graph_service: GraphServiceDep,
    depth: int = Query(default=1, ge=1, le=3),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
) -> CompanyGraphResponse:
    return await graph_service.get_company_graph(
        company_id, depth=depth, min_confidence=min_confidence
    )


@companies_router.post(
    "/{company_id}/graph/relations",
    response_model=RelationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Companies"],
    summary="Ajouter une relation depuis une entreprise",
    dependencies=[Depends(require_analyst)],
)
async def create_company_relation(
    company_id: UUID,
    data: RelationCreate,
    graph_service: GraphServiceDep,
    current_user: CurrentUser,
) -> RelationResponse:
    # Force source_type et source_id sur la company
    from app.models.graph import EntityType
    data.source_type = EntityType.COMPANY
    data.source_id = company_id
    return await graph_service.create_relation(data, created_by=current_user.id)
