"""Deterministic benchmark evaluators and metrics computation.

Computes:
1. Case correctness and unsupported-correct rate with rule-node clustered bootstrap 95% CIs.
2. Per-failure-class error rates (F1–F9, with F4-R vs F4-C split).
3. Verifier sensitivity conditioned on generator commitment and specificity over non-fault opportunities and avoided traps.
4. Rule-node / clause-clustered bootstrap confidence intervals per Protocol §16 and stats.py.
5. Sparse class handling: suppresses point estimate when opportunities n < 5 and reports raw counts.
6. Cost-weighted error sweeps across low, central, and high asymmetry cost matrices.
7. Abstention precision and recall on unanswerable cases.
8. Oracle-gap decomposition (Arm 2 vs Arm 2-O).
"""

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from suryabench.analysis.stats import cluster_bootstrap_ci
from suryabench.cases.schema import BenchmarkCase, FaultEvent
from suryabench.core.enums import ExpectedDecision, FaultClass
from suryabench.eval.failure_classifier import CaseClassificationResult


class MetricWithCI(BaseModel):
    """Metric point estimate with rule-node clustered bootstrap 95% CI per Protocol §16."""

    model_config = ConfigDict(extra="forbid")

    point_estimate: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    std_err: float | None = None
    event_count: int
    total_opportunities: int
    n_clusters: int
    is_sparse: bool = False
    formatted: str


class CostMatrix(BaseModel):
    """Cost weights for asymmetric policy errors per protocol §16 & charter §10."""

    model_config = ConfigDict(extra="forbid")

    name: str
    false_rejection_cost: float = Field(
        default=1.0, description="Cost of falsely rejecting a compliant application"
    )
    false_approval_cost: float = Field(
        default=5.0,
        description="Cost of falsely approving an illegal/overloaded/non-ALMM installation",
    )
    false_abstention_cost: float = Field(
        default=1.0, description="Cost of unnecessarily abstaining on an answerable case"
    )
    unjustified_answer_cost: float = Field(
        default=3.0,
        description="Cost of answering when missing telemetry or conflict required abstention",
    )


# Pre-registered cost matrices swept in sensitivity analysis
LOW_COST_MATRIX = CostMatrix(
    name="low_asymmetry",
    false_rejection_cost=1.0,
    false_approval_cost=2.0,
    false_abstention_cost=1.0,
    unjustified_answer_cost=1.5,
)

CENTRAL_COST_MATRIX = CostMatrix(
    name="central",
    false_rejection_cost=1.0,
    false_approval_cost=5.0,
    false_abstention_cost=1.0,
    unjustified_answer_cost=3.0,
)

HIGH_COST_MATRIX = CostMatrix(
    name="high_asymmetry",
    false_rejection_cost=1.0,
    false_approval_cost=20.0,
    false_abstention_cost=2.0,
    unjustified_answer_cost=10.0,
)


class BenchmarkScorecard(BaseModel):
    """Aggregate benchmark evaluation metrics for an experimental arm."""

    model_config = ConfigDict(extra="forbid")

    arm_id: str
    total_cases: int
    correct_cases: int
    accuracy: float
    accuracy_ci: MetricWithCI | None = None
    unsupported_correct_count: int
    unsupported_correct_rate: float
    unsupported_correct_ci: MetricWithCI | None = None
    fault_counts: dict[str, int] = Field(default_factory=dict)
    fault_rates: dict[str, float] = Field(default_factory=dict)
    verifier_sensitivity_per_class: dict[str, float] = Field(default_factory=dict)
    verifier_sensitivity_ci_per_class: dict[str, MetricWithCI] = Field(default_factory=dict)
    verifier_overall_sensitivity: float = 0.0
    verifier_overall_sensitivity_ci: MetricWithCI | None = None
    verifier_overall_specificity: float = 1.0
    verifier_overall_specificity_ci: MetricWithCI | None = None
    abstention_precision: float = 0.0
    abstention_recall: float = 0.0
    cost_weighted_error: dict[str, float] = Field(default_factory=dict)
    mean_evidence_overlap_jaccard: float | None = None
    evidence_overlap_by_config: dict[str, float] = Field(default_factory=dict)
    # Non-vacuous cases behind each mean (both-empty overlaps are undefined and excluded)
    evidence_overlap_n_by_config: dict[str, int] = Field(default_factory=dict)


def build_metric_with_ci(
    records: list[dict[str, Any]],
    value_key: str,
    cluster_key: str = "cluster_clause_id",
    min_opportunities: int = 5,
    min_clusters: int = 3,
    seed: int = 42,
) -> MetricWithCI:
    """Build a MetricWithCI evaluating point estimate and rule-node clustered bootstrap CI."""
    total = len(records)
    if total == 0:
        return MetricWithCI(
            point_estimate=None,
            event_count=0,
            total_opportunities=0,
            n_clusters=0,
            is_sparse=True,
            formatted="0/0 (no opportunities)",
        )

    event_count = int(sum(r[value_key] for r in records))
    unique_clusters = {r[cluster_key] for r in records}
    n_clusters = len(unique_clusters)

    if total < min_opportunities or n_clusters < min_clusters:
        reasons = []
        if total < min_opportunities:
            reasons.append(f"n<{min_opportunities}")
        if n_clusters < min_clusters:
            reasons.append(f"clusters<{min_clusters}")
        reason_str = ", ".join(reasons)
        return MetricWithCI(
            point_estimate=None,
            ci_lower=None,
            ci_upper=None,
            std_err=None,
            event_count=event_count,
            total_opportunities=total,
            n_clusters=n_clusters,
            is_sparse=True,
            formatted=f"{event_count}/{total} (sparse class, {reason_str}, point estimate suppressed)",
        )

    def metric_fn(recs: list[dict[str, Any]]) -> float:
        return sum(r[value_key] for r in recs) / len(recs) if recs else 0.0

    boot_res = cluster_bootstrap_ci(
        records=records,
        cluster_key=cluster_key,
        metric_fn=metric_fn,
        n_replicates=1000,
        ci=0.95,
        seed=seed,
    )

    pt = boot_res.point_estimate
    lower = boot_res.ci_lower
    upper = boot_res.ci_upper
    std_err = boot_res.std_err
    formatted = f"{pt * 100:.1f}% [{lower * 100:.1f}%, {upper * 100:.1f}%] ({event_count}/{total})"

    return MetricWithCI(
        point_estimate=pt,
        ci_lower=lower,
        ci_upper=upper,
        std_err=std_err,
        event_count=event_count,
        total_opportunities=total,
        n_clusters=n_clusters,
        is_sparse=False,
        formatted=formatted,
    )


def compute_benchmark_scorecard(
    arm_id: str,
    cases: list[BenchmarkCase],
    classifications: list[CaseClassificationResult],
    cost_matrices: list[CostMatrix] | None = None,
) -> BenchmarkScorecard:
    """Compute comprehensive benchmark scorecard from case classification results."""
    if not cases or not classifications:
        return BenchmarkScorecard(
            arm_id=arm_id,
            total_cases=0,
            correct_cases=0,
            accuracy=0.0,
            unsupported_correct_count=0,
            unsupported_correct_rate=0.0,
        )

    matrices = cost_matrices or [LOW_COST_MATRIX, CENTRAL_COST_MATRIX, HIGH_COST_MATRIX]
    total_cases = len(cases)
    correct_cases = sum(1 for c in classifications if c.is_correct)
    accuracy = correct_cases / total_cases if total_cases > 0 else 0.0

    unsupported_correct_count = sum(1 for c in classifications if c.unsupported_correct)
    unsupported_correct_rate = (
        unsupported_correct_count / total_cases if total_cases > 0 else 0.0
    )

    # Rule-node clustered bootstrap CI for accuracy & unsupported-correct rate
    acc_records = [
        {"cluster_clause_id": c.cluster_clause_id, "correct": 1.0 if c.is_correct else 0.0}
        for c in classifications
    ]
    accuracy_ci = build_metric_with_ci(acc_records, value_key="correct")

    unsup_records = [
        {
            "cluster_clause_id": c.cluster_clause_id,
            "unsup": 1.0 if c.unsupported_correct else 0.0,
        }
        for c in classifications
    ]
    unsupported_correct_ci = build_metric_with_ci(unsup_records, value_key="unsup")

    # -------------------------------------------------------------
    # 1. Fault counts and error rates (F1–F9, including F4-R and F4-C)
    # -------------------------------------------------------------
    fault_counts: dict[str, int] = defaultdict(int)
    for c in classifications:
        for fault in c.detected_faults:
            if fault.fault_class == FaultClass.F4 and fault.fault_subtype:
                fault_counts[fault.fault_subtype.value] += 1
            else:
                fault_counts[fault.fault_class.value] += 1

    fault_rates: dict[str, float] = {
        key: count / total_cases for key, count in fault_counts.items()
    }

    # -------------------------------------------------------------
    # 2. Verifier Sensitivity Conditioned on Generator Commitment
    # -------------------------------------------------------------
    # Build map of all fault events across cases
    fe_map: dict[str, FaultEvent] = {}
    for case in cases:
        for fe in case.fault_events:
            fe_map[fe.fault_event_id] = fe

    # Collect records strictly for fault events where generator committed the error
    committed_fe_records: list[dict[str, Any]] = []
    committed_by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for c in classifications:
        for fe_id, committed in c.fault_event_committed.items():
            if committed and fe_id in fe_map:
                fe = fe_map[fe_id]
                cls_key = fe.fault_class.value
                if fe.fault_class == FaultClass.F4 and fe.fault_subtype:
                    cls_key = fe.fault_subtype.value

                flagged = 1.0 if c.fault_event_matches.get(fe_id, False) else 0.0
                rec = {
                    "cluster_clause_id": c.cluster_clause_id,
                    "flagged": flagged,
                    "fe_id": fe_id,
                }
                committed_fe_records.append(rec)
                committed_by_class[cls_key].append(rec)

    # Compute overall conditioned sensitivity with bootstrap CI
    verifier_overall_sensitivity_ci = build_metric_with_ci(
        committed_fe_records, value_key="flagged"
    )
    verifier_overall_sensitivity = (
        verifier_overall_sensitivity_ci.point_estimate
        if verifier_overall_sensitivity_ci.point_estimate is not None
        else (
            verifier_overall_sensitivity_ci.event_count
            / verifier_overall_sensitivity_ci.total_opportunities
            if verifier_overall_sensitivity_ci.total_opportunities > 0
            else 1.0
        )
    )

    # Compute per-class conditioned sensitivity with bootstrap CIs
    sensitivity_per_class: dict[str, float] = {}
    sensitivity_ci_per_class: dict[str, MetricWithCI] = {}

    for cls_key, recs in committed_by_class.items():
        ci_obj = build_metric_with_ci(recs, value_key="flagged")
        sensitivity_ci_per_class[cls_key] = ci_obj
        if ci_obj.point_estimate is not None:
            sensitivity_per_class[cls_key] = ci_obj.point_estimate
        elif ci_obj.total_opportunities > 0:
            sensitivity_per_class[cls_key] = ci_obj.event_count / ci_obj.total_opportunities
        else:
            sensitivity_per_class[cls_key] = 0.0

    # -------------------------------------------------------------
    # 3. Verifier Specificity over NFOs and Avoided Traps
    # -------------------------------------------------------------
    specificity_records: list[dict[str, Any]] = []
    for c in classifications:
        # Non-fault opportunities: flag is a false positive
        for nfo_id, flagged in c.nfo_matches.items():
            specificity_records.append(
                {
                    "cluster_clause_id": c.cluster_clause_id,
                    "true_neg": 0.0 if flagged else 1.0,
                    "target_id": nfo_id,
                }
            )
        # Avoided traps: generator avoided the trap, so verifier flag is a false positive
        for fe_id, flagged in c.avoided_trap_matches.items():
            specificity_records.append(
                {
                    "cluster_clause_id": c.cluster_clause_id,
                    "true_neg": 0.0 if flagged else 1.0,
                    "target_id": fe_id,
                }
            )

    verifier_overall_specificity_ci = build_metric_with_ci(
        specificity_records, value_key="true_neg"
    )
    verifier_overall_specificity = (
        verifier_overall_specificity_ci.point_estimate
        if verifier_overall_specificity_ci.point_estimate is not None
        else (
            verifier_overall_specificity_ci.event_count
            / verifier_overall_specificity_ci.total_opportunities
            if verifier_overall_specificity_ci.total_opportunities > 0
            else 1.0
        )
    )

    # -------------------------------------------------------------
    # 4. Abstention Precision & Recall
    # -------------------------------------------------------------
    gold_abstain_cases = {
        case.case_id for case in cases if case.expected_decision == ExpectedDecision.ABSTAIN
    }
    agent_abstain_cases = {
        c.case_id for c in classifications if c.decision == ExpectedDecision.ABSTAIN
    }

    true_pos_abstain = len(gold_abstain_cases.intersection(agent_abstain_cases))
    abstention_precision = (
        true_pos_abstain / len(agent_abstain_cases) if agent_abstain_cases else 0.0
    )
    abstention_recall = (
        true_pos_abstain / len(gold_abstain_cases) if gold_abstain_cases else 0.0
    )

    # -------------------------------------------------------------
    # 5. Cost-Weighted Error Sweeps across matrices
    # -------------------------------------------------------------
    cost_weighted_error: dict[str, float] = {}
    case_map = {case.case_id: case for case in cases}

    for matrix in matrices:
        total_cost = 0.0
        for c in classifications:
            case = case_map[c.case_id]
            if (
                case.expected_decision == ExpectedDecision.ANSWER
                and case.expected_answer.blocking_stage is None
            ):
                if c.decision == ExpectedDecision.ABSTAIN:
                    total_cost += matrix.false_abstention_cost
                elif not c.is_correct:
                    total_cost += matrix.false_rejection_cost

            elif (
                case.expected_decision == ExpectedDecision.ANSWER
                and case.expected_answer.blocking_stage is not None
            ):
                if c.decision == ExpectedDecision.ABSTAIN:
                    total_cost += matrix.false_abstention_cost
                elif not c.is_correct:
                    total_cost += matrix.false_approval_cost

            elif (
                case.expected_decision == ExpectedDecision.ABSTAIN
                and c.decision == ExpectedDecision.ANSWER
            ):
                total_cost += matrix.unjustified_answer_cost

        cost_weighted_error[matrix.name] = (
            total_cost / total_cases if total_cases > 0 else 0.0
        )

    # -------------------------------------------------------------
    # 6. Mean Evidence Overlap Jaccard Index (overall and by config)
    # -------------------------------------------------------------
    overlaps = [
        c.evidence_overlap_jaccard
        for c in classifications
        if c.evidence_overlap_jaccard is not None
    ]
    mean_overlap = sum(overlaps) / len(overlaps) if overlaps else None

    overlaps_by_config: dict[str, list[float]] = defaultdict(list)
    for c in classifications:
        if c.evidence_overlap_jaccard is not None and c.independence_config:
            overlaps_by_config[c.independence_config].append(c.evidence_overlap_jaccard)
    evidence_overlap_by_config = {
        cfg: round(sum(ovs) / len(ovs), 4) for cfg, ovs in overlaps_by_config.items() if ovs
    }
    evidence_overlap_n_by_config = {cfg: len(ovs) for cfg, ovs in overlaps_by_config.items()}

    return BenchmarkScorecard(
        arm_id=arm_id,
        total_cases=total_cases,
        correct_cases=correct_cases,
        accuracy=accuracy,
        accuracy_ci=accuracy_ci,
        unsupported_correct_count=unsupported_correct_count,
        unsupported_correct_rate=unsupported_correct_rate,
        unsupported_correct_ci=unsupported_correct_ci,
        fault_counts=dict(fault_counts),
        fault_rates=fault_rates,
        verifier_sensitivity_per_class=sensitivity_per_class,
        verifier_sensitivity_ci_per_class=sensitivity_ci_per_class,
        verifier_overall_sensitivity=verifier_overall_sensitivity,
        verifier_overall_sensitivity_ci=verifier_overall_sensitivity_ci,
        verifier_overall_specificity=verifier_overall_specificity,
        verifier_overall_specificity_ci=verifier_overall_specificity_ci,
        abstention_precision=abstention_precision,
        abstention_recall=abstention_recall,
        cost_weighted_error=cost_weighted_error,
        mean_evidence_overlap_jaccard=mean_overlap,
        evidence_overlap_by_config=evidence_overlap_by_config,
        evidence_overlap_n_by_config=evidence_overlap_n_by_config,
    )


def compute_oracle_gap(
    arm2_scorecard: BenchmarkScorecard,
    arm2o_scorecard: BenchmarkScorecard,
) -> dict[str, float]:
    """Compute the oracle gap isolating retrieval error from reasoning error per protocol §14."""
    accuracy_gap = arm2o_scorecard.accuracy - arm2_scorecard.accuracy
    error_gap = (1.0 - arm2_scorecard.accuracy) - (1.0 - arm2o_scorecard.accuracy)

    arm2_error = 1.0 - arm2_scorecard.accuracy
    retrieval_attributed_pct = (
        (error_gap / arm2_error * 100.0) if arm2_error > 0 else 0.0
    )

    return {
        "arm2_accuracy": arm2_scorecard.accuracy,
        "arm2o_accuracy": arm2o_scorecard.accuracy,
        "accuracy_oracle_gap": accuracy_gap,
        "error_gap": error_gap,
        "retrieval_attributed_error_pct": max(0.0, retrieval_attributed_pct),
        "reasoning_attributed_error_pct": max(
            0.0, 100.0 - max(0.0, retrieval_attributed_pct)
        ),
    }
