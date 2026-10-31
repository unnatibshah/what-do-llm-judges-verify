"""Unit tests for SupersessionGraph, Node, and Edge schema and integrity validation."""

import json
from pathlib import Path

import pytest

from suryabench.core.enums import (
    AuthorityRank,
    ConfidenceLevel,
    EdgeEvidenceType,
    EdgeRelation,
    EffectiveDateBasis,
    JurisdictionLevel,
    NodeStatus,
    StateCode,
)
from suryabench.core.exceptions import GraphCycleError, GraphIntegrityError
from suryabench.corpus.schema import Jurisdiction
from suryabench.graph.oracle import validate_graph
from suryabench.graph.schema import Edge, EdgeEvidence, Node, SupersessionGraph
from suryabench.paths import CORPUS_DIR

FIXTURE_GRAPH_PATH = (
    Path(__file__).parents[1] / "fixtures" / "corpus" / "graph" / "supersession.json"
)


def _create_dummy_node(node_id: str, effective_date: str = "2024-01-01") -> Node:
    doc_id = node_id.split("#")[0]
    return Node(
        node_id=node_id,
        doc_id=doc_id,
        clause_ref="1.0",
        clause_text_snippet="Test clause text",
        subject="net_metering_capacity_cap",
        jurisdiction=Jurisdiction(level=JurisdictionLevel.STATE, code=StateCode.MH),
        effective_date=effective_date,
        effective_date_basis=EffectiveDateBasis.E1,
        effective_date_confidence=ConfidenceLevel.HIGH,
        status_at_snapshot=NodeStatus.IN_FORCE,
        authority_rank=AuthorityRank.A1,
    )


def test_load_fixture_graph() -> None:
    """Test loading and validating the fixture supersession graph."""
    with open(FIXTURE_GRAPH_PATH, encoding="utf-8") as f:
        data = json.load(f)

    graph = SupersessionGraph.model_validate(data)
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 1
    validate_graph(graph)


def test_load_live_corpus_graph() -> None:
    """Test loading and validating the live corpus supersession graph if it exists."""
    live_graph_path = CORPUS_DIR / "graph" / "supersession.json"
    if not live_graph_path.exists():
        pytest.skip("Live corpus graph not yet populated")

    with open(live_graph_path, encoding="utf-8") as f:
        data = json.load(f)

    graph = SupersessionGraph.model_validate(data)
    assert len(graph.nodes) >= 10
    assert len(graph.edges) >= 5
    validate_graph(graph)


def test_node_id_format_validation() -> None:
    """Test that malformed node IDs without '#' are rejected."""
    with pytest.raises(ValueError, match="must contain '#' delimiter"):
        Node(
            node_id="INVALID_NODE_ID",
            doc_id="MH-C3-001",
            clause_ref="7.2",
            clause_text_snippet="Snippet",
            subject="net_metering_capacity_cap",
            jurisdiction=Jurisdiction(level=JurisdictionLevel.STATE, code=StateCode.MH),
            effective_date="2020-01-01",
            effective_date_basis=EffectiveDateBasis.E1,
            effective_date_confidence=ConfidenceLevel.HIGH,
            status_at_snapshot=NodeStatus.IN_FORCE,
            authority_rank=AuthorityRank.A1,
        )


def test_edge_references_missing_node() -> None:
    """Test that an edge referencing a non-existent node raises GraphIntegrityError."""
    graph = SupersessionGraph()
    n1 = _create_dummy_node("DOC1#cl-1")
    graph.add_node(n1)

    edge = Edge(
        from_node="DOC1#cl-1",
        to_node="NON_EXISTENT#cl-2",
        relation=EdgeRelation.SUPERSEDED_BY,
        evidence=EdgeEvidence(
            type=EdgeEvidenceType.EXPLICIT,
            quote_text="Clause 1 is superseded",
            doc_id="NON_EXISTENT",
        ),
        confidence=ConfidenceLevel.HIGH,
    )
    graph.add_edge(edge)

    with pytest.raises(GraphIntegrityError, match="unknown target node"):
        validate_graph(graph)


def test_explicit_edge_requires_quote_text() -> None:
    """Test that an explicit edge with empty quote text is rejected."""
    graph = SupersessionGraph()
    n1 = _create_dummy_node("DOC1#cl-1")
    n2 = _create_dummy_node("DOC2#cl-1")
    graph.add_node(n1)
    graph.add_node(n2)

    edge = Edge(
        from_node="DOC1#cl-1",
        to_node="DOC2#cl-1",
        relation=EdgeRelation.SUPERSEDED_BY,
        evidence=EdgeEvidence(
            type=EdgeEvidenceType.EXPLICIT,
            quote_text="   ",  # whitespace only
            doc_id="DOC2",
        ),
        confidence=ConfidenceLevel.HIGH,
    )
    graph.add_edge(edge)

    with pytest.raises(GraphIntegrityError, match="must have non-empty quote_text"):
        validate_graph(graph)


def test_supersession_cycle_detection() -> None:
    """Test that circular supersession chains (A -> B -> C -> A) trigger GraphCycleError."""
    graph = SupersessionGraph()
    n1 = _create_dummy_node("A#cl-1")
    n2 = _create_dummy_node("B#cl-1")
    n3 = _create_dummy_node("C#cl-1")
    for n in (n1, n2, n3):
        graph.add_node(n)

    # Add cycle A -> B -> C -> A
    edges = [
        Edge(
            from_node="A#cl-1",
            to_node="B#cl-1",
            relation=EdgeRelation.SUPERSEDED_BY,
            evidence=EdgeEvidence(
                type=EdgeEvidenceType.EXPLICIT, quote_text="A replaced by B", doc_id="B"
            ),
            confidence=ConfidenceLevel.HIGH,
        ),
        Edge(
            from_node="B#cl-1",
            to_node="C#cl-1",
            relation=EdgeRelation.SUPERSEDED_BY,
            evidence=EdgeEvidence(
                type=EdgeEvidenceType.EXPLICIT, quote_text="B replaced by C", doc_id="C"
            ),
            confidence=ConfidenceLevel.HIGH,
        ),
        Edge(
            from_node="C#cl-1",
            to_node="A#cl-1",
            relation=EdgeRelation.SUPERSEDED_BY,
            evidence=EdgeEvidence(
                type=EdgeEvidenceType.EXPLICIT, quote_text="C replaced by A", doc_id="A"
            ),
            confidence=ConfidenceLevel.HIGH,
        ),
    ]
    for e in edges:
        graph.add_edge(e)

    with pytest.raises(GraphCycleError, match="Detected directed cycle"):
        validate_graph(graph)
