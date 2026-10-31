"""Schemas for Gate 0 Retrieval Exposure Audit (protocol §3, §8, §9)."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from suryabench.core.enums import SubjectTag


class QueryBand(StrEnum):
    """Gate 0 query bands per protocol §8."""

    Q_A = "Q-A"  # Currency-sensitive (n=6)
    Q_B = "Q-B"  # Jurisdiction-sensitive (n=5)
    Q_C = "Q-C"  # Structure-sensitive (n=4)
    Q_D = "Q-D"  # Multi-document (n=3)
    Q_E = "Q-E"  # Control (n=2)


class ExpectedNodeBasis(StrEnum):
    """Basis for expected governing node tag per protocol §8."""

    EXPLICIT_SUPERSESSION = "explicit_supersession"
    EXPLICIT_APPLICABILITY = "explicit_applicability"
    AUTHORITY_RESOLUTION = "authority_resolution"
    INFERRED = "inferred"
    UNDETERMINED = "undetermined"


class Gate0Query(BaseModel):
    """Schema for a single Gate 0 query record per protocol §8."""

    model_config = ConfigDict(extra="forbid")

    query_id: str
    band: QueryBand
    text: str
    subject: SubjectTag
    intended_jurisdiction: str
    jurisdiction_stated: bool
    expected_governing_nodes: list[str] = Field(default_factory=list)
    expected_node_basis: ExpectedNodeBasis = ExpectedNodeBasis.EXPLICIT_APPLICABILITY
    known_superseded_nodes: list[str] = Field(default_factory=list)


class Gate0QueryRegistry(BaseModel):
    """Frozen registry of 20 Gate 0 queries."""

    model_config = ConfigDict(extra="forbid")

    registry_version: str = "SuryaBench-Gate0-Queries-v1.0"
    frozen_at: str
    queries: list[Gate0Query]


class AuditChunk(BaseModel):
    """Schema for an audited chunk in the 100-chunk audit sheet per protocol §3."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    query_id: str
    rank: int
    doc_id: str
    chunk_text: str
    similarity_score: float
    mapped_node_id: str | None = None
    is_superseded: bool = False
    is_wrong_jurisdiction: bool = False
    is_severed_from_scope: bool = False
    is_undated: bool = False
    would_mislead: bool = False
    audit_notes: str | None = None


class Gate0Metrics(BaseModel):
    """Calculated Gate 0 Exposure Metrics R1 through R8 per protocol §9."""

    model_config = ConfigDict(extra="forbid")

    r1_superseded_chunks: int  # Chunks from superseded/partially-superseded clauses
    r2_wrong_jurisdiction_chunks: int  # Chunks from wrong jurisdiction
    r3_severed_chunks: int  # Chunks severed from scope header or effective date
    r4_missing_expected_node_queries: int  # Queries with no expected governing node in top 5
    r5_both_versions_present_queries: int  # Queries where both current & superseded appear
    r6_undated_chunks: int  # Undated chunks
    r7_qa_superseded_queries: int  # Q-A queries with >=1 superseded chunk (out of 6)
    r8_qb_wrong_jurisdiction_queries: int  # Q-B queries with >=1 wrong jurisdiction (out of 5)
    would_mislead_total: int
    misleading_percentage: float
    branch_decision: str
