"""Supersession graph schema: clause nodes, directed edges, and graph container."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from suryabench.core.enums import (
    AuthorityRank,
    ConfidenceLevel,
    EdgeEvidenceType,
    EdgeRelation,
    EffectiveDateBasis,
    NodeStatus,
    SubjectTag,
)
from suryabench.corpus.schema import Jurisdiction


class Node(BaseModel):
    """Clause-level regulatory node."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    node_id: str = Field(..., description="Unique clause identifier, e.g. MH-C3-004#cl-7.2")
    doc_id: str = Field(..., description="Parent document identifier, e.g. MH-C3-004")
    clause_ref: str = Field(..., description="Clause or section reference number, e.g. 7.2")
    clause_text_snippet: str = Field(..., description="Verbatim text snippet of the clause")
    subject: SubjectTag | str = Field(..., description="Controlled subject vocabulary tag")
    jurisdiction: Jurisdiction
    effective_date: str = Field(..., description="Derived effective date (YYYY-MM-DD) or 'UNKNOWN'")
    effective_date_basis: EffectiveDateBasis = Field(..., description="Derivation rule E1–E9")
    effective_date_confidence: ConfidenceLevel = Field(
        ..., description="Confidence high/medium/low"
    )
    status_at_snapshot: NodeStatus = Field(..., description="Status at benchmark snapshot date")
    authority_rank: AuthorityRank = Field(
        ..., description="Conflict-resolution hierarchy rank A1–A6"
    )
    # Corpus r3 staging fields (None for every r2 node).
    verification_status: str | None = Field(None, description="UNVERIFIED until checked by a human")
    legal_status: str | None = Field(
        None, description="e.g. draft_not_in_force, quoted_predecessor; None when ordinary"
    )
    quote_check: str | None = Field(
        None, description="How the snippet was matched to the corpus text (exact, loose, not_found)"
    )

    @field_validator("node_id")
    @classmethod
    def validate_node_id_format(cls, v: str) -> str:
        """Assert node_id follows <doc_id>#cl-<clause_ref> syntax."""
        if "#" not in v:
            raise ValueError(
                f"Invalid node_id format '{v}': must contain '#' delimiter, e.g. 'DOC#cl-1'"
            )
        return v


class EdgeEvidence(BaseModel):
    """Evidence provenance supporting a graph edge."""

    model_config = ConfigDict(extra="forbid")

    type: EdgeEvidenceType = Field(..., description="explicit, implicit, or inferred")
    quote_text: str = Field(
        ..., description="Verbatim quote establishing the supersession/amendment"
    )
    doc_id: str = Field(..., description="Document where the superseding evidence appears")


class Edge(BaseModel):
    """Directed relation between two clause nodes."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    from_node: str = Field(..., alias="from", description="Source node being modified/superseded")
    to_node: str = Field(
        ..., alias="to", description="Target node doing the modification/superseding"
    )
    relation: EdgeRelation = Field(..., description="Relation type")
    from_date: str | None = Field(
        None, description="Date relation took effect (YYYY-MM-DD or UNKNOWN)"
    )
    evidence: EdgeEvidence
    confidence: ConfidenceLevel = Field(..., description="Confidence in edge validity")
    verification_status: str | None = Field(None, description="UNVERIFIED until checked by a human")
    notes: str | None = Field(None, description="Provenance notes for the edge")


class SupersessionGraph(BaseModel):
    """Graph structure containing clause nodes and regulatory relations."""

    model_config = ConfigDict(extra="forbid")

    nodes: dict[str, Node] = Field(default_factory=dict, description="Nodes indexed by node_id")
    edges: list[Edge] = Field(default_factory=list, description="Directed edges")
    superseded_documents: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Wholly superseded instruments -> date from which every clause is superseded. Each entry "
            "is backed by a superseded_by edge from a clause of that document."
        ),
    )

    def add_node(self, node: Node) -> None:
        """Add or update a node in the graph."""
        self.nodes[node.node_id] = node

    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Node | None:
        """Retrieve a node by its identifier."""
        return self.nodes.get(node_id)
