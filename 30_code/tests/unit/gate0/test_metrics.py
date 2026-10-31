"""Unit tests for Gate 0 R1–R8 metrics computation and branch logic (protocol §9)."""

from suryabench.gate0.auditor import compute_gate0_metrics
from suryabench.gate0.registry import get_default_frozen_registry
from suryabench.gate0.schema import AuditChunk


def test_gate0_metrics_calculation() -> None:
    """Test deterministic R1–R8 metrics calculation from audited chunks."""
    registry = get_default_frozen_registry()

    chunks: list[AuditChunk] = []
    # Build 100 mock chunks (5 chunks for each of 20 queries)
    for q in registry.queries:
        for r in range(1, 6):
            is_superseded = q.band == "Q-A" and r == 1
            is_wrong_jur = q.band == "Q-B" and r == 2
            is_severed = r == 3
            is_undated = r == 4 and q.query_id == "Q-A-01"
            would_mislead = is_superseded or is_wrong_jur

            chunks.append(
                AuditChunk(
                    chunk_id=f"{q.query_id}#chk-{r}",
                    query_id=q.query_id,
                    rank=r,
                    doc_id="IN-C1-001" if not is_superseded else "IN-C1-002",
                    chunk_text=f"Sample text for {q.query_id} rank {r}",
                    similarity_score=0.85,
                    mapped_node_id=q.expected_governing_nodes[0] if r == 1 else None,
                    is_superseded=is_superseded,
                    is_wrong_jurisdiction=is_wrong_jur,
                    is_severed_from_scope=is_severed,
                    is_undated=is_undated,
                    would_mislead=would_mislead,
                )
            )

    assert len(chunks) == 100

    metrics = compute_gate0_metrics(chunks, registry)

    # 6 Q-A queries * 1 chunk = 6 superseded chunks
    assert metrics.r1_superseded_chunks == 6
    # 5 Q-B queries * 1 chunk = 5 wrong jurisdiction chunks
    assert metrics.r2_wrong_jurisdiction_chunks == 5
    # 20 queries * 1 chunk = 20 severed chunks
    assert metrics.r3_severed_chunks == 20
    # 1 undated chunk
    assert metrics.r6_undated_chunks == 1
    # 6 Q-A queries with superseded chunks
    assert metrics.r7_qa_superseded_queries == 6
    # 5 Q-B queries with wrong jurisdiction chunks
    assert metrics.r8_qb_wrong_jurisdiction_queries == 5

    assert metrics.would_mislead_total == 11
    assert metrics.misleading_percentage == 11.0
    assert "Proceed with sized cases" in metrics.branch_decision
