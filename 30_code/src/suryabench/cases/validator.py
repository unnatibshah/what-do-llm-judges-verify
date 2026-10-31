"""Validation assertions for benchmark cases and fault events."""

from suryabench.cases.schema import BenchmarkCase
from suryabench.core.enums import ExpectedDecision, FaultClass
from suryabench.core.exceptions import CaseValidationError


def validate_case(case: BenchmarkCase) -> None:
    """Validate programmatic integrity constraints on a benchmark case.

    Raises:
        CaseValidationError: If any integrity constraint is violated.
    """
    # 1. ID consistency
    for fe in case.fault_events:
        if fe.case_id != case.case_id:
            raise CaseValidationError(
                f"FaultEvent '{fe.fault_event_id}' case_id '{fe.case_id}' does not match Case '{case.case_id}'"
            )

    for nfo in case.non_fault_opportunities:
        if nfo.case_id != case.case_id:
            raise CaseValidationError(
                f"NonFaultOpportunity '{nfo.opportunity_id}' case_id '{nfo.case_id}' does not match Case '{case.case_id}'"
            )

    # 2. Clean case assertion
    probed = case.failure_class_probed.upper()
    if probed == "CLEAN":
        if len(case.fault_events) > 0:
            raise CaseValidationError(
                f"Case '{case.case_id}' marked as CLEAN but contains {len(case.fault_events)} fault events"
            )
        if case.expected_decision != ExpectedDecision.ANSWER:
            raise CaseValidationError(
                f"Clean case '{case.case_id}' must have expected_decision='ANSWER'"
            )

    # 3. Multi-fault case assertion
    elif probed == "MULTI":
        if len(case.fault_events) < 2:
            raise CaseValidationError(
                f"Case '{case.case_id}' marked as MULTI but contains only {len(case.fault_events)} fault events (must be >= 2)"
            )
        distinct_classes = {fe.fault_class for fe in case.fault_events}
        if len(distinct_classes) < 2:
            raise CaseValidationError(
                f"MULTI case '{case.case_id}' must combine >= 2 distinct fault classes, found: {distinct_classes}"
            )

    # 4. Probed single-fault class assertion
    elif probed in {f.value for f in FaultClass}:
        matching = [fe for fe in case.fault_events if fe.fault_class == probed]
        if not matching:
            raise CaseValidationError(
                f"Case '{case.case_id}' probes '{probed}' but contains no fault event with fault_class='{probed}'"
            )

    # 5. Abstention decision consistency
    if case.expected_decision == ExpectedDecision.ABSTAIN:
        if not case.abstention_reason:
            raise CaseValidationError(
                f"Case '{case.case_id}' expected_decision is ABSTAIN but abstention_reason is empty"
            )
        if not any(fc in case.abstention_reason for fc in ["F8", "F9", "conflict", "missing"]):
            raise CaseValidationError(
                f"Case '{case.case_id}' abstention_reason must document F8 (conflict) or F9 (missing facts)"
            )
    else:
        if case.abstention_reason is not None:
            raise CaseValidationError(
                f"Case '{case.case_id}' expected_decision is ANSWER but abstention_reason is populated"
            )


def validate_benchmark_suite(cases: list[BenchmarkCase]) -> None:
    """Validate a full benchmark case suite for uniqueness and composition invariants."""
    seen_case_ids: set[str] = set()
    for case in cases:
        if case.case_id in seen_case_ids:
            raise CaseValidationError(
                f"Duplicate case_id found in benchmark suite: '{case.case_id}'"
            )
        seen_case_ids.add(case.case_id)
        validate_case(case)
