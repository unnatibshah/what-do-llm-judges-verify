"""Evaluation subpackage for SuryaBench (WS8 / D9).

Provides:
- FailureClassifier: Deterministic classifier detecting F1–F9 failure classes.
- BenchmarkScorecard, compute_benchmark_scorecard, compute_oracle_gap: Metric computation.
- BenchmarkRunner, BenchmarkRunConfig, RunResult: Multi-arm execution engine.
- RunManifest, save_run_manifest, load_run_manifest: Reproducibility manifests.
"""

from suryabench.eval.evaluators import (
    CENTRAL_COST_MATRIX,
    HIGH_COST_MATRIX,
    LOW_COST_MATRIX,
    BenchmarkScorecard,
    CostMatrix,
    compute_benchmark_scorecard,
    compute_oracle_gap,
)
from suryabench.eval.failure_classifier import (
    CaseClassificationResult,
    DetectedFault,
    FailureClassifier,
    evaluate_verifier_over_fault_events,
    evaluate_verifier_over_nfos,
)
from suryabench.eval.manifest import RunManifest, load_run_manifest, save_run_manifest
from suryabench.eval.runner import BenchmarkRunConfig, BenchmarkRunner, RunResult

__all__ = [
    "CENTRAL_COST_MATRIX",
    "HIGH_COST_MATRIX",
    "LOW_COST_MATRIX",
    "BenchmarkRunConfig",
    "BenchmarkRunner",
    "BenchmarkScorecard",
    "CaseClassificationResult",
    "CostMatrix",
    "DetectedFault",
    "FailureClassifier",
    "RunManifest",
    "RunResult",
    "compute_benchmark_scorecard",
    "compute_oracle_gap",
    "evaluate_verifier_over_fault_events",
    "evaluate_verifier_over_nfos",
    "load_run_manifest",
    "save_run_manifest",
]
