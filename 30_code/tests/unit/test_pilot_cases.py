"""Unit tests for the 10-case pilot suite (protocol §7A, §1.4)."""

from suryabench.cases.pilot import get_pilot_cases
from suryabench.cases.validator import validate_benchmark_suite


def test_pilot_suite_integrity() -> None:
    """Test that all 10 pilot cases satisfy the full benchmark integrity validator."""
    cases = get_pilot_cases()
    assert len(cases) == 10
    validate_benchmark_suite(cases)

    # Check partition distribution
    probed = [c.failure_class_probed for c in cases]
    assert probed.count("CLEAN") == 2
    assert probed.count("F5") == 2
    assert probed.count("F3") == 2
    assert probed.count("F2") == 1
    assert probed.count("F6") == 1
    assert probed.count("MULTI") == 1
    assert probed.count("F9") == 1

    # Check non-fault opportunities presence
    for c in cases:
        assert len(c.non_fault_opportunities) >= 1
        assert all(nfo.gold_valid for nfo in c.non_fault_opportunities)
