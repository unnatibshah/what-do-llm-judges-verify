"""Unit tests for statistical inference and cluster-bootstrap pipeline (protocol §1.4.6, §4.2)."""

import math
from typing import Any

import pytest

from suryabench.analysis.stats import cluster_bootstrap_ci, mcnemar_test


def test_mcnemar_identical_outcomes() -> None:
    """Test McNemar test when both models agree on all cases."""
    outcomes_a = [True, False, True, True, False]
    outcomes_b = [True, False, True, True, False]

    res = mcnemar_test(outcomes_a, outcomes_b)
    assert res.n_discordant_a == 0
    assert res.n_discordant_b == 0
    assert res.chi2_stat == 0.0
    assert res.p_value == 1.0
    assert not res.is_significant


def test_mcnemar_significant_discordance() -> None:
    """Test McNemar test with strong asymmetrical discordance."""
    # A is correct when B fails in 15 cases; B is correct when A fails in 1 case
    outcomes_a = [True] * 15 + [False] * 1 + [True] * 10
    outcomes_b = [False] * 15 + [True] * 1 + [True] * 10

    res = mcnemar_test(outcomes_a, outcomes_b)
    assert res.n_discordant_a == 15
    assert res.n_discordant_b == 1
    assert res.is_significant
    assert res.p_value < 0.01


def test_mcnemar_length_mismatch() -> None:
    """Test that mismatched sample lengths raise ValueError."""
    with pytest.raises(ValueError, match="Mismatched sample lengths"):
        mcnemar_test([True, False], [True])


def test_cluster_bootstrap_ci_basic() -> None:
    """Test cluster-bootstrap confidence interval computation."""
    # Synthetic records across 4 clusters (rule nodes)
    records: list[dict[str, Any]] = [
        {"cluster": "rule_A", "correct": 1},
        {"cluster": "rule_A", "correct": 1},
        {"cluster": "rule_B", "correct": 0},
        {"cluster": "rule_B", "correct": 1},
        {"cluster": "rule_C", "correct": 1},
        {"cluster": "rule_C", "correct": 1},
        {"cluster": "rule_D", "correct": 0},
        {"cluster": "rule_D", "correct": 0},
    ]

    def accuracy_metric(recs: list[dict[str, Any]]) -> float:
        return float(sum(r["correct"] for r in recs) / len(recs))

    ci_res = cluster_bootstrap_ci(
        records=records,
        cluster_key="cluster",
        metric_fn=accuracy_metric,
        n_replicates=500,
        ci=0.95,
        seed=42,
    )

    assert ci_res.n_clusters == 4
    assert ci_res.point_estimate == 0.625
    assert ci_res.ci_lower <= ci_res.point_estimate <= ci_res.ci_upper
    assert ci_res.std_err > 0.0
    assert 0.0 <= ci_res.ci_lower <= 1.0
    assert 0.0 <= ci_res.ci_upper <= 1.0


def test_cluster_bootstrap_single_cluster() -> None:
    """Test edge case with fewer than 2 clusters."""
    records: list[dict[str, Any]] = [{"cluster": "rule_A", "score": 0.8}]
    ci_res = cluster_bootstrap_ci(
        records=records,
        cluster_key="cluster",
        metric_fn=lambda recs: float(recs[0]["score"]),
    )
    assert ci_res.ci_lower == ci_res.ci_upper == 0.8
    assert ci_res.std_err == 0.0


def test_exact_mcnemar_and_holm() -> None:
    from suryabench.analysis.stats import holm

    a = [True] * 30 + [False] * 10
    b = [False] * 30 + [True] * 10
    exact = mcnemar_test(a, b, exact=True)
    assert exact.p_value == round(2 * sum(math.comb(40, k) for k in range(11)) / 2**40, 5)
    assert mcnemar_test(a, b).p_value != exact.p_value  # asymptotic above 25 discordant pairs
    h = holm({"x": 0.01, "y": 0.04, "z": 0.03})
    assert h["x"]["p_holm"] == 0.03 and h["z"]["p_holm"] == 0.06 and h["y"]["p_holm"] == 0.06
    assert h["x"]["reject"] and not h["y"]["reject"] and not h["z"]["reject"]
