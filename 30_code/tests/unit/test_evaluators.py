"""Unit tests for SuryaBench evaluators and scorecard metrics."""

import pytest

from suryabench.applicability.schema import CaseFacts
from suryabench.cases.schema import (
    BenchmarkCase,
    CaseInputs,
    ExpectedAnswer,
    FaultEvent,
    GroundTruthProvenance,
    NonFaultOpportunity,
)
from suryabench.core.enums import (
    ConfidenceLevel,
    ConsumerCategory,
    ExpectedDecision,
    FaultClass,
    StateCode,
)
from suryabench.eval.evaluators import (
    CENTRAL_COST_MATRIX,
    HIGH_COST_MATRIX,
    LOW_COST_MATRIX,
    BenchmarkScorecard,
    compute_benchmark_scorecard,
    compute_oracle_gap,
)
from suryabench.eval.failure_classifier import CaseClassificationResult, DetectedFault


def make_case(
    case_id: str,
    expected_decision: ExpectedDecision = ExpectedDecision.ANSWER,
    is_clean: bool = True,
    fault_events: list[FaultEvent] | None = None,
    nfos: list[NonFaultOpportunity] | None = None,
) -> BenchmarkCase:
    return BenchmarkCase(
        case_id=case_id,
        corpus_version="v1.0",
        facts=CaseFacts(
            state=StateCode.MH,
            consumer_category=ConsumerCategory.RESIDENTIAL,
            sanctioned_load_kw=5.0,
            proposed_capacity_kw=4.0,
        ),
        inputs=CaseInputs(bill="bill", proposal="proposal", portal_state="portal"),
        applicable_rules=[],
        expected_answer=ExpectedAnswer(
            blocking_stage=None if is_clean else "feasibility_rejected",
            root_cause="nominal_compliant" if is_clean else "capacity_exceeded",
        ),
        ground_truth_provenance=GroundTruthProvenance(basis="explicit", confidence=ConfidenceLevel.HIGH),
        failure_class_probed="CLEAN" if is_clean else "F5",
        expected_decision=expected_decision,
        fault_events=fault_events or [],
        non_fault_opportunities=nfos or [],
    )


def test_scorecard_accuracy_and_fault_rates() -> None:
    """Validate scorecard accuracy, unsupported-correct, and fault rates."""
    cases = [
        make_case("C1", is_clean=True),
        make_case("C2", is_clean=False),
        make_case("C3", expected_decision=ExpectedDecision.ABSTAIN, is_clean=False),
    ]

    classifications = [
        CaseClassificationResult(
            case_id="C1",
            cluster_clause_id="MH-C3-001#cl-6.2",
            decision=ExpectedDecision.ANSWER,
            expected_decision=ExpectedDecision.ANSWER,
            is_correct=True,
            unsupported_correct=False,
            detected_faults=[],
        ),
        CaseClassificationResult(
            case_id="C2",
            cluster_clause_id="MH-C3-001#cl-6.2",
            decision=ExpectedDecision.ANSWER,
            expected_decision=ExpectedDecision.ANSWER,
            is_correct=True,
            unsupported_correct=True,
            detected_faults=[
                DetectedFault(
                    fault_class=FaultClass.F3,
                    trigger="superseded_clause",
                    description="Cited superseded clause",
                )
            ],
        ),
        CaseClassificationResult(
            case_id="C3",
            cluster_clause_id="MH-C3-001#cl-6.2",
            decision=ExpectedDecision.ANSWER,  # Failed to abstain
            expected_decision=ExpectedDecision.ABSTAIN,
            is_correct=False,
            unsupported_correct=False,
            detected_faults=[
                DetectedFault(
                    fault_class=FaultClass.F9,
                    trigger="failure_to_abstain",
                    description="Failed to abstain",
                )
            ],
        ),
    ]

    sc = compute_benchmark_scorecard("test_arm", cases, classifications)

    assert sc.total_cases == 3
    assert sc.correct_cases == 2
    assert pytest.approx(sc.accuracy) == 2 / 3
    assert sc.unsupported_correct_count == 1
    assert pytest.approx(sc.unsupported_correct_rate) == 1 / 3
    assert sc.fault_counts["F3"] == 1
    assert sc.fault_counts["F9"] == 1
    assert pytest.approx(sc.fault_rates["F3"]) == 1 / 3


def test_verifier_sensitivity_and_specificity() -> None:
    """Validate sensitivity across fault events and specificity across non-fault opportunities."""
    fe1 = FaultEvent(
        fault_event_id="FE-001",
        case_id="C1",
        fault_class=FaultClass.F5,
        gold_trigger="over_capacity",
        gold_evidence=["MH-C3-001#cl-6.2"],
        expected_behavior="reject_over_capacity",
    )
    fe2 = FaultEvent(
        fault_event_id="FE-002",
        case_id="C1",
        fault_class=FaultClass.F3,
        gold_trigger="superseded",
        gold_evidence=["IN-C1-002#cl-2"],
        expected_behavior="cite_in_force",
    )
    nfo1 = NonFaultOpportunity(
        opportunity_id="NFO-001",
        case_id="C1",
        target_property="currency",
        claim_text="IN-C1-001 is in force",
    )
    nfo2 = NonFaultOpportunity(
        opportunity_id="NFO-002",
        case_id="C1",
        target_property="jurisdiction",
        claim_text="MERC governs MH",
    )

    case = make_case("C1", is_clean=False, fault_events=[fe1, fe2], nfos=[nfo1, nfo2])

    classifications = [
        CaseClassificationResult(
            case_id="C1",
            cluster_clause_id="MH-C3-001#cl-6.2",
            decision=ExpectedDecision.ANSWER,
            expected_decision=ExpectedDecision.ANSWER,
            is_correct=False,
            unsupported_correct=False,
            fault_event_committed={"FE-001": True, "FE-002": True},
            fault_event_matches={"FE-001": True, "FE-002": False},  # Caught 1 of 2
            nfo_matches={"NFO-001": False, "NFO-002": True},  # 1 true negative, 1 false flag
        )
    ]

    sc = compute_benchmark_scorecard("verifier_arm", [case], classifications)

    # Sensitivity: 1 of 2 caught -> 50%
    assert pytest.approx(sc.verifier_overall_sensitivity) == 0.5
    assert pytest.approx(sc.verifier_sensitivity_per_class["F5"]) == 1.0
    assert pytest.approx(sc.verifier_sensitivity_per_class["F3"]) == 0.0

    # Specificity: 1 of 2 not flagged -> 50%
    assert pytest.approx(sc.verifier_overall_specificity) == 0.5


def test_cost_matrix_sweeps() -> None:
    """Validate cost-weighted error sweeps across Low, Central, and High matrices."""
    # Case with False Approval of illegal installation (cost 2 in low, 5 in central, 20 in high)
    case_illegal = make_case("C_illegal", is_clean=False)
    clf_illegal = CaseClassificationResult(
        case_id="C_illegal",
        cluster_clause_id="MH-C3-001#cl-6.2",
        decision=ExpectedDecision.ANSWER,
        expected_decision=ExpectedDecision.ANSWER,
        is_correct=False,  # False approval!
        unsupported_correct=False,
    )

    sc = compute_benchmark_scorecard(
        "arm",
        [case_illegal],
        [clf_illegal],
        cost_matrices=[LOW_COST_MATRIX, CENTRAL_COST_MATRIX, HIGH_COST_MATRIX],
    )

    assert sc.cost_weighted_error["low_asymmetry"] == 2.0
    assert sc.cost_weighted_error["central"] == 5.0
    assert sc.cost_weighted_error["high_asymmetry"] == 20.0


def test_oracle_gap_computation() -> None:
    """Validate oracle gap decomposition isolating retrieval error."""
    sc_arm2 = BenchmarkScorecard(
        arm_id="arm2",
        total_cases=100,
        correct_cases=60,
        accuracy=0.60,
        unsupported_correct_count=0,
        unsupported_correct_rate=0.0,
    )
    sc_arm2o = BenchmarkScorecard(
        arm_id="arm2o",
        total_cases=100,
        correct_cases=85,
        accuracy=0.85,
        unsupported_correct_count=0,
        unsupported_correct_rate=0.0,
    )

    gap = compute_oracle_gap(sc_arm2, sc_arm2o)
    assert pytest.approx(gap["accuracy_oracle_gap"]) == 0.25
    assert pytest.approx(gap["error_gap"]) == 0.25
    # Arm 2 error is 40%. 25% of that was resolved by oracle retrieval -> 62.5% retrieval-attributed
    assert pytest.approx(gap["retrieval_attributed_error_pct"]) == 62.5
    assert pytest.approx(gap["reasoning_attributed_error_pct"]) == 37.5


def test_sparse_class_and_cluster_floor_suppression() -> None:
    """Validate that metrics are suppressed when n < 5 or n_clusters < 3."""
    from suryabench.eval.evaluators import build_metric_with_ci

    # 1. Total < 5: Suppressed on n < 5
    sparse_n = [
        {"cluster_clause_id": "c1", "val": 1.0},
        {"cluster_clause_id": "c2", "val": 1.0},
        {"cluster_clause_id": "c3", "val": 0.0},
    ]
    m1 = build_metric_with_ci(sparse_n, value_key="val", min_opportunities=5, min_clusters=3)
    assert m1.is_sparse is True
    assert m1.point_estimate is None
    assert "n<5" in m1.formatted

    # 2. Total >= 5 (e.g. n=6), but across only 2 clusters: Suppressed on clusters < 3
    sparse_clusters = [
        {"cluster_clause_id": "c1", "val": 1.0},
        {"cluster_clause_id": "c1", "val": 1.0},
        {"cluster_clause_id": "c1", "val": 1.0},
        {"cluster_clause_id": "c2", "val": 0.0},
        {"cluster_clause_id": "c2", "val": 0.0},
        {"cluster_clause_id": "c2", "val": 1.0},
    ]
    m2 = build_metric_with_ci(sparse_clusters, value_key="val", min_opportunities=5, min_clusters=3)
    assert m2.is_sparse is True
    assert m2.point_estimate is None
    assert "clusters<3" in m2.formatted

    # 3. Total >= 5 (n=6) and clusters >= 3 (e.g. 3 clusters): Not suppressed, point estimate calculated
    dense = [
        {"cluster_clause_id": "c1", "val": 1.0},
        {"cluster_clause_id": "c1", "val": 1.0},
        {"cluster_clause_id": "c2", "val": 1.0},
        {"cluster_clause_id": "c2", "val": 0.0},
        {"cluster_clause_id": "c3", "val": 1.0},
        {"cluster_clause_id": "c3", "val": 0.0},
    ]
    m3 = build_metric_with_ci(dense, value_key="val", min_opportunities=5, min_clusters=3)
    assert m3.is_sparse is False
    assert m3.point_estimate is not None
    assert m3.ci_lower is not None
    assert m3.ci_upper is not None


def test_jaccard_overlap_by_config() -> None:
    """Validate that scorecard computes mean evidence overlap overall and partitioned by config."""
    cases = [make_case("C1", is_clean=True), make_case("C2", is_clean=True)]
    classifications = [
        CaseClassificationResult(
            case_id="C1",
            cluster_clause_id="MH-C3-001#cl-6.2",
            decision=ExpectedDecision.ANSWER,
            expected_decision=ExpectedDecision.ANSWER,
            is_correct=True,
            unsupported_correct=False,
            evidence_overlap_jaccard=1.0,
            independence_config="000",
        ),
        CaseClassificationResult(
            case_id="C2",
            cluster_clause_id="MH-C3-001#cl-6.2",
            decision=ExpectedDecision.ANSWER,
            expected_decision=ExpectedDecision.ANSWER,
            is_correct=True,
            unsupported_correct=False,
            evidence_overlap_jaccard=0.3333,
            independence_config="111",
        ),
    ]

    sc = compute_benchmark_scorecard("test_arm", cases, classifications)
    assert sc.mean_evidence_overlap_jaccard is not None
    assert pytest.approx(sc.mean_evidence_overlap_jaccard, rel=1e-3) == (1.0 + 0.3333) / 2
    assert sc.evidence_overlap_by_config["000"] == 1.0
    assert sc.evidence_overlap_by_config["111"] == 0.3333

