"""Unit tests for Gate 0 Query Registry invariants (protocol §8)."""

from suryabench.gate0.registry import (
    compute_registry_sha256,
    get_default_frozen_registry,
    validate_query_registry,
)
from suryabench.gate0.schema import QueryBand


def test_frozen_registry_invariants() -> None:
    """Test that the frozen registry strictly satisfies all protocol §8 constraints."""
    registry = get_default_frozen_registry()
    validate_query_registry(registry)

    assert len(registry.queries) == 20

    band_counts: dict[QueryBand, int] = {}
    for q in registry.queries:
        band_counts[q.band] = band_counts.get(q.band, 0) + 1

    assert band_counts[QueryBand.Q_A] == 6
    assert band_counts[QueryBand.Q_B] == 5
    assert band_counts[QueryBand.Q_C] == 4
    assert band_counts[QueryBand.Q_D] == 3
    assert band_counts[QueryBand.Q_E] == 2

    # Verify Q-B state omission rule (>=3 omit state)
    qb_omitted = [
        q for q in registry.queries if q.band == QueryBand.Q_B and not q.jurisdiction_stated
    ]
    assert len(qb_omitted) >= 3

    # Verify non-empty texts and valid expected nodes
    for q in registry.queries:
        assert len(q.text.strip()) >= 15
        assert len(q.expected_governing_nodes) >= 1
        assert all("#" in n for n in q.expected_governing_nodes)

    # Hash determinism
    digest1 = compute_registry_sha256(registry)
    digest2 = compute_registry_sha256(registry)
    assert digest1 == digest2
    assert len(digest1) == 64
