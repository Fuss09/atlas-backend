"""
Atlas - Graph Schemas
=====================
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.graph import EntityType, RelationType


class RelationCreate(BaseModel):
    """Création manuelle d'une relation."""

    source_type: EntityType
    source_id: uuid.UUID
    target_type: EntityType
    target_id: uuid.UUID
    relation_type: RelationType
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    relation_source: str = Field(default="manual", max_length=50)
    is_inferred: bool = False
    source_label: str | None = Field(default=None, max_length=255)
    target_label: str | None = Field(default=None, max_length=255)

    @field_validator("target_id")
    @classmethod
    def no_self_loop(cls, v: uuid.UUID, info) -> uuid.UUID:
        if hasattr(info, "data") and "source_id" in info.data:
            if v == info.data["source_id"]:
                raise ValueError("A relation cannot point to itself")
        return v


class RelationResponse(BaseModel):
    """Représentation d'une relation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: EntityType
    source_id: uuid.UUID
    source_label: str | None
    target_type: EntityType
    target_id: uuid.UUID
    target_label: str | None
    relation_type: RelationType
    weight: float
    confidence_score: float
    relation_source: str
    is_inferred: bool
    created_at: datetime
    updated_at: datetime


class RelationUpdate(BaseModel):
    """Mise à jour partielle d'une relation."""

    weight: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    source_label: str | None = Field(default=None, max_length=255)
    target_label: str | None = Field(default=None, max_length=255)


class NeighborResponse(BaseModel):
    """Un voisin dans le graphe (résultat de traversée)."""

    entity_type: EntityType
    entity_id: uuid.UUID
    entity_label: str | None
    relation_type: RelationType
    weight: float
    distance: int
    via_entity_type: EntityType
    via_entity_id: uuid.UUID
    via_relation_id: uuid.UUID


class CompanyGraphResponse(BaseModel):
    """Vue graphe d'une entreprise : relations + voisins."""

    company_id: uuid.UUID
    relations_count: int
    relations: list[RelationResponse]
    neighbors: list[NeighborResponse]


class GraphStatsResponse(BaseModel):
    """Statistiques globales du graphe."""

    total_relations: int
    by_type: dict[str, int]
    by_source: dict[str, int]
    most_connected_entities: list[dict]
