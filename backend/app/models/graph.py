"""
Atlas - GraphRelation Model
============================
Modèle de relations entre entités Atlas.

Architecture :
    PostgreSQL (maintenant) → Neo4j (futur)

L'API publique ne change pas lors de la migration.
Le GraphBackend abstrait masque l'implémentation sous-jacente.

Entités source/cible supportées :
    company, theme, event, technology (*), person (*), product (*),
    country (*), fund (*)   (* = futurs modules)

Types de relations :
    SUPPLIES, USES, COMPETES_WITH, PARTNERS_WITH, INVESTS_IN,
    ACQUIRED, MEMBER_OF_THEME, RELATED_TO, OWNS,
    CUSTOMER_OF, SUPPLIER_OF

Décisions de conception :
- source_type + source_id (UUID) au lieu d'une FK directe :
  permet de relier des entités de types différents sans explosion de colonnes FK.
  Cohérent avec le modèle de graphe (nœuds typés).
- weight [0,1] : force de la relation (pour le futur ranking et propagation de score)
- confidence_score [0,1] : certitude de la relation (auto-détectée vs humaine)
- is_inferred : distingue les relations créées par un humain vs déduites par un algorithme
- Soft delete : conserver l'historique des relations passées (ex: une acquisition défaite)
- UniqueConstraint sur (source_type, source_id, target_type, target_id, relation_type) :
  pas deux fois la même relation entre les mêmes entités
"""

import uuid
from enum import StrEnum

from sqlalchemy import Float, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AtlasBase


class RelationType(StrEnum):
    """Types de relations dans le graphe Atlas."""

    # ── Compétition & Marché ──────────────────────────────────────────────────
    COMPETES_WITH = "competes_with"       # A est en concurrence directe avec B
    SUPPLIES = "supplies"                  # A fournit des composants/services à B
    SUPPLIER_OF = "supplier_of"           # Alias sémantique de SUPPLIES (inverse)
    CUSTOMER_OF = "customer_of"           # A est client de B
    USES = "uses"                          # A utilise la technologie/service B

    # ── Partenariats & Capital ────────────────────────────────────────────────
    PARTNERS_WITH = "partners_with"        # Partenariat stratégique A ↔ B
    INVESTS_IN = "invests_in"              # A investit dans B
    OWNS = "owns"                          # A détient/possède B
    ACQUIRED = "acquired"                  # A a acquis B

    # ── Appartenance ──────────────────────────────────────────────────────────
    MEMBER_OF_THEME = "member_of_theme"    # Company appartient à un Theme
    RELATED_TO = "related_to"              # Relation générique / non catégorisée


class EntityType(StrEnum):
    """Types d'entités qui peuvent être nœuds du graphe."""

    COMPANY = "company"
    THEME = "theme"
    EVENT = "event"
    # ── Futurs modules ─────────────────────────────────────────────────────────
    TECHNOLOGY = "technology"      # Module 08
    PERSON = "person"              # Module 09 (dirigeants, investisseurs)
    PRODUCT = "product"            # Module 10
    COUNTRY = "country"            # Module 11
    FUND = "fund"                  # Module 12 (fonds d'investissement)


class GraphRelation(AtlasBase):
    """
    Relation orientée entre deux entités du graphe Atlas.

    Modèle stocké en PostgreSQL, conçu pour migrer vers Neo4j.
    La couche GraphBackend (graph/backend.py) masque ce détail.

    Exemple :
        NVIDIA (company) --[SUPPLIES]--> Apple (company)
        poids=0.9, confiance=0.95, source=sec_filing
    """

    __tablename__ = "graph_relations"

    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "relation_type",
            name="uq_graph_relation",
        ),
    )

    # ── Nœud source ────────────────────────────────────────────────────────────

    source_type: Mapped[EntityType] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Type de l'entité source (company, theme, event…)",
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="UUID de l'entité source dans sa table respective",
    )
    source_label: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Label lisible de la source (dénormalisé pour affichage rapide)",
    )

    # ── Nœud cible ─────────────────────────────────────────────────────────────

    target_type: Mapped[EntityType] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Type de l'entité cible",
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="UUID de l'entité cible dans sa table respective",
    )
    target_label: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Label lisible de la cible (dénormalisé pour affichage rapide)",
    )

    # ── Relation ───────────────────────────────────────────────────────────────

    relation_type: Mapped[RelationType] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="Force de la relation [0.0 – 1.0]. Utilisée pour le ranking et la propagation.",
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="Certitude de la relation [0.0 – 1.0]. 1.0 = confirmée manuellement.",
    )

    # ── Provenance ─────────────────────────────────────────────────────────────

    relation_source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="manual",
        index=True,
        comment="Origine de la relation : manual, sec, github, ycombinator, opportunity_engine…",
    )
    is_inferred: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="True si la relation a été déduite algorithmiquement (vs saisie humaine)",
    )

    def __repr__(self) -> str:
        return (
            f"<GraphRelation {self.source_type}:{self.source_id}"
            f" --[{self.relation_type}]--> "
            f"{self.target_type}:{self.target_id}>"
        )
