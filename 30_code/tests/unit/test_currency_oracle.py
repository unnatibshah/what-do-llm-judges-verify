"""Unit tests for in_force() currency oracle and temporal evaluation."""

import json
from pathlib import Path

from suryabench.core.enums import (
    AuthorityRank,
    ConfidenceLevel,
    CurrencyVerdict,
    EdgeEvidenceType,
    EdgeRelation,
    EffectiveDateBasis,
    JurisdictionLevel,
    NodeStatus,
    StateCode,
)
from suryabench.corpus.schema import Jurisdiction
from suryabench.graph.oracle import in_force
from suryabench.graph.schema import Edge, EdgeEvidence, Node, SupersessionGraph

FIXTURE_GRAPH_PATH = (
    Path(__file__).parents[1] / "fixtures" / "corpus" / "graph" / "supersession.json"
)


def _load_fixture_graph() -> SupersessionGraph:
    with open(FIXTURE_GRAPH_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return SupersessionGraph.model_validate(data)


def test_currency_oracle_fixture_timeline() -> None:
    """Test in_force() across the timeline of the fixture documents:

    - Prior to 2019-12-30: MH-C3-001#cl-7.2 is NOT_YET_IN_FORCE
    - Between 2019-12-30 and 2024-02-28: MH-C3-001#cl-7.2 is IN_FORCE, MH-C3-002#cl-3 is NOT_YET_IN_FORCE
    - On/after 2024-03-01: MH-C3-001#cl-7.2 is SUPERSEDED, MH-C3-002#cl-3 is IN_FORCE
    """
    graph = _load_fixture_graph()

    # Query 1: 2018-01-01 (before base regulation)
    assert in_force("MH-C3-001#cl-7.2", "2018-01-01", graph) == CurrencyVerdict.NOT_YET_IN_FORCE

    # Query 2: 2021-06-01 (base regulation is live, amendment not yet enacted)
    assert in_force("MH-C3-001#cl-7.2", "2021-06-01", graph) == CurrencyVerdict.IN_FORCE
    assert in_force("MH-C3-002#cl-3", "2021-06-01", graph) == CurrencyVerdict.NOT_YET_IN_FORCE

    # Query 3: 2026-11-01 (amendment in force, base regulation superseded)
    assert in_force("MH-C3-001#cl-7.2", "2026-11-01", graph) == CurrencyVerdict.SUPERSEDED
    assert in_force("MH-C3-002#cl-3", "2026-11-01", graph) == CurrencyVerdict.IN_FORCE

    # Query 4: Central guideline
    assert in_force("IN-C1-001#cl-4.1", "2026-11-01", graph) == CurrencyVerdict.IN_FORCE


def test_currency_oracle_abstains_on_unknown_or_low_confidence() -> None:
    """Test protocol rule: in_force() returns UNDETERMINED if date or confidence is missing/low."""
    graph = SupersessionGraph()

    # Node with UNKNOWN effective date
    undated_node = Node(
        node_id="CIRCULAR#cl-1",
        doc_id="CIRCULAR",
        clause_ref="1",
        clause_text_snippet="Snippet",
        subject="net_metering_capacity_cap",
        jurisdiction=Jurisdiction(level=JurisdictionLevel.STATE, code=StateCode.MH),
        effective_date="UNKNOWN",
        effective_date_basis=EffectiveDateBasis.E9,
        effective_date_confidence=ConfidenceLevel.LOW,
        status_at_snapshot=NodeStatus.UNKNOWN,
        authority_rank=AuthorityRank.A5,
    )
    graph.add_node(undated_node)

    assert in_force("CIRCULAR#cl-1", "2026-11-01", graph) == CurrencyVerdict.UNDETERMINED

    # Unknown node
    assert in_force("NONEXISTENT#cl-9", "2026-11-01", graph) == CurrencyVerdict.UNDETERMINED


def test_currency_oracle_partial_amendment() -> None:
    """Test that amended_by relations return PARTIALLY_SUPERSEDED."""
    graph = SupersessionGraph()
    parent = Node(
        node_id="BASE#cl-2",
        doc_id="BASE",
        clause_ref="2",
        clause_text_snippet="Base clause",
        subject="net_metering_capacity_cap",
        jurisdiction=Jurisdiction(level=JurisdictionLevel.STATE, code=StateCode.RJ),
        effective_date="2020-01-01",
        effective_date_basis=EffectiveDateBasis.E1,
        effective_date_confidence=ConfidenceLevel.HIGH,
        status_at_snapshot=NodeStatus.PARTIALLY_SUPERSEDED,
        authority_rank=AuthorityRank.A1,
    )
    amendment = Node(
        node_id="AMEND#cl-1",
        doc_id="AMEND",
        clause_ref="1",
        clause_text_snippet="Amending clause",
        subject="net_metering_capacity_cap",
        jurisdiction=Jurisdiction(level=JurisdictionLevel.STATE, code=StateCode.RJ),
        effective_date="2023-01-01",
        effective_date_basis=EffectiveDateBasis.E1,
        effective_date_confidence=ConfidenceLevel.HIGH,
        status_at_snapshot=NodeStatus.IN_FORCE,
        authority_rank=AuthorityRank.A1,
    )
    edge = Edge(
        from_node="BASE#cl-2",
        to_node="AMEND#cl-1",
        relation=EdgeRelation.AMENDED_BY,
        from_date="2023-01-01",
        evidence=EdgeEvidence(
            type=EdgeEvidenceType.EXPLICIT,
            quote_text="Clause 2 is amended in part",
            doc_id="AMEND",
        ),
        confidence=ConfidenceLevel.HIGH,
    )
    graph.add_node(parent)
    graph.add_node(amendment)
    graph.add_edge(edge)

    assert in_force("BASE#cl-2", "2024-01-01", graph) == CurrencyVerdict.PARTIALLY_SUPERSEDED
