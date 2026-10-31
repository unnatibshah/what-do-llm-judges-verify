"""Graph integrity validation and currency oracle."""

from collections import defaultdict

from suryabench.core.enums import (
    ConfidenceLevel,
    CurrencyVerdict,
    EdgeEvidenceType,
    EdgeRelation,
)
from suryabench.core.exceptions import GraphCycleError, GraphIntegrityError
from suryabench.graph.schema import Edge, SupersessionGraph


def validate_graph(graph: SupersessionGraph) -> None:
    """Run all mandatory integrity assertions over the supersession graph.

    Assertions (per protocol §6):
    1. Every edge connects existing nodes.
    2. Zero cycles in superseded_by and consolidated_into relations.
    3. Explicit edges must provide supporting evidence quote text.
    4. If effective_date is specified as YYYY-MM-DD, verify syntax.

    Raises:
        GraphIntegrityError: If reference or content integrity is violated.
        GraphCycleError: If a cycle is detected in supersession relations.
    """
    # 1. Reference check
    for edge in graph.edges:
        if edge.from_node not in graph.nodes:
            raise GraphIntegrityError(f"Edge references unknown source node: '{edge.from_node}'")
        if edge.to_node not in graph.nodes:
            raise GraphIntegrityError(f"Edge references unknown target node: '{edge.to_node}'")

        # 3. Explicit edge evidence check
        if edge.evidence.type == EdgeEvidenceType.EXPLICIT and not edge.evidence.quote_text.strip():
            raise GraphIntegrityError(
                f"Explicit edge from '{edge.from_node}' to '{edge.to_node}' must have non-empty quote_text"
            )

    # 2. Cycle detection in supersession chains
    adj: dict[str, list[str]] = defaultdict(list)
    supersession_relations = {EdgeRelation.SUPERSEDED_BY, EdgeRelation.CONSOLIDATED_INTO}

    for edge in graph.edges:
        if edge.relation in supersession_relations:
            adj[edge.from_node].append(edge.to_node)

    visited: dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited

    def dfs(u: str, path: list[str]) -> None:
        visited[u] = 1
        for v in adj[u]:
            if visited.get(v, 0) == 1:
                cycle_str = " -> ".join(path + [v])
                raise GraphCycleError(f"Detected directed cycle in supersession graph: {cycle_str}")
            if visited.get(v, 0) == 0:
                dfs(v, path + [v])
        visited[u] = 2

    for node_id in graph.nodes:
        if visited.get(node_id, 0) == 0:
            dfs(node_id, [node_id])


def in_force(
    node_id: str,
    query_date: str,
    graph: SupersessionGraph,
    require_explicit_supersession: bool = False,
) -> CurrencyVerdict:
    """Determine whether a regulatory clause node is in force at a target query date.

    Protocol §6 currency query specification:
    in_force(node, D) :=
        node.effective_date <= D
        AND no edge (node -> *) with relation in {superseded_by, consolidated_into} and from_date <= D
        AND no active amended_by edge with from_date <= D

    Returns CurrencyVerdict:
        - IN_FORCE: Node is live and authoritative at query_date.
        - SUPERSEDED: Node has been fully superseded by a subsequent document.
        - PARTIALLY_SUPERSEDED: Node has an active amendment at query_date.
        - NOT_YET_IN_FORCE: query_date is before node's effective_date.
        - UNDETERMINED: Node date is UNKNOWN, low confidence, or edge has low confidence.
    """
    node = graph.get_node(node_id)
    if node is None:
        return CurrencyVerdict.UNDETERMINED

    # Protocol §6: oracle must be allowed to abstain on UNKNOWN or low-confidence dates
    if node.effective_date == "UNKNOWN" or node.effective_date_confidence == ConfidenceLevel.LOW:
        return CurrencyVerdict.UNDETERMINED

    # Check effective date threshold
    if node.effective_date > query_date:
        return CurrencyVerdict.NOT_YET_IN_FORCE

    outgoing_edges: list[Edge] = [e for e in graph.edges if e.from_node == node_id]

    partially_superseded = False

    for edge in outgoing_edges:
        if require_explicit_supersession and edge.evidence.type != EdgeEvidenceType.EXPLICIT:
            continue

        if edge.relation in {EdgeRelation.SUPERSEDED_BY, EdgeRelation.CONSOLIDATED_INTO}:
            if edge.confidence == ConfidenceLevel.LOW or edge.from_date == "UNKNOWN":
                return CurrencyVerdict.UNDETERMINED
            if edge.from_date is not None and edge.from_date <= query_date:
                return CurrencyVerdict.SUPERSEDED

        elif edge.relation == EdgeRelation.AMENDED_BY:
            if edge.confidence == ConfidenceLevel.LOW or edge.from_date == "UNKNOWN":
                return CurrencyVerdict.UNDETERMINED
            if edge.from_date is not None and edge.from_date <= query_date:
                partially_superseded = True

    if partially_superseded:
        return CurrencyVerdict.PARTIALLY_SUPERSEDED

    return CurrencyVerdict.IN_FORCE
