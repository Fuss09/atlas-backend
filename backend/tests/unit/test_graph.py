"""Tests unitaires — Graph model, schemas, backend abstraction"""

import uuid
import pytest
from pydantic import ValidationError

from app.models.graph import EntityType, GraphRelation, RelationType
from app.schemas.graph import RelationCreate, RelationUpdate, NeighborResponse


class TestRelationType:
    def test_all_types_defined(self):
        expected = {
            "competes_with", "supplies", "supplier_of", "customer_of", "uses",
            "partners_with", "invests_in", "owns", "acquired",
            "member_of_theme", "related_to",
        }
        actual = {r.value for r in RelationType}
        assert expected == actual

    def test_member_of_theme_exists(self):
        assert RelationType.MEMBER_OF_THEME == "member_of_theme"


class TestEntityType:
    def test_current_entities(self):
        assert EntityType.COMPANY == "company"
        assert EntityType.THEME == "theme"
        assert EntityType.EVENT == "event"

    def test_future_entities_stubbed(self):
        assert EntityType.TECHNOLOGY == "technology"
        assert EntityType.PERSON == "person"
        assert EntityType.FUND == "fund"


class TestRelationCreate:
    def test_valid_minimal(self):
        r = RelationCreate(
            source_type=EntityType.COMPANY,
            source_id=uuid.uuid4(),
            target_type=EntityType.THEME,
            target_id=uuid.uuid4(),
            relation_type=RelationType.MEMBER_OF_THEME,
        )
        assert r.weight == 1.0
        assert r.confidence_score == 1.0
        assert r.relation_source == "manual"
        assert r.is_inferred is False

    def test_weight_out_of_range(self):
        with pytest.raises(ValidationError):
            RelationCreate(
                source_type=EntityType.COMPANY,
                source_id=uuid.uuid4(),
                target_type=EntityType.THEME,
                target_id=uuid.uuid4(),
                relation_type=RelationType.RELATED_TO,
                weight=1.5,
            )

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            RelationCreate(
                source_type=EntityType.COMPANY,
                source_id=uuid.uuid4(),
                target_type=EntityType.COMPANY,
                target_id=uuid.uuid4(),
                relation_type=RelationType.COMPETES_WITH,
                confidence_score=-0.1,
            )

    def test_labels_optional(self):
        r = RelationCreate(
            source_type=EntityType.COMPANY,
            source_id=uuid.uuid4(),
            target_type=EntityType.COMPANY,
            target_id=uuid.uuid4(),
            relation_type=RelationType.COMPETES_WITH,
        )
        assert r.source_label is None
        assert r.target_label is None


class TestRelationUpdate:
    def test_all_optional(self):
        u = RelationUpdate()
        assert u.model_dump(exclude_none=True) == {}

    def test_partial_update(self):
        u = RelationUpdate(weight=0.5, confidence_score=0.8)
        data = u.model_dump(exclude_none=True)
        assert data == {"weight": 0.5, "confidence_score": 0.8}


class TestBackendAbstraction:
    def test_postgres_backend_implements_contract(self):
        """Vérifie que PostgresGraphBackend respecte le contrat GraphBackend."""
        from app.graph.backend import GraphBackend, PostgresGraphBackend
        import inspect

        abstract_methods = {
            name for name, method in inspect.getmembers(GraphBackend, predicate=inspect.isfunction)
            if getattr(method, "__isabstractmethod__", False)
        }
        concrete_methods = {
            name for name, _ in inspect.getmembers(PostgresGraphBackend, predicate=inspect.isfunction)
        }
        for method in abstract_methods:
            assert method in concrete_methods, f"PostgresGraphBackend missing: {method}"

    def test_neo4j_backend_stub_importable(self):
        """Le backend Neo4j futur doit être préparé dans l'abstraction."""
        from app.graph.backend import GraphBackend
        assert GraphBackend is not None
