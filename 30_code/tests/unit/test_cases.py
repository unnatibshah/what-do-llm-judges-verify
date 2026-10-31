"""Unit tests for BenchmarkCase, FaultEvent, and TestSplitGuard."""

import json
from pathlib import Path

import pytest

from suryabench.cases.schema import BenchmarkCase, FaultEvent
from suryabench.cases.validator import validate_benchmark_suite, validate_case
from suryabench.core.enums import ExpectedDecision, FaultClass, FaultSubtype
from suryabench.core.exceptions import CaseValidationError, TestSplitAccessViolation
from suryabench.core.guard import TestSplitGuard

FIXTURE_CASES_PATH = Path(__file__).parents[1] / "fixtures" / "cases" / "fixture_cases.json"


def _load_fixture_cases() -> list[BenchmarkCase]:
    with open(FIXTURE_CASES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return [BenchmarkCase.model_validate(c) for c in data]


def test_load_and_validate_fixture_case() -> None:
    """Test loading and validating the fixture case suite."""
    cases = _load_fixture_cases()
    assert len(cases) == 1
    case = cases[0]

    assert case.case_id == "MH-T1-001"
    assert case.failure_class_probed == "F3"
    assert len(case.fault_events) == 1
    assert case.fault_events[0].fault_class == FaultClass.F3
    assert len(case.non_fault_opportunities) == 2

    # Should pass all programmatic assertions
    validate_case(case)
    validate_benchmark_suite(cases)


def test_clean_case_validation() -> None:
    """Test that a CLEAN case must have 0 fault events."""
    cases = _load_fixture_cases()
    clean_case = cases[0].model_copy(deep=True)
    clean_case.failure_class_probed = "CLEAN"
    clean_case.fault_events = []  # Properly cleared

    validate_case(clean_case)

    # If CLEAN case has a fault event, must fail
    clean_case.fault_events = [cases[0].fault_events[0]]
    with pytest.raises(CaseValidationError, match="marked as CLEAN but contains"):
        validate_case(clean_case)


def test_f4_subtype_validation() -> None:
    """Test that F4 events must specify F4-R or F4-C subtype, and others must have None."""
    # Valid F4 event
    fe_f4 = FaultEvent(
        fault_event_id="CASE#fe-1",
        case_id="CASE",
        fault_class=FaultClass.F4,
        fault_subtype=FaultSubtype.F4_R,
        gold_trigger="Central guideline was omitted from retrieval",
        gold_evidence=["IN-C1-001#cl-4.1"],
        expected_behavior="Retrieve and cite IN-C1-001#cl-4.1",
    )
    assert fe_f4.fault_subtype == FaultSubtype.F4_R

    # Invalid: F4 without subtype
    with pytest.raises(ValueError, match="must specify fault_subtype"):
        FaultEvent(
            fault_event_id="CASE#fe-2",
            case_id="CASE",
            fault_class=FaultClass.F4,
            fault_subtype=None,
            gold_trigger="Omitted",
            gold_evidence=["DOC#cl-1"],
            expected_behavior="Cite rule",
        )

    # Invalid: F3 with F4 subtype
    with pytest.raises(ValueError, match="fault_subtype must be None"):
        FaultEvent(
            fault_event_id="CASE#fe-3",
            case_id="CASE",
            fault_class=FaultClass.F3,
            fault_subtype=FaultSubtype.F4_R,
            gold_trigger="Currency trap",
            gold_evidence=["DOC#cl-2"],
            expected_behavior="Cite live rule",
        )


def test_abstention_case_validation() -> None:
    """Test that an ABSTAIN case must carry a valid abstention_reason documenting F8 or F9."""
    cases = _load_fixture_cases()
    abstain_case = cases[0].model_copy(deep=True)
    abstain_case.failure_class_probed = "F9"
    abstain_case.expected_decision = ExpectedDecision.ABSTAIN
    abstain_case.abstention_reason = "F9: Mandatory sanctioned load missing from consumer inputs"
    abstain_case.fault_events = [
        FaultEvent(
            fault_event_id=f"{abstain_case.case_id}#fe-f9",
            case_id=abstain_case.case_id,
            fault_class=FaultClass.F9,
            fault_subtype=None,
            gold_trigger="Mandatory case facts missing",
            gold_evidence=[],
            expected_behavior="Abstain due to missing load information",
        )
    ]

    validate_case(abstain_case)

    # Missing reason
    abstain_case.abstention_reason = None
    with pytest.raises(CaseValidationError, match="abstention_reason is empty"):
        validate_case(abstain_case)


def test_test_split_guard_enforcement() -> None:
    """Test that TestSplitGuard blocks unauthorized access to held-out test cases."""
    test_case_path = "benchmark/test_split/case_099.json"

    # Unauthorized access -> raises TestSplitAccessViolation
    with pytest.raises(TestSplitAccessViolation, match="Prohibited access"):
        TestSplitGuard.verify_access(test_case_path)

    # Authorized access under context manager -> succeeds
    with TestSplitGuard.authorize():
        assert TestSplitGuard.is_authorized() is True
        TestSplitGuard.verify_access(test_case_path)  # Should not raise

    # Guard re-locks after context exit
    assert TestSplitGuard.is_authorized() is False
    with pytest.raises(TestSplitAccessViolation):
        TestSplitGuard.verify_access(test_case_path)
